"""Policy-aware LinkedIn public job discovery.

This module reads LinkedIn's public guest job-result endpoint. It does not log in,
bypass challenges, imitate a user, or submit applications. Application decisions
remain with the user in Sam Career Studio.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


class LinkedInScraper:
    """Collect current public LinkedIn job cards without account automation."""

    LOCATIONS = ("Kolkata", "Bengaluru", "Hyderabad", "Remote", "India")
    ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    USER_AGENT = "SamCareerDiscovery/2.0 (+personal job research)"

    def __init__(self, headless=True):
        self.headless = headless  # retained for compatibility with the old caller
        self.session: requests.Session | None = None
        self.logged_in = False
        self.errors: list[str] = []

    @staticmethod
    def _clean(value) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _canonical_url(value: str) -> str:
        try:
            parts = urlsplit(value.strip())
            host = parts.netloc.lower()
            if parts.scheme not in {"http", "https"}:
                return ""
            job_id = re.search(r"(?:-|/)(\d+)(?:/)?$", parts.path)
            if "linkedin.com" in host and job_id:
                return f"https://www.linkedin.com/jobs/view/{job_id.group(1)}"
            return urlunsplit((parts.scheme, host, parts.path.rstrip("/"), "", ""))
        except (TypeError, ValueError):
            return ""

    def start_browser(self):
        """Create an HTTP session; no browser or portal login is used."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept-Language": "en-IN,en;q=0.9",
        })
        print("✅ Public LinkedIn discovery session started (no login, no auto-apply)")
        return True

    def login(self):
        """Compatibility method: authenticated automation is intentionally disabled."""
        print("ℹ️ LinkedIn account login is disabled; using public job results only")
        return True

    def close(self):
        if self.session:
            self.session.close()
        print("🌐 Public LinkedIn discovery session closed")

    def search_jobs(self, keyword="Data Analyst", max_jobs=10):
        """Return canonical, source-dated public cards posted in the past 24 hours."""
        if not self.session:
            self.start_browser()
        jobs: list[dict] = []
        seen: set[str] = set()
        print(f"\n🔍 Public LinkedIn search: {keyword} · past 24 hours")

        per_location = max(2, (max_jobs + len(self.LOCATIONS) - 1) // len(self.LOCATIONS))
        for location in self.LOCATIONS:
            if len(jobs) >= max_jobs:
                break
            location_added = 0
            try:
                response = self.session.get(
                    self.ENDPOINT,
                    params={
                        "keywords": keyword,
                        "location": location,
                        "f_TPR": "r86400",
                        "start": 0,
                    },
                    timeout=30,
                )
                if response.status_code == 429:
                    message = f"LinkedIn/{keyword}/{location}: rate limited"
                    self.errors.append(message)
                    print(f"⚠️ {message}; moving to the next query")
                    time.sleep(4)
                    continue
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for card in soup.select("div.base-card"):
                    title_el = card.select_one(".base-search-card__title")
                    company_el = card.select_one(".base-search-card__subtitle")
                    location_el = card.select_one(".job-search-card__location")
                    link_el = card.select_one("a.base-card__full-link")
                    time_el = card.select_one("time")
                    if not title_el or not link_el:
                        continue
                    url = self._canonical_url(link_el.get("href") or "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    job_location = self._clean(location_el.get_text()) if location_el else location
                    jobs.append({
                        "title": self._clean(title_el.get_text()),
                        "company": self._clean(company_el.get_text()) if company_el else "",
                        "location": job_location,
                        "url": url,
                        "platform": "LinkedIn",
                        "salary": "Not disclosed",
                        "description": "",
                        "posted_date": time_el.get("datetime") if time_el else "",
                        "source": "public_guest_result",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    })
                    location_added += 1
                    if len(jobs) >= max_jobs or location_added >= per_location:
                        break
                time.sleep(1.4)
            except Exception as exc:
                message = f"LinkedIn/{keyword}/{location}: {type(exc).__name__}: {str(exc)[:120]}"
                self.errors.append(message)
                print(f"⚠️ {message}")

        print(f"✅ Collected {len(jobs)} canonical public jobs for {keyword}")
        return jobs
