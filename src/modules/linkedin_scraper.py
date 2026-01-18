"""
LinkedIn Job Scraper
Searches and optionally applies to jobs on LinkedIn
"""
import os
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# Try stealth mode
try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

load_dotenv()


class LinkedInScraper:
    """Scrapes job listings from LinkedIn."""
    
    # Preferred locations
    PREFERRED_LOCATIONS = [
        'bangalore', 'bengaluru',
        'kolkata', 'calcutta',
        'hyderabad',
        'chennai',
        'odisha', 'bhubaneswar', 'cuttack',
        'remote', 'work from home', 'wfh',
        'delhi', 'new delhi',
        'gurgaon', 'gurugram',
        'ahmedabad',
        'pune',
        'noida',
        'hybrid',
        'india'
    ]
    
    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None
        self.context = None
        self.logged_in = False
    
    def _delay(self, min_sec=1, max_sec=3):
        """Random delay to appear human-like."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def _is_preferred_location(self, location):
        """Check if job location is in preferred list."""
        if not location:
            return True
        
        location_lower = location.lower()
        
        for preferred in self.PREFERRED_LOCATIONS:
            if preferred in location_lower:
                return True
        
        return False
    
    def start_browser(self):
        """Initialize browser with stealth mode."""
        try:
            from playwright.sync_api import sync_playwright
            
            print("   🌐 Starting LinkedIn browser...")
            self.playwright = sync_playwright().start()
            
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            self.context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale='en-IN',
                timezone_id='Asia/Kolkata'
            )
            
            self.page = self.context.new_page()
            
            # Apply stealth
            if STEALTH_AVAILABLE:
                stealth_sync(self.page)
                print("   🥷 Stealth mode activated")
            
            # Anti-detection scripts
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)
            
            print("✅ LinkedIn browser started")
            return True
            
        except Exception as e:
            print(f"❌ Browser start failed: {e}")
            return False
    
    def close(self):
        """Clean up browser."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("🌐 LinkedIn browser closed")
        except:
            pass
    
    def login(self):
        """Login to LinkedIn."""
        username = os.getenv('LINKEDIN_USERNAME')
        password = os.getenv('LINKEDIN_PASSWORD')
        
        if not username or not password:
            print("⚠️ LinkedIn credentials not found")
            return False
        
        try:
            print("🔐 Logging into LinkedIn...")
            
            # Go to LinkedIn
            print("   🏠 Loading LinkedIn...")
            self.page.goto('https://www.linkedin.com/', timeout=60000)
            self._delay(2, 4)
            
            # Check if already logged in
            if 'feed' in self.page.url:
                print("✅ Already logged in!")
                self.logged_in = True
                return True
            
            # Go to login page
            print("   🔓 Navigating to login...")
            self.page.goto('https://www.linkedin.com/login', timeout=60000)
            self._delay(2, 4)
            
            # Screenshot for debugging
            try:
                self.page.screenshot(path="logs/linkedin_login.png")
            except:
                pass
            
            # Find and fill email
            print("   📧 Entering email...")
            email_field = self.page.query_selector('input#username, input[name="session_key"]')
            if email_field:
                for char in username:
                    email_field.type(char, delay=random.randint(30, 100))
                self._delay(0.5, 1)
            else:
                print("   ❌ Email field not found")
                return False
            
            # Find and fill password
            print("   🔑 Entering password...")
            password_field = self.page.query_selector('input#password, input[name="session_password"]')
            if password_field:
                for char in password:
                    password_field.type(char, delay=random.randint(30, 100))
                self._delay(0.5, 1)
            else:
                print("   ❌ Password field not found")
                return False
            
            # Click sign in
            print("   🖱️ Clicking sign in...")
            signin_btn = self.page.query_selector('button[type="submit"], button:has-text("Sign in")')
            if signin_btn:
                signin_btn.click()
                self._delay(5, 8)
            
            # Check for security verification
            current_url = self.page.url.lower()
            if 'checkpoint' in current_url or 'challenge' in current_url:
                print("   ⚠️ LinkedIn security check detected!")
                print("   💡 Please complete verification manually in the browser")
                print("   ⏳ Waiting 60 seconds for manual verification...")
                self._delay(55, 65)
            
            # Check login success
            current_url = self.page.url.lower()
            if 'feed' in current_url or 'mynetwork' in current_url:
                print("✅ LinkedIn login successful!")
                self.logged_in = True
                return True
            
            if 'login' not in current_url:
                print("✅ LinkedIn login appears successful")
                self.logged_in = True
                return True
            
            print("❌ LinkedIn login failed")
            try:
                self.page.screenshot(path="logs/linkedin_login_failed.png")
            except:
                pass
            return False
            
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def search_jobs(self, keyword="Data Analyst", max_jobs=10):
        """Search for jobs on LinkedIn."""
        jobs = []
        
        try:
            search_keyword = keyword.replace(' ', '%20')
            
            # LinkedIn Jobs URL with filters
            # f_TPR=r604800 = past week (7 days)
            # f_E=2 = Entry level
            url = f"https://www.linkedin.com/jobs/search/?keywords={search_keyword}&location=India&f_TPR=r604800&f_E=2&sortBy=DD"
            
            print(f"\n🔍 Searching LinkedIn: {keyword}")
            print(f"   📅 Last 7 days")
            print(f"   💼 Entry level")
            print(f"   📍 India")
            
            self.page.goto(url, timeout=60000, wait_until='domcontentloaded')
            self._delay(3, 5)
            
            # Check if login required
            page_content = self.page.content().lower()
            if 'sign in' in page_content and 'join now' in page_content and len(page_content) < 10000:
                print("   ⚠️ LinkedIn requires login")
                
                if not self.logged_in:
                    if self.login():
                        self.page.goto(url, timeout=60000, wait_until='domcontentloaded')
                        self._delay(3, 5)
                    else:
                        return jobs
            
            # Scroll to load more jobs
            print("   📜 Loading job listings...")
            for i in range(3):
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._delay(1, 2)
            
            # Find job cards
            job_selectors = [
                '.jobs-search-results__list-item',
                '.job-card-container',
                '.jobs-search__results-list li',
                'li[data-occludable-job-id]',
                '.base-card',
                '.base-search-card'
            ]
            
            cards = []
            for selector in job_selectors:
                cards = self.page.query_selector_all(selector)
                if cards and len(cards) > 0:
                    print(f"   📋 Found {len(cards)} jobs")
                    break
            
            if not cards:
                print("   ❌ No job cards found")
                try:
                    with open('logs/linkedin_search.html', 'w', encoding='utf-8') as f:
                        f.write(self.page.content())
                    self.page.screenshot(path='logs/linkedin_search.png')
                    print("   📄 Debug files saved to logs/")
                except:
                    pass
                return jobs
            
            # Parse each job
            parsed_count = 0
            
            for card in cards:
                if parsed_count >= max_jobs:
                    break
                
                try:
                    job = self._parse_job_card(card)
                    
                    if job and job.get('title'):
                        if self._is_preferred_location(job.get('location', '')):
                            job['platform'] = 'LinkedIn'
                            job['search_keyword'] = keyword
                            jobs.append(job)
                            parsed_count += 1
                            
                            title_short = job['title'][:35]
                            company_short = job.get('company', 'N/A')[:20]
                            print(f"   ✓ [{parsed_count}] {title_short}... @ {company_short}")
                        
                except:
                    continue
            
            print(f"   ✅ Parsed {len(jobs)} matching jobs")
            return jobs
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            return jobs
    
    def _parse_job_card(self, card):
        """Extract job info from LinkedIn card."""
        try:
            job = {}
            
            # Title
            title_selectors = [
                '.base-search-card__title',
                '.job-card-list__title',
                'h3',
                'a[data-tracking-control-name*="title"]'
            ]
            for selector in title_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['title'] = elem.inner_text().strip()
                    break
            
            # Company
            company_selectors = [
                '.base-search-card__subtitle',
                '.job-card-container__company-name',
                'h4',
                'a[data-tracking-control-name*="company"]'
            ]
            for selector in company_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['company'] = elem.inner_text().strip()
                    break
            
            # Location
            location_selectors = [
                '.job-card-container__metadata-item',
                '.base-search-card__metadata span',
                '.job-search-card__location'
            ]
            for selector in location_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['location'] = elem.inner_text().strip()
                    break
            
            # Posted date
            date_selectors = [
                '.job-card-container__listed-time',
                'time',
                '.base-search-card__metadata time'
            ]
            for selector in date_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['posted_date'] = elem.inner_text().strip()
                    break
            
            # Job URL
            link_selectors = [
                'a.base-card__full-link',
                'a[data-tracking-control-name*="job"]',
                'a[href*="/jobs/view/"]'
            ]
            for selector in link_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['url'] = elem.get_attribute('href') or ""
                    break
            
            # Easy Apply
            easy_apply = card.query_selector('.job-card-container__apply-method')
            job['easy_apply'] = easy_apply is not None
            
            job['salary'] = 'Not disclosed'
            job['experience'] = 'Entry Level'
            job['scraped_at'] = datetime.now().isoformat()
            
            return job if job.get('title') else None
            
        except:
            return None
    
    def easy_apply(self, job_url):
        """Apply to a job using Easy Apply."""
        try:
            print(f"   🔄 Attempting Easy Apply...")
            
            self.page.goto(job_url, timeout=60000)
            self._delay(2, 4)
            
            easy_apply_btn = self.page.query_selector('button:has-text("Easy Apply")')
            
            if not easy_apply_btn:
                print("   ⚠️ Easy Apply not available")
                return False
            
            easy_apply_btn.click()
            self._delay(2, 3)
            
            # Handle application steps
            for step in range(5):
                submit_btn = self.page.query_selector('button:has-text("Submit application")')
                if submit_btn:
                    submit_btn.click()
                    self._delay(2, 3)
                    print("   ✅ Application submitted!")
                    return True
                
                next_btn = self.page.query_selector('button:has-text("Next"), button:has-text("Continue")')
                if next_btn:
                    next_btn.click()
                    self._delay(1, 2)
                    continue
                
                review_btn = self.page.query_selector('button:has-text("Review")')
                if review_btn:
                    review_btn.click()
                    self._delay(1, 2)
                    continue
                
                self._delay(1, 2)
            
            print("   ⚠️ Could not complete Easy Apply")
            return False
            
        except Exception as e:
            print(f"   ❌ Easy Apply error: {e}")
            return False


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING LINKEDIN SCRAPER")
    print("=" * 60)
    
    scraper = LinkedInScraper(headless=False)
    
    try:
        if scraper.start_browser():
            scraper.login()
            jobs = scraper.search_jobs("Data Analyst", max_jobs=5)
            
            print(f"\n{'=' * 60}")
            print(f"📊 FOUND {len(jobs)} JOBS")
            print(f"{'=' * 60}\n")
            
            for i, job in enumerate(jobs, 1):
                print(f"{'─' * 50}")
                print(f"Job #{i}")
                print(f"📋 {job.get('title', 'N/A')}")
                print(f"🏢 {job.get('company', 'N/A')}")
                print(f"📍 {job.get('location', 'N/A')}")
                print(f"⚡ Easy Apply: {'Yes' if job.get('easy_apply') else 'No'}")
    
    finally:
        input("\n\nPress Enter to close...")
        scraper.close()