"""
Main Entry Point - Job Application Automation System
Supports: Naukri (Email Parser), LinkedIn (Scraping/Easy Apply), Email Alerts
"""
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add src to Python path
ROOT_DIR = Path(__file__).parent
SRC_DIR = ROOT_DIR / 'src'
sys.path.insert(0, str(SRC_DIR))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import modules
try:
    from modules.sheets_manager import SheetsManager
    from modules.notifier import Notifier
    from modules.matcher import JobMatcher
    from modules.cover_letter_generator import CoverLetterGenerator
    from modules.job_scraper import JobScraper
    from modules.linkedin_scraper import LinkedInScraper
    from modules.email_parser import EmailParser # Import Email Parser
    print("✅ All modules imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(f"   Details: {e}")
    sys.exit(1)


class JobAutomation:
    """Main automation orchestrator."""
    
    def __init__(self):
        print("\n" + "="*50)
        print("🚀 JOB APPLICATION AUTOMATION SYSTEM")
        print("="*50 + "\n")
        
        self.sheets = SheetsManager()
        self.notifier = Notifier()
        self.matcher = JobMatcher()
        self.cover_letter = CoverLetterGenerator()
        self.scraper = None
        self.linkedin_scraper = None
        
        self.stats = {
            'scanned': 0,
            'applied': 0,
            'skipped': 0,
            'errors': 0,
            'email_jobs_parsed': 0
        }
    
    def run_test(self):
        """Run with sample data."""
        print("🧪 RUNNING IN TEST MODE\n")
        
        self.sheets.connect()
        
        test_jobs = [
            # High score match (80%+)
            {
                'title': 'Junior Data Analyst - SQL Excel Python Tableau',
                'company': 'Amazing Analytics Corp',
                'location': 'Bengaluru',
                'url': 'https://example.com/job5',
                'platform': 'Test',
                'salary': '6-8 LPA',
                'description': 'SQL, Excel, Tableau, Power BI, Python, R, EDA, Statistics, Data Visualization'
            },
            # Review match (60-69%)
            {
                'title': 'MIS Analyst Reporting',
                'company': 'DataDriven Inc',
                'location': 'Remote',
                'url': 'https://example.com/job2',
                'platform': 'Test',
                'salary': '3-5 LPA'
            },
            # Excluded match
            {
                'title': 'Customer Service Representative',
                'company': 'Support Co',
                'location': 'Bengaluru',
                'url': 'https://example.com/job3',
                'platform': 'Test',
                'salary': '2-3 LPA'
            }
        ]
        
        for job in test_jobs:
            self._process_job(job)
        
        self._print_summary()
    
    def run_naukri(self, max_jobs=10):
        """Run Naukri web scraping automation (may be blocked)."""
        print("🔍 RUNNING NAUKRI WEB SCRAPING")
        
        self.sheets.connect()
        self.notifier.notify_startup()
        
        try:
            self.scraper = JobScraper(headless=True)
            if not self.scraper.start_browser():
                raise Exception("Browser failed to start")
            
            self.scraper.login_naukri()
            
            keywords = ['Data Analyst', 'MIS Analyst', 'Junior Business Analyst']
            
            for keyword in keywords:
                jobs = self.scraper.search_jobs(keyword, max_jobs=max_jobs)
                for job in jobs:
                    self._process_job(job)
            
        except Exception as e:
            print(f"❌ Error during Naukri web scrape: {e}")
            self.notifier.notify_error(f"Naukri Web Scrape Error: {str(e)}")
            self.stats['errors'] += 1
        
        finally:
            if self.scraper:
                self.scraper.close()
            self._print_summary()
            self.notifier.notify_summary(self.stats)

    def run_linkedin(self, max_jobs=10, auto_apply=False):
        """Run LinkedIn automation."""
        print("🔗 RUNNING LINKEDIN AUTOMATION\n")
        
        self.sheets.connect()
        self.notifier.notify_startup()
        
        try:
            self.linkedin_scraper = LinkedInScraper(headless=True)
            if not self.linkedin_scraper.start_browser():
                raise Exception("LinkedIn Browser failed to start")
            
            self.linkedin_scraper.login()
            
            keywords = ['Data Analyst', 'MIS Analyst', 'Business Analyst', 'Junior Data Analyst']
            
            for keyword in keywords:
                print(f"\n{'='*40}")
                jobs = self.linkedin_scraper.search_jobs(keyword, max_jobs=max_jobs)
                
                for job in jobs:
                    self._process_job(job, auto_apply=auto_apply)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            self.notifier.notify_error(f"LinkedIn Run Error: {str(e)}")
            self.stats['errors'] += 1
        
        finally:
            if self.linkedin_scraper:
                self.linkedin_scraper.close()
            self._print_summary()
            self.notifier.notify_summary(self.stats)

    def run_email_parser(self):
        """Parse Naukri job alert emails."""
        print("📧 RUNNING NAUKRI EMAIL PARSER\n")
        
        self.sheets.connect()
        self.notifier.notify_startup()
        
        try:
            parser = EmailParser()
            if not parser.enabled:
                print("⚠️ Email parser not configured (Check .env for Gmail credentials)")
                return
            
            jobs = parser.get_all_jobs(days_back=7, max_emails=10)
            
            if not jobs:
                print("   ⚠️ No Naukri emails found or parsed")
                return
            
            print(f"   📋 Found {len(jobs)} unique jobs from emails")
            
            for job in jobs:
                self._process_job(job)
            
        except Exception as e:
            print(f"❌ Error in Email Parser Run: {e}")
            self.notifier.notify_error(f"Email Parser Error: {str(e)}")
            self.stats['errors'] += 1
        
        finally:
            self._print_summary()
            self.notifier.notify_summary(self.stats)
    
    def _process_job(self, job, auto_apply=False):
        """Process a single job posting."""
        print(f"\n{'─'*40}")
        print(f"📋 {job.get('title', 'Unknown')}")
        print(f"🏢 {job.get('company', 'Unknown')}")
        print(f"📍 {job.get('location', 'N/A')}")
        
        self.stats['scanned'] += 1
        
        # Check if already applied
        if self.sheets._connected:
            if self.sheets.check_already_applied(job.get('url', '')):
                print("⏭️ Already applied - Skipping")
                self.stats['skipped'] += 1
                return
        
        # Calculate match score
        score, skills, recommendation, reason = self.matcher.calculate_score(
            job.get('title', ''),
            job.get('description', job.get('title', ''))
        )
        
        job['match_score'] = score
        job['matched_skills'] = skills
        
        print(f"📊 Match Score: {score}%")
        print(f"🎯 Recommendation: {recommendation}")
        
        # Handle exclusions
        if recommendation == 'exclude':
            print(f"🚫 Excluded: {reason}")
            self.stats['skipped'] += 1
            return
        
        # Handle auto-apply (score >= 70%)
        if recommendation == 'auto_apply':
            print(f"✅ Matched Skills: {', '.join(skills[:5])}")
            
            # Generate cover letter
            self.cover_letter.generate(
                job.get('title', ''),
                job.get('company', ''),
                skills
            )
            
            # Log to Sheet
            self.sheets.log_application(job)
            
            # Apply/Notify
            if auto_apply and job.get('platform') == 'LinkedIn':
                if self.linkedin_scraper and self.linkedin_scraper.auto_apply_to_job(job):
                    self.notifier.notify_application(job)
                    self.stats['applied'] += 1
                else:
                    self.notifier.notify_application(job)
                    self.stats['applied'] += 1
            else:
                self.notifier.notify_application(job)
                self.stats['applied'] += 1
            
            if score >= 85:
                self.notifier.notify_high_match(job)
        
        # Handle review (60-69%)
        elif recommendation == 'review':
            print(f"📝 Queued for manual review")
            if skills:
                print(f"✅ Matched Skills: {', '.join(skills[:5])}")
            
            self.sheets.log_application(job)
            self.stats['skipped'] += 1
        
        else:
            print("⏭️ Score too low - Skipping")
            self.stats['skipped'] += 1
    
    def _print_summary(self):
        """Print run summary."""
        print("\n" + "="*50)
        print("📊 RUN SUMMARY")
        print("="*50)
        print(f"   🔍 Jobs Scanned:  {self.stats['scanned']}")
        print(f"   ✅ Applied:       {self.stats['applied']}")
        print(f"   ⏭️ Skipped:       {self.stats['skipped']}")
        print(f"   ❌ Errors:        {self.stats['errors']}")
        print("="*50 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Job Application Automation')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--naukri', action='store_true', help='Run Naukri web scraping')
    parser.add_argument('--linkedin', action='store_true', help='Run LinkedIn web scraping')
    parser.add_argument('--email', action='store_true', help='Run Naukri Email Parser')
    parser.add_argument('--auto-apply', action='store_true', help='Auto-apply to Easy Apply jobs on LinkedIn')
    parser.add_argument('--max-jobs', type=int, default=10, help='Max jobs per keyword')
    
    args = parser.parse_args()
    
    automation = JobAutomation()
    
    if args.test:
        automation.run_test()
    elif args.naukri:
        automation.run_naukri(max_jobs=args.max_jobs)
    elif args.linkedin:
        automation.run_linkedin(max_jobs=args.max_jobs, auto_apply=args.auto_apply)
    elif args.email:
        automation.run_email_parser()
    else:
        print("ℹ️ Available commands:")
        print("\n   python main.py --test")
        print("   python main.py --linkedin --max-jobs 15")
        print("   python main.py --email")
        print("   python main.py --linkedin --max-jobs 10 --auto-apply")
        print("\nRunning test mode by default...\n")
        automation.run_test()


if __name__ == "__main__":
    main()