#!/usr/bin/env python3
"""One-time, privacy-preserving pairing for @SoumyadipSAMCareerBot.

The chat ID is sent back inside the private bot conversation and is never printed to
GitHub Actions logs.
"""
import json
import os
import sys

import requests

EXPECTED_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "SoumyadipSAMCareerBot").lstrip("@")


def main():
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        print("::error::Missing TELEGRAM_BOT_TOKEN")
        return 1
    base = f"https://api.telegram.org/bot{token}"
    try:
        identity_response = requests.get(f"{base}/getMe", timeout=15)
        identity_response.raise_for_status()
        identity = identity_response.json()
        username = str((identity.get("result") or {}).get("username", ""))
        if not identity.get("ok") or username.lower() != EXPECTED_USERNAME.lower():
            raise RuntimeError(f"token is for @{username or 'unknown'}, not @{EXPECTED_USERNAME}")

        updates_response = requests.get(
            f"{base}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["message"])},
            timeout=20,
        )
        updates_response.raise_for_status()
        updates = updates_response.json()
        candidates = []
        for update in updates.get("result", []):
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            if chat.get("type") == "private" and str(message.get("text", "")).startswith("/start"):
                candidates.append((int(update["update_id"]), str(chat.get("id"))))
        if not candidates:
            raise RuntimeError("no private /start message found; open the bot and send /start, then rerun pairing")

        update_id, chat_id = candidates[-1]
        send_response = requests.post(
            f"{base}/sendMessage",
            json={
                "chat_id": chat_id,
                "parse_mode": "HTML",
                "text": (
                    "✅ <b>SAM Career pairing detected</b>\n\n"
                    f"Your private Telegram chat ID is: <code>{chat_id}</code>\n\n"
                    "Add this number to the GitHub Actions secret named "
                    "<code>TELEGRAM_CHAT_ID</code>. Do not post it publicly."
                ),
            },
            timeout=20,
        )
        send_response.raise_for_status()
        if not send_response.json().get("ok"):
            raise RuntimeError("Telegram could not send the private pairing message")

        # Confirm only through the paired /start update. No chat ID is logged.
        ack = requests.get(f"{base}/getUpdates", params={"offset": update_id + 1, "timeout": 0}, timeout=15)
        ack.raise_for_status()
        print(f"✅ Pairing message sent privately by @{username}; no chat ID was written to logs")
        return 0
    except Exception as exc:
        print(f"::error::Telegram pairing failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
