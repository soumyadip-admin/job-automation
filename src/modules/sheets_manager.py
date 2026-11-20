"""Google Sheets manager for safe job discovery records.

Rows use the 11-column schema consumed by Sam Career Studio:
ID, tracker timestamp, portal, title, company, URL, location, salary,
match score, tracker status, tags.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

class SheetsManager:
    """Write duplicate-safe discovery records to the authorized tracker."""

    def __init__(self):
        self.spreadsheet_id = (os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or "").strip()
        self.client = None
        self.spreadsheet = None
        self._connected = False
        self._known_urls: set[str] | None = None
        print(f"[DEBUG] Spreadsheet ID configured: {bool(self.spreadsheet_id)}")

    @staticmethod
    def canonical_url(value: str) -> str:
        try:
            parts = urlsplit(str(value or "").strip())
            host = parts.netloc.lower()
            if parts.scheme not in {"http", "https"}:
                return ""
            job_id = re.search(r"(?:-|/)(\d+)(?:/)?$", parts.path)
            if "linkedin.com" in host and job_id:
                return f"https://www.linkedin.com/jobs/view/{job_id.group(1)}"
            identity_keys = {"id", "jobid", "job_id", "jrid", "reqid", "requisitionid", "folderid"}
            query = [
                (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=False)
                if key.lower() in identity_keys and val
            ]
            return urlunsplit((parts.scheme, host, parts.path.rstrip("/"), urlencode(sorted(query)), ""))
        except ValueError:
            return ""

    def connect(self):
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            if not self.spreadsheet_id:
                print("❌ GOOGLE_SHEETS_SPREADSHEET_ID is missing")
                return False
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
            credentials = None
            if creds_json:
                try:
                    payload = creds_json.strip()
                    if not payload.startswith("{"):
                        payload = base64.b64decode(payload).decode("utf-8")
                    credentials = Credentials.from_service_account_info(json.loads(payload), scopes=scopes)
                except Exception as exc:
                    print(f"❌ GOOGLE_SHEETS_CREDENTIALS_JSON is invalid: {type(exc).__name__}: {exc}")
                    return False
            else:
                path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "config/credentials.json")
                if os.path.exists(path):
                    credentials = Credentials.from_service_account_file(path, scopes=scopes)
            if credentials is None:
                print("❌ No Google Sheets service-account credentials found")
                return False

            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self._connected = True
            print(f"✅ Connected to Google Sheet: {self.spreadsheet.title}")
            return True
        except Exception as exc:
            print(f"❌ Google Sheets connection failed: {type(exc).__name__}: {exc}")
            self._connected = False
            return False

    def get_sheet(self, sheet_name="Job_Applications"):
        if not self._connected:
            return None
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except Exception as exc:
            print(f"❌ Required sheet '{sheet_name}' is unavailable: {exc}")
            return None

    def _load_known_urls(self) -> set[str]:
        if self._known_urls is not None:
            return self._known_urls
        sheet = self.get_sheet()
        if sheet is None:
            self._known_urls = set()
            return self._known_urls
        values = sheet.col_values(6)
        self._known_urls = {url for value in values if (url := self.canonical_url(value))}
        print(f"✅ Loaded {len(self._known_urls)} canonical tracker URLs for deduplication")
        return self._known_urls

    def check_already_applied(self, job_url):
        """Compatibility name: check whether the vacancy is already tracked."""
        canonical = self.canonical_url(job_url)
        return bool(canonical and canonical in self._load_known_urls())

    def log_candidate(self, job_data, status="Discovered") -> bool:
        if not self._connected:
            print("❌ Candidate not saved because Sheets is disconnected")
            return False
        sheet = self.get_sheet()
        if sheet is None:
            return False
        canonical = self.canonical_url(job_data.get("url", ""))
        if not canonical:
            print("⚠️ Candidate skipped because its source URL is invalid")
            return False
        if canonical in self._load_known_urls():
            print("⏭️ Vacancy already exists in the tracker")
            return False

        observed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
        identifier = "JOB_" + hashlib.sha1(canonical.encode()).hexdigest()[:16].upper()
        tags = list(job_data.get("matched_skills") or [])
        if job_data.get("posted_date"):
            tags.append(f"source_posted={job_data['posted_date']}")
        if job_data.get("source_observed_at"):
            tags.append(f"source_observed={job_data['source_observed_at']}")
        if job_data.get("source_message_url"):
            tags.append(f"source_message={job_data['source_message_url']}")
        if job_data.get("link_verified") is True:
            tags.append("external_link_verified")
        elif job_data.get("link_verified") == "browser_protected":
            tags.append("official_link_browser_protected")
        tags.append("discovery_only")
        row = [
            identifier,
            observed,
            str(job_data.get("platform", "")),
            str(job_data.get("title", "")),
            str(job_data.get("company", "")),
            canonical,
            str(job_data.get("location", "")),
            str(job_data.get("salary", "")),
            str(job_data.get("match_score", 0)),
            status,
            ", ".join(tags),
        ]
        try:
            sheet.append_row(row, value_input_option="RAW")
            self._known_urls.add(canonical)
            print(f"✅ [SHEET SAVED · {status}] {job_data.get('title')} at {job_data.get('company')}")
            return True
        except Exception as exc:
            print(f"❌ Failed to save candidate: {type(exc).__name__}: {exc}")
            return False

    def log_application(self, job_data):
        """Backward-compatible wrapper; discovery is never mislabeled as an application."""
        return self.log_candidate(job_data, status=job_data.get("tracker_status", "Discovered"))
