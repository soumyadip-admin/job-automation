"""Public Telegram job discovery and private forwarded-message inbox.

Public channels are read from their no-login web previews. Private-channel posts are
only available when the user explicitly forwards them to the configured bot. The
module never logs in to a personal Telegram account or requests an OTP/session.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


class TelegramJobSource:
    SOCIAL_HOSTS = {
        "t.me", "telegram.me", "telegram.dog", "whatsapp.com", "www.whatsapp.com",
        "instagram.com", "www.instagram.com", "youtube.com", "www.youtube.com", "youtu.be",
        "facebook.com", "www.facebook.com", "x.com", "twitter.com",
    }
    AGGREGATOR_HOSTS = {
        "foundthejob.com", "www.foundthejob.com", "merademyjobs.com", "www.merademyjobs.com",
        "jobsgovind.com", "www.jobsgovind.com", "pdlink.in", "www.pdlink.in",
    }
    TARGET_HINT = re.compile(
        r"\b(data analyst|data analytics|reporting and analytics|reporting analyst|"
        r"business intelligence|bi analyst|mis analyst|mis executive|operations analyst|"
        r"operations analytics|workforce analyst|wfm analyst|insights analyst)\b", re.I,
    )
    EXCLUDE_HINT = re.compile(
        r"\b(customer support|customer service|technical support|chat support|voice process|"
        r"non[- ]voice|telecaller|telecalling|call cent(?:er|re)|contact cent(?:er|re)|bpo|"
        r"process associate|process executive|senior|sr\.?|lead|manager|director|principal|head)\b",
        re.I,
    )
    IDENTITY_QUERY_KEYS = {"id", "jobid", "job_id", "jrid", "reqid", "requisitionid", "folderid"}

    def __init__(self, channels=(), session=None):
        self.channels = tuple(str(x).lstrip("@").strip() for x in channels if str(x).strip())
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "SAM-Career-Discovery/3.0 (+public job research)",
            "Accept-Language": "en-IN,en;q=0.9",
        })
        self.errors: list[str] = []
        self.successful_channels = 0
        self.scanned_posts = 0

    @classmethod
    def canonical_url(cls, value: str) -> str:
        try:
            parts = urlsplit(str(value or "").strip())
            host = parts.netloc.lower()
            if parts.scheme not in {"http", "https"} or not host:
                return ""
            path = re.sub(r"/jobs/preview/(\d+)$", r"/job/\1", parts.path.rstrip("/"))
            query = [
                (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=False)
                if key.lower() in cls.IDENTITY_QUERY_KEYS and val
            ]
            return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))
        except (TypeError, ValueError):
            return ""

    @classmethod
    def _usable_external_url(cls, value: str) -> bool:
        canonical = cls.canonical_url(value)
        if not canonical:
            return False
        parts = urlsplit(canonical)
        if parts.netloc in cls.SOCIAL_HOSTS:
            return False
        # Reject generic home pages and links that only ask for comments/DMs.
        return bool(parts.path.strip("/") or parts.query)

    @staticmethod
    def _clean(value) -> str:
        return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()

    @staticmethod
    def _parse_time(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _field(lines, labels):
        pattern = re.compile(rf"^(?:{'|'.join(re.escape(x) for x in labels)})\s*[:\-–]\s*(.+)$", re.I)
        for line in reversed(lines):
            match = pattern.match(line)
            if match:
                return match.group(1).strip(" -*")
        return ""

    @classmethod
    def _nearest_company(cls, lines, title_index):
        explicit = cls._field(lines[: title_index + 1], ("company", "company name"))
        if explicit:
            return explicit
        ignored = re.compile(
            r"^(position|role|post|qualification|experience|location|apply|link|join|jobs?|hiring|"
            r"work experience|work mode|salary)\b", re.I,
        )
        for line in reversed(lines[max(0, title_index - 5):title_index]):
            candidate = cls._clean(re.sub(r"^[^A-Za-z0-9]+", "", line))
            if candidate and len(candidate) <= 90 and not ignored.match(candidate) and "http" not in candidate:
                return candidate
        return ""

    @classmethod
    def candidates_from_text(cls, text: str, links: list[str], source: str,
                             message_url: str, observed_at: str) -> list[dict]:
        lines = [cls._clean(x) for x in str(text or "").splitlines() if cls._clean(x)]
        results = []
        for raw_link in dict.fromkeys(links):
            if not cls._usable_external_url(raw_link):
                continue
            canonical = cls.canonical_url(raw_link)
            line_index = next(
                (i for i, line in enumerate(lines) if raw_link in line or canonical in line),
                len(lines),
            )
            context = lines[max(0, line_index - 10):line_index]
            title = cls._field(context, ("position", "role", "post"))
            if not title:
                hiring = re.search(r"([A-Za-z0-9&.' -]{2,70})\s+is hiring.*?(?:post|role)\s*[-:]\s*([^\n]+)", text, re.I | re.S)
                if hiring:
                    title = cls._clean(hiring.group(2).splitlines()[0])
            if not title or not cls.TARGET_HINT.search(title) or cls.EXCLUDE_HINT.search(title):
                continue
            title_index = next((i for i, line in enumerate(lines) if title.lower() in line.lower()), max(0, line_index - 1))
            company = cls._nearest_company(lines, title_index)
            location = cls._field(context, ("location",)) or ("Remote" if re.search(r"\b(remote|work from home|wfh)\b", text, re.I) else "India")
            results.append({
                "title": title,
                "company": company or "See official listing",
                "location": location,
                "url": canonical,
                "platform": source,
                "salary": "Not disclosed",
                "description": cls._clean(text)[:5000],
                "posted_date": "",
                "source_observed_at": observed_at,
                "source_message_url": message_url,
                "source": "telegram_public_or_forwarded",
            })
        return results

    @staticmethod
    def _walk_json(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from TelegramJobSource._walk_json(child)
        elif isinstance(value, list):
            for child in value:
                yield from TelegramJobSource._walk_json(child)

    @classmethod
    def _job_posting(cls, soup):
        for script in soup.select("script[type='application/ld+json']"):
            try:
                payload = json.loads(script.string or script.get_text() or "null")
            except (json.JSONDecodeError, TypeError):
                continue
            for node in cls._walk_json(payload):
                kinds = node.get("@type", [])
                if isinstance(kinds, str):
                    kinds = [kinds]
                if "JobPosting" in kinds:
                    return node
        return None

    @classmethod
    def _posting_location(cls, posting):
        if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
            return "Remote"
        locations = posting.get("jobLocation") or []
        if isinstance(locations, dict):
            locations = [locations]
        output = []
        for item in locations:
            address = item.get("address", {}) if isinstance(item, dict) else {}
            if isinstance(address, str):
                output.append(address)
            elif isinstance(address, dict):
                value = ", ".join(str(address.get(k, "")).strip() for k in ("addressLocality", "addressRegion", "addressCountry") if address.get(k))
                if value:
                    output.append(value)
        return " / ".join(dict.fromkeys(output))

    def _fetch_and_enrich(self, candidate: dict, depth=0) -> dict | None:
        try:
            response = self.session.get(candidate["url"], timeout=20, allow_redirects=True)
            response.raise_for_status()
            final_url = self.canonical_url(response.url)
            if not final_url or not self._usable_external_url(final_url):
                return None
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "xhtml" not in content_type:
                candidate["url"] = final_url
                candidate["link_verified"] = True
                return candidate
            soup = BeautifulSoup(response.text, "html.parser")
            posting = self._job_posting(soup)
            host = urlsplit(final_url).netloc

            if posting:
                title = self._clean(posting.get("title"))
                if title:
                    candidate["title"] = title
                organization = posting.get("hiringOrganization") or {}
                if isinstance(organization, dict) and self._clean(organization.get("name")):
                    candidate["company"] = self._clean(organization.get("name"))
                location = self._posting_location(posting)
                if location:
                    candidate["location"] = location
                description = BeautifulSoup(str(posting.get("description") or ""), "html.parser").get_text(" ", strip=True)
                if description:
                    candidate["description"] = self._clean(description)[:7000]
                if posting.get("datePosted"):
                    candidate["posted_date"] = str(posting["datePosted"])
            elif host in self.AGGREGATOR_HOSTS and depth == 0:
                outbound = []
                for anchor in soup.find_all("a", href=True):
                    label = self._clean(anchor.get_text(" ", strip=True))
                    href = urljoin(response.url, anchor["href"])
                    href_host = urlsplit(href).netloc.lower()
                    if re.search(r"\b(apply|click here|official)\b", label, re.I) and href_host not in self.SOCIAL_HOSTS and href_host not in self.AGGREGATOR_HOSTS:
                        outbound.append(href)
                if outbound:
                    candidate["url"] = self.canonical_url(outbound[0])
                    return self._fetch_and_enrich(candidate, depth=1)

            if not posting:
                page_text = self._clean(soup.get_text(" ", strip=True))
                heading = soup.find("h1")
                heading_text = self._clean(heading.get_text(" ", strip=True)) if heading else ""
                if heading_text and self.TARGET_HINT.search(heading_text):
                    candidate["title"] = heading_text[:180]
                if page_text:
                    candidate["description"] = page_text[:7000]
                # Catch official pages whose H1 is generic but whose job level is explicitly senior.
                if re.search(r"\b(senior analyst|senior associate|lead analyst|manager)\b", page_text[:900], re.I):
                    return None
            # Recheck after authoritative enrichment so a Telegram mislabel cannot bypass exclusions.
            if not self.TARGET_HINT.search(candidate.get("title", "")) or self.EXCLUDE_HINT.search(candidate.get("title", "")):
                return None
            candidate["url"] = final_url
            candidate["link_verified"] = True
            return candidate
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            parts = urlsplit(candidate.get("url", ""))
            if status in {401, 403} and parts.netloc.lower() not in self.AGGREGATOR_HOSTS and re.search(r"/(?:job|jobs)/", parts.path, re.I):
                # Some official career portals block automated clients but open normally in a browser.
                candidate["link_verified"] = "browser_protected"
                candidate["description"] = (candidate.get("description", "") + " Official portal blocks automated verification; review in browser.").strip()
                return candidate
            self.errors.append(f"Link verification failed for {candidate.get('url')}: HTTP {status}")
            return None
        except Exception as exc:
            self.errors.append(f"Link verification failed for {candidate.get('url')}: {type(exc).__name__}: {str(exc)[:100]}")
            return None

    def collect_public(self, max_age_hours=24, max_jobs=50):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        results, seen = [], set()
        for channel in self.channels:
            try:
                response = self.session.get(f"https://t.me/s/{channel}", timeout=25)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                messages = soup.select(".tgme_widget_message")
                self.successful_channels += 1
                for message in messages:
                    time_el = message.select_one("time[datetime]")
                    observed = self._parse_time(time_el.get("datetime", "") if time_el else "")
                    if not observed or observed < cutoff:
                        continue
                    self.scanned_posts += 1
                    text_el = message.select_one(".tgme_widget_message_text")
                    if not text_el:
                        continue
                    text = text_el.get_text("\n", strip=True)
                    links = [a.get("href", "") for a in text_el.select("a[href]")]
                    data_post = message.get("data-post", "")
                    message_url = f"https://t.me/{data_post}" if data_post else f"https://t.me/{channel}"
                    candidates = self.candidates_from_text(
                        text, links, f"Telegram: {channel}", message_url, observed.isoformat()
                    )
                    for candidate in candidates:
                        enriched = self._fetch_and_enrich(candidate)
                        if enriched and enriched["url"] not in seen:
                            seen.add(enriched["url"])
                            results.append(enriched)
                            if len(results) >= max_jobs:
                                return results
            except Exception as exc:
                self.errors.append(f"Telegram/{channel}: {type(exc).__name__}: {str(exc)[:120]}")
        return results


class TelegramBotInbox:
    """Read only messages explicitly sent/forwarded to the configured private bot."""

    def __init__(self, token: str, allowed_chat_id: str, parser: TelegramJobSource):
        self.token = str(token or "").strip()
        self.allowed_chat_id = str(allowed_chat_id or "").strip()
        self.parser = parser
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.pending_update_ids: list[int] = []

    @property
    def configured(self):
        return bool(self.token and self.allowed_chat_id)

    def collect_forwarded(self):
        if not self.configured:
            raise RuntimeError("Telegram bot token/chat ID is not configured")
        response = requests.get(
            f"{self.base}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["message"])},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram getUpdates failed"))
        jobs = []
        for update in payload.get("result", []):
            update_id = int(update["update_id"])
            self.pending_update_ids.append(update_id)
            message = update.get("message") or {}
            chat_id = str((message.get("chat") or {}).get("id", ""))
            if chat_id != self.allowed_chat_id:
                continue
            text = message.get("text") or message.get("caption") or ""
            if not text or text.startswith("/start"):
                continue
            links = re.findall(r"https?://[^\s<>\"]+", text)
            for entity in (message.get("entities") or []) + (message.get("caption_entities") or []):
                if entity.get("url"):
                    links.append(entity["url"])
            observed = datetime.fromtimestamp(message.get("date", 0), tz=timezone.utc).isoformat()
            message_url = ""
            origin = message.get("forward_origin") or {}
            source_chat = origin.get("chat") or {}
            username = source_chat.get("username")
            source_message_id = origin.get("message_id")
            if username and source_message_id:
                message_url = f"https://t.me/{username}/{source_message_id}"
            for candidate in self.parser.candidates_from_text(
                text, links, "Telegram: Forwarded to SAM bot", message_url, observed
            ):
                enriched = self.parser._fetch_and_enrich(candidate)
                if enriched:
                    jobs.append(enriched)
        return jobs

    def acknowledge(self):
        if not self.pending_update_ids:
            return
        response = requests.get(
            f"{self.base}/getUpdates",
            params={"offset": max(self.pending_update_ids) + 1, "timeout": 0},
            timeout=20,
        )
        response.raise_for_status()
        if not response.json().get("ok"):
            raise RuntimeError("Telegram update acknowledgement failed")
