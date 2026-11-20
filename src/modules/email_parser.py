"""Read recent Naukri job-alert emails and extract concrete vacancy links.

Email receipt time is kept as source-observation metadata; it is never represented
as the vacancy publication date. Placeholder jobs are deliberately not created.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup


class EmailParser:
    TRUSTED_SENDER = "naukri.com"
    TITLE_TERMS = re.compile(r"\b(analyst|analytics|business intelligence|power bi|mis|reporting|workforce|wfm)\b", re.I)

    def __init__(self):
        self.gmail_user = (os.getenv("GMAIL_ADDRESS") or "").strip()
        self.gmail_app_password = (os.getenv("GMAIL_APP_PASSWORD") or "").strip()
        self.enabled = bool(self.gmail_user and self.gmail_app_password)
        self.mail = None
        self.errors: list[str] = []

    @staticmethod
    def _decode_header(value: str) -> str:
        parts = []
        for payload, charset in decode_header(value or ""):
            if isinstance(payload, bytes):
                parts.append(payload.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(payload)
        return " ".join(parts).strip()

    @staticmethod
    def _canonical_url(value: str) -> str:
        try:
            parts = urlsplit(value.strip())
            if parts.scheme not in {"http", "https"} or "naukri.com" not in parts.netloc.lower():
                return ""
            return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
        except (TypeError, ValueError):
            return ""

    def connect(self) -> bool:
        if not self.enabled:
            self.errors.append("Gmail credentials are not configured")
            return False
        try:
            self.mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            self.mail.login(self.gmail_user, self.gmail_app_password)
            status, _ = self.mail.select("inbox", readonly=True)
            if status != "OK":
                raise RuntimeError("could not open inbox read-only")
            print("✅ Connected to Gmail in read-only mode")
            return True
        except Exception as exc:
            self.errors.append(f"Gmail connection failed: {type(exc).__name__}: {exc}")
            return False

    def disconnect(self):
        if not self.mail:
            return
        try:
            self.mail.close()
            self.mail.logout()
        except Exception as exc:
            print(f"⚠️ Gmail disconnect warning: {exc}")
        finally:
            self.mail = None

    def search_naukri_emails(self, days_back=1, max_emails=30):
        since = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        status, data = self.mail.search(None, f'(FROM "{self.TRUSTED_SENDER}" SINCE {since})')
        if status != "OK":
            raise RuntimeError("Gmail search did not return OK")
        return (data[0].split() if data and data[0] else [])[-max_emails:]

    @staticmethod
    def _body(message) -> str:
        candidates = []
        for part in message.walk() if message.is_multipart() else [message]:
            if part.get_content_type() not in {"text/html", "text/plain"}:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            candidates.append((part.get_content_type() == "text/html", text))
        html_parts = [text for is_html, text in candidates if is_html]
        return html_parts[0] if html_parts else (candidates[0][1] if candidates else "")

    def parse_email(self, email_id):
        status, data = self.mail.fetch(email_id, "(RFC822)")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            raise RuntimeError(f"could not fetch email {email_id!r}")
        message = email.message_from_bytes(data[0][1])
        sender = self._decode_header(message.get("From", ""))
        if self.TRUSTED_SENDER not in sender.lower():
            return []
        subject = self._decode_header(message.get("Subject", ""))
        try:
            observed = parsedate_to_datetime(message.get("Date", "")).astimezone(timezone.utc).isoformat()
        except Exception:
            observed = datetime.now(timezone.utc).isoformat()

        soup = BeautifulSoup(self._body(message), "html.parser")
        jobs, seen = [], set()
        for anchor in soup.find_all("a", href=True):
            url = self._canonical_url(anchor.get("href", ""))
            title = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
            if not url or url in seen or len(title) < 4 or not self.TITLE_TERMS.search(title):
                continue
            path = urlsplit(url).path.lower()
            if "job-listings" not in path and not re.search(r"/(?:job|jd)/", path):
                continue
            seen.add(url)
            context = re.sub(r"\s+", " ", anchor.parent.get_text(" ", strip=True))[:500]
            location_match = re.search(
                r"\b(Kolkata|Bengaluru|Bangalore|Hyderabad|Pune|Noida|Gurugram|Gurgaon|Chennai|Mumbai|Remote)\b",
                context, re.I,
            )
            jobs.append({
                "title": title,
                "company": "See Naukri listing",
                "location": location_match.group(1) if location_match else "India",
                "url": url,
                "platform": "Naukri",
                "salary": "Not disclosed",
                "description": context,
                "posted_date": "",
                "source": "trusted_email_alert",
                "source_observed_at": observed,
                "email_subject": subject,
            })
        return jobs

    def get_all_jobs(self, days_back=1, max_emails=30):
        if not self.connect():
            raise RuntimeError(self.errors[-1])
        jobs, seen = [], set()
        try:
            email_ids = self.search_naukri_emails(days_back=days_back, max_emails=max_emails)
            print(f"📧 Found {len(email_ids)} recent Naukri alert emails")
            for email_id in email_ids:
                try:
                    for job in self.parse_email(email_id):
                        if job["url"] not in seen:
                            seen.add(job["url"])
                            jobs.append(job)
                except Exception as exc:
                    message = f"Email parsing failed: {type(exc).__name__}: {exc}"
                    self.errors.append(message)
                    print(f"⚠️ {message}")
            print(f"✅ Extracted {len(jobs)} concrete, canonical Naukri vacancies")
            return jobs
        finally:
            self.disconnect()
