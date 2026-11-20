"""Truthful Telegram summaries for SAM Career discovery runs."""
from __future__ import annotations

import html
import os

import requests


class TelegramNotifier:
    def __init__(self):
        self.token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        self.expected_username = (os.getenv("TELEGRAM_BOT_USERNAME") or "").strip().lstrip("@")
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    @property
    def configured(self):
        return bool(self.token and self.chat_id)

    def validate(self):
        if not self.configured:
            raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")
        response = requests.get(f"{self.base}/getMe", timeout=15)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram getMe failed"))
        username = str((payload.get("result") or {}).get("username", ""))
        if self.expected_username and username.lower() != self.expected_username.lower():
            raise RuntimeError(f"Telegram token belongs to @{username}, not @{self.expected_username}")
        return username

    def send_summary(self, stats, new_jobs, failures=()):
        self.validate()
        lines = [
            "<b>SAM Career hourly update</b>",
            "",
            f"Sources scanned: <b>{int(stats.get('scanned', 0))}</b> jobs",
            f"New matches saved: <b>{int(stats.get('saved', 0))}</b>",
            f"For review: <b>{int(stats.get('review', 0))}</b>",
            f"Duplicates ignored: <b>{int(stats.get('duplicates', 0))}</b>",
            f"Excluded/skipped: <b>{int(stats.get('skipped', 0))}</b>",
            f"Errors: <b>{int(stats.get('errors', 0))}</b>",
        ]
        if new_jobs:
            lines.extend(["", "<b>New matching jobs</b>"])
            for job in new_jobs[:8]:
                title = html.escape(str(job.get("title") or "Job"))
                company = html.escape(str(job.get("company") or "Company not supplied"))
                url = html.escape(str(job.get("url") or ""), quote=True)
                location = html.escape(str(job.get("location") or "India"))
                if url:
                    lines.append(f"• <a href=\"{url}\">{title}</a> — {company} · {location}")
                else:
                    lines.append(f"• {title} — {company} · {location}")
        else:
            lines.extend(["", "No new matching jobs were saved in this run."])
        if failures:
            lines.extend(["", "Some sources need attention; check the GitHub Actions run."])
        lines.extend(["", "No applications were submitted automatically."])
        message = "\n".join(lines)[:4000]
        response = requests.post(
            f"{self.base}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram sendMessage failed"))
        return True
