#!/usr/bin/env python3
"""Sam Career discovery runner.

Collects public job cards, evaluates them conservatively, and saves new candidates
as Discovered or Review. It never logs in to LinkedIn or submits applications.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.modules.email_parser import EmailParser
from src.modules.linkedin_scraper import LinkedInScraper
from src.modules.matcher import JobMatcher
from src.modules.sheets_manager import SheetsManager
from src.modules.telegram_notifier import TelegramNotifier
from src.modules.telegram_source import TelegramBotInbox, TelegramJobSource


class JobAutomation:
    def __init__(self):
        print("🚀 Initializing Sam Career job discovery...")
        with open("config/config.json", encoding="utf-8") as handle:
            self.config = json.load(handle)

        self.sheets = SheetsManager()
        self.matcher = JobMatcher()
        self.linkedin = LinkedInScraper(headless=True)
        self.email_parser = EmailParser()
        self.telegram_source = TelegramJobSource(self.config.get("telegram_channels", []))
        self.telegram_inbox = TelegramBotInbox(
            os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", ""), self.telegram_source
        )
        self.notifier = TelegramNotifier()
        self.stats = {"scanned": 0, "saved": 0, "review": 0, "skipped": 0, "duplicates": 0, "errors": 0}
        self.failures: list[str] = []
        self.new_jobs: list[dict] = []

        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(self.log_dir / "automation.log"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def _fail(self, message: str):
        self.failures.append(message)
        self.stats["errors"] += 1
        self.logger.error(message)

    def initialize(self):
        """Require a verified Sheet connection before any collection begins."""
        if not self.sheets.connect():
            self._fail("Required Google Sheets connection failed")
            return False
        if self.sheets.get_sheet("Job_Applications") is None:
            self._fail("Required Job_Applications worksheet is unavailable")
            return False
        try:
            username = self.notifier.validate()
            print(f"✅ Telegram bot identity verified: @{username}")
        except Exception as exc:
            self._fail(f"Required Telegram bot validation failed: {type(exc).__name__}: {exc}")
            return False
        if not self.linkedin.start_browser():
            self._fail("Public LinkedIn discovery session failed to start")
            return False
        self.linkedin.login()  # compatibility call; it performs no account login
        return True

    def process_job(self, job):
        self.stats["scanned"] += 1
        url = job.get("url", "")
        if not url:
            self.stats["skipped"] += 1
            return
        try:
            if self.sheets.check_already_applied(url):
                self.stats["duplicates"] += 1
                return
            score, skills, recommendation, reason = self.matcher.calculate_score(
                job.get("title", ""), job.get("description", "")
            )
            job["match_score"] = score
            job["matched_skills"] = skills
            if recommendation in {"skip", "exclude"}:
                self.stats["skipped"] += 1
                self.logger.info("Skipped %s: %s", job.get("title"), reason or f"score={score}")
                return
            status = "Review" if recommendation == "review" else "Discovered"
            job["tracker_status"] = status
            if self.sheets.log_candidate(job, status=status):
                self.stats["saved"] += 1
                self.new_jobs.append(dict(job))
                if status == "Review":
                    self.stats["review"] += 1
            else:
                self._fail(f"Failed to save candidate: {job.get('title')} at {job.get('company')}")
        except Exception as exc:
            self._fail(f"Job processing failed for {job.get('title')}: {type(exc).__name__}: {exc}")

    def run_telegram_public(self):
        print("\n" + "=" * 60)
        print("📣 PUBLIC TELEGRAM DISCOVERY · PAST 24 HOURS")
        print("=" * 60)
        jobs = self.telegram_source.collect_public(max_age_hours=24, max_jobs=60)
        for job in jobs:
            self.process_job(job)
        for error in self.telegram_source.errors:
            self.logger.warning(error)
        if self.telegram_source.successful_channels == 0:
            self._fail("Every configured public Telegram channel failed to load")
        print(
            f"✅ Telegram channels reached: {self.telegram_source.successful_channels}; "
            f"recent posts scanned: {self.telegram_source.scanned_posts}; candidates: {len(jobs)}"
        )

    def run_telegram_inbox(self):
        print("\n" + "=" * 60)
        print("📨 PRIVATE TELEGRAM FORWARDING INBOX")
        print("=" * 60)
        before_failures = len(self.failures)
        try:
            jobs = self.telegram_inbox.collect_forwarded()
            for job in jobs:
                self.process_job(job)
            if len(self.failures) == before_failures:
                self.telegram_inbox.acknowledge()
            else:
                self.logger.warning("Telegram inbox updates left pending because processing failed")
            print(f"✅ Forwarded candidates received: {len(jobs)}")
        except Exception as exc:
            self._fail(f"Telegram forwarding inbox failed: {type(exc).__name__}: {exc}")

    def run_linkedin_search(self):
        print("\n" + "=" * 60)
        print("🔍 PUBLIC LINKEDIN DISCOVERY · PAST 24 HOURS")
        print("=" * 60)
        roles = self.config.get("search_queries") or self.config.get("target_roles", ["Data Analyst"])
        per_role = max(5, int(os.getenv("MAX_JOBS_PER_ROLE", "25")))
        collected = 0
        for role in roles:
            jobs = self.linkedin.search_jobs(keyword=role, max_jobs=per_role)
            collected += len(jobs)
            for job in jobs:
                self.process_job(job)
        for error in self.linkedin.errors:
            self.logger.warning(error)
        if collected == 0:
            self._fail("LinkedIn public discovery returned no jobs; source access or parsing may be broken")

    def run_email_search(self):
        print("\n" + "=" * 60)
        print("📧 TRUSTED NAUKRI EMAIL DISCOVERY · PAST 24 HOURS")
        print("=" * 60)
        try:
            jobs = self.email_parser.get_all_jobs(days_back=1, max_emails=30)
            for job in jobs:
                self.process_job(job)
            if self.email_parser.errors:
                for error in self.email_parser.errors:
                    self._fail(error)
        except Exception as exc:
            self._fail(f"Naukri email discovery failed: {type(exc).__name__}: {exc}")

    def send_telegram_summary(self):
        try:
            self.notifier.send_summary(self.stats, self.new_jobs, self.failures)
            print("✅ Truthful hourly Telegram summary sent")
        except Exception as exc:
            self._fail(f"Telegram summary failed: {type(exc).__name__}: {exc}")

    def cleanup(self):
        self.linkedin.close()

    def print_summary(self):
        print("\n" + "=" * 60)
        print("📊 DISCOVERY SUMMARY")
        print("=" * 60)
        for key, value in self.stats.items():
            print(f"{key.title():18} {value}")
        print("ℹ️ No external applications were submitted.")

    def run(self):
        try:
            if not self.initialize():
                return 1
            self.run_telegram_public()
            self.run_linkedin_search()
            self.run_email_search()
            self.run_telegram_inbox()
            self.print_summary()
            self.send_telegram_summary()
            return 1 if self.failures else 0
        except Exception as exc:
            self._fail(f"Fatal automation failure: {type(exc).__name__}: {exc}")
            return 1
        finally:
            self.cleanup()


def main():
    print(f"\n🤖 SAM CAREER DISCOVERY · {datetime.now():%Y-%m-%d %H:%M:%S}")
    raise SystemExit(JobAutomation().run())


if __name__ == "__main__":
    main()
