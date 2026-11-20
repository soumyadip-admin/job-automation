#!/usr/bin/env python3
"""One-time, privacy-preserving pairing for @SoumyadipSAMCareerBot.

While this script is running, the user sends the exact phrase PAIR SAM to the bot.
The chat ID is returned inside that private bot conversation and is never printed to
GitHub Actions logs.
"""
import json
import os
import time

import requests

EXPECTED_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "SoumyadipSAMCareerBot").lstrip("@")
PAIR_PHRASE = "PAIR SAM"


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

        print(f"✅ @{username} verified. Waiting up to 90 seconds for the private pairing phrase...")
        deadline = time.monotonic() + 90
        offset = None
        paired = None
        while time.monotonic() < deadline and paired is None:
            params = {"timeout": 10, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                params["offset"] = offset
            response = requests.get(f"{base}/getUpdates", params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Telegram getUpdates failed"))
            for update in payload.get("result", []):
                update_id = int(update["update_id"])
                offset = update_id + 1
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                text = str(message.get("text", "")).strip().upper()
                if chat.get("type") == "private" and text == PAIR_PHRASE:
                    paired = (update_id, str(chat.get("id")))
                    break

        if paired is None:
            raise RuntimeError("pairing phrase not received; rerun pairing and send PAIR SAM to the bot while the job is active")

        update_id, chat_id = paired
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

        ack = requests.get(f"{base}/getUpdates", params={"offset": update_id + 1, "timeout": 0}, timeout=15)
        ack.raise_for_status()
        print(f"✅ Pairing message sent privately by @{username}; no chat ID was written to logs")
        return 0
    except Exception as exc:
        print(f"::error::Telegram pairing failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
