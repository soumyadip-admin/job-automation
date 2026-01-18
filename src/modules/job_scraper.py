"""
Job Scraper - Enhanced with Stealth Mode & Anti-Detection
Automates job searching on Naukri/LinkedIn
"""
import os
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# Try to import stealth mode
try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("⚠️ playwright-stealth not installed. Run: pip install playwright-stealth")

load_dotenv()


class JobScraper:
    """Scrapes job listings from job portals using Playwright."""
    
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
        'hybrid'
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
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
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
        """Initialize the browser with maximum stealth."""
        try:
            from playwright.sync_api import sync_playwright
            
            print("   🌐 Starting browser with stealth mode...")
            self.playwright = sync_playwright().start()
            
            # Launch browser with stealth args
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized',
                    '--disable-extensions',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            
            # Create context with realistic fingerprint
            self.context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale='en-IN',
                timezone_id='Asia/Kolkata',
                permissions=['geolocation'],
                geolocation={'latitude': 12.9716, 'longitude': 77.5946},
                extra_http_headers={
                    'Accept-Language': 'en-IN,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            self.page = self.context.new_page()
            
            # Apply stealth mode if available
            if STEALTH_AVAILABLE:
                stealth_sync(self.page)
                print("   🥷 Stealth mode activated")
            
            # Additional anti-detection scripts
            self.page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-IN', 'en-US', 'en']
                });
                
                // Chrome runtime
                window.chrome = {
                    runtime: {}
                };
                
                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            print("✅ Browser started with anti-detection")
            return True
            
        except Exception as e:
            print(f"❌ Browser start failed: {e}")
            return False
    
    def close(self):
        """Clean up browser resources."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("🌐 Browser closed")
        except:
            pass
    
    def login_naukri(self):
        """
        Try to login to Naukri.
        Returns True if login successful OR if we can proceed without login.
        """
        username = os.getenv('NAUKRI_USERNAME')
        password = os.getenv('NAUKRI_PASSWORD')
        
        if not username or not password:
            print("⚠️ Naukri credentials not found - will search without login")
            return True  # Proceed without login
        
        try:
            print("🔐 Attempting Naukri login...")
            
            # Visit homepage first (more natural)
            print("   🏠 Loading homepage...")
            try:
                self.page.goto('https://www.naukri.com/', timeout=60000, wait_until='networkidle')
                self._delay(3, 5)
            except:
                print("   ⚠️ Homepage access blocked - trying direct search...")
                return True  # Proceed to search anyway
            
            # Check if we're blocked
            page_content = self.page.content().lower()
            if 'access denied' in page_content or 'reference #' in page_content:
                print("   ⚠️ Access blocked by firewall - will search without login")
                return True
            
            # Try to find login link
            print("   🔗 Looking for login option...")
            try:
                login_link = self.page.query_selector('a[href*="nlogin"], a:has-text("Login"), .login')
                if login_link and login_link.is_visible():
                    login_link.click()
                    self._delay(3, 5)
                else:
                    # Direct navigation
                    self.page.goto('https://www.naukri.com/nlogin/login', timeout=60000)
                    self._delay(3, 5)
            except:
                print("   ⚠️ Could not access login page - proceeding without login")
                return True
            
            # Check if login page loaded
            page_content = self.page.content().lower()
            if 'access denied' in page_content:
                print("   ⚠️ Login page blocked - will search without login")
                return True
            
            # Find email field
            print("   📧 Entering credentials...")
            email_field = self.page.query_selector('input[type="text"], input[type="email"]')
            password_field = self.page.query_selector('input[type="password"]')
            
            if not email_field or not password_field:
                print("   ⚠️ Login form not found - proceeding without login")
                return True
            
            # Type slowly (human-like)
            for char in username:
                email_field.type(char, delay=random.randint(50, 150))
            self._delay(0.5, 1)
            
            for char in password:
                password_field.type(char, delay=random.randint(50, 150))
            self._delay(1, 2)
            
            # Click login
            login_btn = self.page.query_selector('button[type="submit"], button:has-text("Login")')
            if login_btn:
                login_btn.click()
                self._delay(5, 7)
                
                # Check if login succeeded
                if 'login' not in self.page.url.lower():
                    print("✅ Login successful!")
                    self.logged_in = True
                    return True
            
            print("   ⚠️ Login uncertain - proceeding to search")
            return True
                
        except Exception as e:
            print(f"   ⚠️ Login error: {e}")
            print("   → Proceeding without login")
            return True  # Always proceed, even if login fails
    
    def search_jobs(self, keyword="Data Analyst", max_jobs=10):
        """
        Search for jobs WITHOUT requiring login.
        Works even if Naukri blocks automation.
        """
        jobs = []
        
        try:
            # Build search URL with all filters
            search_term = keyword.lower().replace(' ', '-')
            
            # Multiple locations
            locations = "bangalore%2Ckolkata%2Chyderabad%2Cchennai%2Cpune%2Cdelhi%2Cgurgaon%2Cahmedabad"
            
            # URL with filters: 0-2 years experience, last 7 days, specific locations
            url = f"https://www.naukri.com/{search_term}-jobs?experience=0-2&jobAge=7&location={locations}"
            
            print(f"\n🔍 Searching: {keyword}")
            print(f"   📅 Last 7 days only")
            print(f"   📍 Preferred locations")
            print(f"   💼 0-2 years experience")
            
            # Navigate to search results
            try:
                self.page.goto(url, timeout=60000, wait_until='domcontentloaded')
                self._delay(3, 5)
            except Exception as e:
                print(f"   ❌ Navigation failed: {e}")
                return jobs
            
            # Check if we're blocked
            page_content = self.page.content().lower()
            if 'access denied' in page_content or 'reference #' in page_content:
                print("   ❌ Search page blocked by firewall")
                print("   💡 Suggestion: Set up Naukri email alerts instead")
                return jobs
            
            # Wait for job cards
            try:
                self.page.wait_for_selector('.srp-jobtuple-wrapper, .jobTuple, article', timeout=15000)
            except:
                print("   ❌ No job listings found")
                return jobs
            
            # Get all job cards (try multiple selectors)
            cards = self.page.query_selector_all('.srp-jobtuple-wrapper')
            if not cards:
                cards = self.page.query_selector_all('.jobTuple')
            if not cards:
                cards = self.page.query_selector_all('article')
            
            print(f"   📋 Found {len(cards)} job listings")
            
            if len(cards) == 0:
                print("   ⚠️ No job cards detected - page structure may have changed")
                # Save page for debugging
                try:
                    with open('logs/search_page.html', 'w', encoding='utf-8') as f:
                        f.write(self.page.content())
                    print("   📄 Page saved to logs/search_page.html for debugging")
                except:
                    pass
                return jobs
            
            # Parse each job
            parsed_count = 0
            skipped_location = 0
            
            for card in cards:
                if parsed_count >= max_jobs:
                    break
                
                try:
                    job = self._parse_job_card(card)
                    
                    if job and job.get('title'):
                        # Verify location
                        if self._is_preferred_location(job.get('location', '')):
                            job['platform'] = 'Naukri'
                            job['search_keyword'] = keyword
                            jobs.append(job)
                            parsed_count += 1
                            
                            # Show progress
                            title_short = job['title'][:40]
                            loc_short = job['location'][:20] if job.get('location') else 'N/A'
                            print(f"   ✓ [{parsed_count}] {title_short}... | {loc_short}")
                        else:
                            skipped_location += 1
                except Exception as e:
                    continue
            
            if skipped_location > 0:
                print(f"   ⏭️ Skipped {skipped_location} jobs (location filter)")
            
            print(f"   ✅ Parsed {len(jobs)} matching jobs")
            return jobs
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            return jobs
    
    def _parse_job_card(self, card):
        """Extract job information from a card element."""
        try:
            job = {}
            
            # Title (try multiple selectors)
            title_selectors = ['.title', 'a.title', '.row1 a', 'h2', 'h3', '[class*="title"]']
            for selector in title_selectors:
                elem = card.query_selector(selector)
                if elem and elem.is_visible():
                    job['title'] = elem.inner_text().strip()
                    break
            
            # Company
            company_selectors = ['.comp-name', '.companyInfo a', '.row2 a', '[class*="company"]']
            for selector in company_selectors:
                elem = card.query_selector(selector)
                if elem and elem.is_visible():
                    job['company'] = elem.inner_text().strip()
                    break
            
            # Location
            location_selectors = ['.locWdth', '.loc', '.location', '[class*="location"]']
            for selector in location_selectors:
                elem = card.query_selector(selector)
                if elem and elem.is_visible():
                    job['location'] = elem.inner_text().strip()
                    break
            
            # Experience
            exp_selectors = ['.expwdth', '.exp', '.experience', '[class*="experience"]']
            for selector in exp_selectors:
                elem = card.query_selector(selector)
                if elem and elem.is_visible():
                    job['experience'] = elem.inner_text().strip()
                    break
            
            # Salary
            salary_selectors = ['.sal-wrap span', '.sal', '.salary', '[class*="salary"]']
            for selector in salary_selectors:
                elem = card.query_selector(selector)
                if elem and elem.is_visible():
                    job['salary'] = elem.inner_text().strip()
                    break
            if 'salary' not in job:
                job['salary'] = 'Not disclosed'
            
            # Job URL
            link_selectors = ['a.title', '.row1 a', 'a[href*="job-listings"]', 'a[href*="jd"]']
            for selector in link_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['url'] = elem.get_attribute('href') or ""
                    break
            
            # Description snippet
            desc_selectors = ['.job-desc', '.desc', '[class*="description"]']
            for selector in desc_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['description'] = elem.inner_text().strip()
                    break
            
            # Posted date
            date_selectors = ['.job-post-day', '.date', '[class*="posted"]']
            for selector in date_selectors:
                elem = card.query_selector(selector)
                if elem:
                    job['posted_date'] = elem.inner_text().strip()
                    break
            
            job['scraped_at'] = datetime.now().isoformat()
            
            return job if job.get('title') else None
            
        except Exception as e:
            return None
    
    def update_profile(self):
        """Update Naukri profile to stay active."""
        if not self.logged_in:
            print("   ⚠️ Not logged in - skipping profile update")
            return False
        
        try:
            print("📝 Updating profile...")
            self.page.goto('https://www.naukri.com/mnjuser/profile', timeout=60000)
            self._delay(2, 4)
            print("   ✅ Profile accessed")
            return True
        except:
            return False


# Test the scraper
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING JOB SCRAPER")
    print("=" * 60)
    print("\n📍 Locations: Bangalore, Kolkata, Hyderabad, Chennai, etc.")
    print("📅 Date: Last 7 days")
    print("💼 Experience: 0-2 years\n")
    
    scraper = JobScraper(headless=False)  # Visible browser for testing
    
    try:
        if scraper.start_browser():
            # Try login (will proceed even if it fails)
            scraper.login_naukri()
            
            # Search jobs
            jobs = scraper.search_jobs("Data Analyst", max_jobs=5)
            
            # Display results
            print(f"\n{'=' * 60}")
            print(f"📊 RESULTS: Found {len(jobs)} matching jobs")
            print(f"{'=' * 60}\n")
            
            for i, job in enumerate(jobs, 1):
                print(f"{'─' * 50}")
                print(f"Job #{i}")
                print(f"📋 Title:    {job.get('title', 'N/A')}")
                print(f"🏢 Company:  {job.get('company', 'N/A')}")
                print(f"📍 Location: {job.get('location', 'N/A')}")
                print(f"💼 Exp:      {job.get('experience', 'N/A')}")
                print(f"💰 Salary:   {job.get('salary', 'N/A')}")
                if job.get('posted_date'):
                    print(f"📅 Posted:   {job['posted_date']}")
                if job.get('url'):
                    print(f"🔗 URL:      {job['url'][:60]}...")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        input("\n\nPress Enter to close browser...")
        scraper.close()