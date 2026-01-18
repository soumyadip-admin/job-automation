"""
Email Parser - Reads Naukri job alert emails from Gmail
Bypasses Naukri website blocking by reading email alerts instead
"""
import os
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Try to import optional dependencies
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ requests/beautifulsoup4 not installed")

load_dotenv()


class EmailParser:
    """Parses job alert emails from Naukri and other job portals."""
    
    def __init__(self):
        self.gmail_user = os.getenv('GMAIL_ADDRESS')
        self.gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
        self.enabled = bool(self.gmail_user and self.gmail_app_password)
        self.mail = None
        
        if not self.enabled:
            print("⚠️ Gmail not configured.")
            print("   Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env file")
    
    def connect(self):
        """Connect to Gmail IMAP server."""
        if not self.enabled:
            return False
        
        try:
            print("📧 Connecting to Gmail...")
            self.mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            self.mail.login(self.gmail_user, self.gmail_app_password)
            self.mail.select('inbox')
            print("✅ Connected to Gmail")
            return True
        except imaplib.IMAP4.error as e:
            print(f"❌ Gmail login failed: {e}")
            print("   Make sure you're using an App Password, not your regular password")
            print("   Generate one at: https://myaccount.google.com/apppasswords")
            return False
        except Exception as e:
            print(f"❌ Gmail connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Gmail."""
        try:
            if self.mail:
                self.mail.close()
                self.mail.logout()
                print("📧 Disconnected from Gmail")
        except:
            pass
    
    def search_naukri_emails(self, days_back=7, max_emails=20):
        """Search for Naukri job alert emails."""
        if not self.mail:
            if not self.connect():
                return []
        
        try:
            # Calculate date range
            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            
            # Search criteria - emails from Naukri
            search_queries = [
                f'(FROM "naukri.com" SINCE {since_date})',
                f'(FROM "jobs-noreply@naukri.com" SINCE {since_date})',
                f'(FROM "info@naukri.com" SINCE {since_date})',
                f'(SUBJECT "job alert" SINCE {since_date})',
                f'(SUBJECT "naukri" SINCE {since_date})'
            ]
            
            all_email_ids = set()
            
            for query in search_queries:
                try:
                    status, data = self.mail.search(None, query)
                    if status == 'OK' and data[0]:
                        email_ids = data[0].split()
                        all_email_ids.update(email_ids)
                except:
                    continue
            
            email_ids = list(all_email_ids)
            print(f"   📬 Found {len(email_ids)} Naukri-related emails")
            
            return email_ids[-max_emails:]  # Return last N emails
            
        except Exception as e:
            print(f"❌ Email search error: {e}")
            return []
    
    def parse_email(self, email_id):
        """Parse a single email and extract job information."""
        try:
            status, data = self.mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                return None
            
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Decode subject
            subject, encoding = decode_header(msg['Subject'])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or 'utf-8')
            
            # Get sender
            sender = msg['From']
            
            # Get date
            date = msg['Date']
            
            # Get body
            body = self._get_email_body(msg)
            
            # Extract job links
            job_links = self._extract_job_links(body)
            
            # Extract job details from email body
            jobs = self._extract_jobs_from_body(body, subject)
            
            return {
                'subject': subject,
                'sender': sender,
                'date': date,
                'job_links': job_links,
                'jobs': jobs
            }
            
        except Exception as e:
            print(f"   ⚠️ Error parsing email: {e}")
            return None
    
    def _get_email_body(self, msg):
        """Extract email body (HTML or plain text)."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        text = payload.decode(charset, errors='ignore')
                        
                        if content_type == "text/html":
                            body = text  # Prefer HTML
                            break
                        elif content_type == "text/plain" and not body:
                            body = text
                except:
                    continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except:
                pass
        
        return body
    
    def _extract_job_links(self, body):
        """Extract Naukri job links from email body."""
        links = []
        
        if not REQUESTS_AVAILABLE:
            # Fallback to regex
            pattern = r'https?://[^\s<>"\']+naukri\.com[^\s<>"\']*job[^\s<>"\']*'
            matches = re.findall(pattern, body)
            links = list(set(matches))
        else:
            try:
                soup = BeautifulSoup(body, 'html.parser')
                
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if 'naukri.com' in href and ('job' in href.lower() or 'jd' in href.lower()):
                        # Clean URL
                        clean_url = href.split('?')[0]
                        if clean_url not in links:
                            links.append(clean_url)
            except:
                # Fallback to regex
                pattern = r'https?://[^\s<>"\']+naukri\.com[^\s<>"\']*'
                matches = re.findall(pattern, body)
                links = list(set(matches))
        
        return links[:10]  # Limit to 10 links per email
    
    def _extract_jobs_from_body(self, body, subject):
        """Extract job details directly from email body."""
        jobs = []
        
        if not REQUESTS_AVAILABLE:
            return jobs
        
        try:
            soup = BeautifulSoup(body, 'html.parser')
            
            # Look for job cards/sections in email
            # Naukri emails typically have job listings in table cells or divs
            
            # Try to find job titles
            job_elements = soup.find_all(['td', 'div', 'tr'], class_=lambda x: x and 'job' in x.lower() if x else False)
            
            if not job_elements:
                # Try finding by content patterns
                job_elements = soup.find_all(['td', 'div'], string=re.compile(r'(analyst|developer|engineer|executive)', re.I))
            
            for elem in job_elements[:5]:  # Limit to 5 jobs per email
                job = {}
                
                # Extract title
                title_elem = elem.find(['a', 'b', 'strong', 'h3', 'h4'])
                if title_elem:
                    job['title'] = title_elem.get_text().strip()
                
                # Extract company
                company_text = elem.get_text()
                company_match = re.search(r'at\s+([A-Za-z0-9\s&]+)', company_text)
                if company_match:
                    job['company'] = company_match.group(1).strip()
                
                # Extract location
                location_match = re.search(r'(bangalore|bengaluru|mumbai|delhi|hyderabad|chennai|pune|kolkata|remote)', company_text, re.I)
                if location_match:
                    job['location'] = location_match.group(1).strip()
                
                # Extract link
                link_elem = elem.find('a', href=True)
                if link_elem and 'naukri.com' in link_elem['href']:
                    job['url'] = link_elem['href'].split('?')[0]
                
                if job.get('title'):
                    job['platform'] = 'Naukri'
                    job['source'] = 'email_alert'
                    job['email_subject'] = subject
                    job['scraped_at'] = datetime.now().isoformat()
                    jobs.append(job)
        
        except Exception as e:
            pass
        
        return jobs
    
    def get_all_jobs(self, days_back=7, max_emails=10):
        """Get all jobs from recent Naukri emails."""
        print(f"\n📧 PARSING NAUKRI EMAIL ALERTS")
        print(f"   📅 Looking back {days_back} days")
        print(f"   📬 Max emails: {max_emails}")
        
        if not self.connect():
            return []
        
        all_jobs = []
        
        try:
            email_ids = self.search_naukri_emails(days_back=days_back, max_emails=max_emails)
            
            if not email_ids:
                print("   ⚠️ No Naukri emails found")
                print("   💡 Make sure you have Naukri job alerts set up")
                return []
            
            for i, email_id in enumerate(email_ids):
                print(f"   📖 Parsing email {i+1}/{len(email_ids)}...")
                
                email_data = self.parse_email(email_id)
                
                if email_data:
                    # Add jobs extracted from body
                    for job in email_data.get('jobs', []):
                        if job not in all_jobs:
                            all_jobs.append(job)
                    
                    # Also add jobs from links (as placeholders)
                    for link in email_data.get('job_links', []):
                        placeholder_job = {
                            'title': f"Job from {email_data['subject'][:30]}...",
                            'company': 'Check Link',
                            'location': 'India',
                            'url': link,
                            'platform': 'Naukri',
                            'source': 'email_link',
                            'email_subject': email_data['subject'],
                            'scraped_at': datetime.now().isoformat()
                        }
                        if placeholder_job not in all_jobs:
                            all_jobs.append(placeholder_job)
            
            print(f"\n   ✅ Found {len(all_jobs)} jobs from emails")
            return all_jobs
            
        except Exception as e:
            print(f"❌ Error getting jobs: {e}")
            return []
        
        finally:
            self.disconnect()


# Test the email parser
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING EMAIL PARSER")
    print("=" * 60)
    
    parser = EmailParser()
    
    if not parser.enabled:
        print("\n❌ Gmail not configured!")
        print("\nTo set up Gmail:")
        print("1. Enable 2-Step Verification: https://myaccount.google.com/security")
        print("2. Generate App Password: https://myaccount.google.com/apppasswords")
        print("3. Add to .env file:")
        print("   GMAIL_ADDRESS=your_email@gmail.com")
        print("   GMAIL_APP_PASSWORD=your_16_char_app_password")
        print("\nTo set up Naukri Job Alerts:")
        print("1. Go to naukri.com")
        print("2. Login to your account")
        print("3. Go to Profile → Job Alerts")
        print("4. Create alerts for: Data Analyst, MIS Analyst, Business Analyst")
        print("5. Set frequency to Daily")
    else:
        jobs = parser.get_all_jobs(days_back=7, max_emails=5)
        
        if jobs:
            print(f"\n{'=' * 60}")
            print(f"📊 FOUND {len(jobs)} JOBS")
            print(f"{'=' * 60}\n")
            
            for i, job in enumerate(jobs[:10], 1):
                print(f"{'─' * 50}")
                print(f"Job #{i}")
                print(f"📋 Title:   {job.get('title', 'N/A')}")
                print(f"🏢 Company: {job.get('company', 'N/A')}")
                print(f"📍 Location: {job.get('location', 'N/A')}")
                print(f"🔗 Source:  {job.get('source', 'N/A')}")
                if job.get('url'):
                    print(f"🔗 URL:     {job['url'][:60]}...")
        else:
            print("\n⚠️ No jobs found in emails")
            print("   Make sure you have Naukri job alerts set up")
    
    print("\n" + "=" * 60)