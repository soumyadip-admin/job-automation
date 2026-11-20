#!/usr/bin/env python3
"""Fail-fast Telegram bot identity and destination validation."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.telegram_notifier import TelegramNotifier


def main():
    try:
        notifier = TelegramNotifier()
        username = notifier.validate()
        # getChat validates the configured destination without sending a message.
        response = __import__("requests").get(
            f"{notifier.base}/getChat",
            params={"chat_id": notifier.chat_id},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram getChat failed"))
        print(f"✅ Telegram preflight passed for @{username}; destination type={(payload.get('result') or {}).get('type', 'unknown')}")
        return 0
    except Exception as exc:
        print(f"::error::Telegram preflight failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
