#!/usr/bin/env python3
"""Fail-fast Google Sheets identity, read, and reversible-write health check."""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.sheets_manager import SheetsManager

EXPECTED_TITLE = os.getenv("EXPECTED_SPREADSHEET_TITLE", "Job Application Tracker")
EXPECTED_TAB = os.getenv("EXPECTED_SHEET_TAB", "Job_Applications")


def main():
    manager = SheetsManager()
    if not manager.connect():
        print("::error::Google Sheets authentication/open-by-ID failed")
        return 1
    actual_title = (manager.spreadsheet.title or "").strip()
    if actual_title != EXPECTED_TITLE:
        print(f"::error::Wrong spreadsheet. Expected '{EXPECTED_TITLE}', got '{actual_title}'")
        return 1
    sheet = manager.get_sheet(EXPECTED_TAB)
    if sheet is None:
        print(f"::error::Required worksheet '{EXPECTED_TAB}' is unavailable")
        return 1
    try:
        values = sheet.get("A1:K1")
        print(f"✅ Read check passed; first-row columns={len(values[0]) if values else 0}")
    except Exception as exc:
        print(f"::error::Read verification failed: {type(exc).__name__}: {exc}")
        return 1

    # Create, verify, and delete a uniquely named one-cell worksheet. This proves
    # write access without touching tracker rows. Cleanup failure is also a failure.
    temporary = None
    temporary_name = f"__SAM_CHECK_{uuid.uuid4().hex[:8]}"
    token = f"sam-write-check-{uuid.uuid4().hex}"
    try:
        temporary = manager.spreadsheet.add_worksheet(title=temporary_name, rows=1, cols=1)
        temporary.update_acell("A1", token)
        if temporary.acell("A1").value != token:
            raise RuntimeError("written token could not be read back")
        print(f"✅ Reversible write check passed: {actual_title} / {EXPECTED_TAB}")
    except Exception as exc:
        print(f"::error::Write verification failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if temporary is not None:
            try:
                manager.spreadsheet.del_worksheet(temporary)
            except Exception as exc:
                print(f"::error::Diagnostic cleanup failed for {temporary_name}: {type(exc).__name__}: {exc}")
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
