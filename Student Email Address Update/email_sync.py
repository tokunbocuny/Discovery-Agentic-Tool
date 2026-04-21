#!/usr/bin/env python3
"""
Student Email Address Update
BCC/CUNY Library — Tokunbo Adeshina Jr.

Workflow:
  1. Read all patron usernames from an ILLiad user export CSV
  2. For each patron, look up their account in Alma
  3. Retrieve the preferred email from Alma contact info
  4. Write all original columns + a new 'Alma Email' column to an output CSV

The output CSV can then be used to bulk import updated email addresses into ILLiad.

Usage:
  python3 email_sync.py                        # uses default illiad_users.csv
  python3 email_sync.py my_export.csv          # uses a custom export file

Output:
  output/email_update_<timestamp>.csv          # updated records
  logs/failed_updates_<timestamp>.csv          # patrons with no Alma email found
  logs/sync_<timestamp>.log                    # full run log

ILLiad Export Instructions:
  ILLiad Staff Client → Reports → User Reports → Export Users → Save as CSV
  The CSV must contain a column named 'Username' or 'User Name'.
"""

import os
import csv
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

ALMA_API_KEY  = os.getenv("ALMA_API_KEY")
ALMA_BASE_URL = os.getenv("ALMA_BASE_URL", "").rstrip("/")

SCRIPT_DIR = os.path.dirname(__file__)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR    = os.path.join(SCRIPT_DIR, "logs")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
run_log     = os.path.join(LOG_DIR, f"sync_{timestamp}.log")
failed_csv  = os.path.join(LOG_DIR, f"failed_updates_{timestamp}.csv")
output_csv  = os.path.join(OUTPUT_DIR, f"email_update_{timestamp}.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(run_log),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ILLiad CSV reader
# ---------------------------------------------------------------------------
def load_illiad_export(filepath):
    """
    Read all rows from an ILLiad CSV export.
    Detects 'Username' or 'User Name' column automatically.
    Returns (fieldnames, rows, username_col).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"ILLiad export file not found: {filepath}\n"
            "Export from ILLiad Staff Client → Reports → User Reports → Export Users"
        )

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        username_col = None
        for col in fieldnames:
            if col.replace(" ", "").lower() == "username":
                username_col = col
                break

        if not username_col:
            raise ValueError(
                f"CSV is missing a 'Username' column. Found: {fieldnames}"
            )

        rows = list(reader)

    log.info(f"Loaded {len(rows)} patron(s) from: {filepath}")
    return fieldnames, rows, username_col


# ---------------------------------------------------------------------------
# Alma helpers
# ---------------------------------------------------------------------------
ALMA_HEADERS = {
    "Authorization": f"apikey {ALMA_API_KEY}",
    "Accept":        "application/json",
}

def get_alma_preferred_email(user_id):
    """
    Look up an Alma user by ID and return their preferred email, or None.
    Returns None silently on 404 (user not in Alma).
    """
    url  = f"{ALMA_BASE_URL}/almaws/v1/users/{user_id}"
    resp = requests.get(url, headers=ALMA_HEADERS, timeout=30)

    # 404 = not in Alma, 400 = ID not recognised by Alma — skip both gracefully
    if resp.status_code in (400, 404):
        return None

    resp.raise_for_status()

    emails = resp.json().get("contact_info", {}).get("email", [])
    for entry in emails:
        if entry.get("preferred"):
            return entry.get("email_address")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    export_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "illiad_users.csv")

    log.info("=" * 60)
    log.info("Student Email Address Sync — START")
    log.info(f"ILLiad export file : {export_file}")
    log.info(f"Output file        : {output_csv}")
    log.info("=" * 60)

    failed_records  = []
    success_count   = 0
    skip_count      = 0

    # Step 1 — Load ILLiad export
    try:
        fieldnames, rows, username_col = load_illiad_export(export_file)
    except (FileNotFoundError, ValueError) as exc:
        log.critical(str(exc))
        raise SystemExit(1)

    # Step 2 — Look up each patron in Alma and enrich with email
    output_fieldnames = fieldnames + ["Alma Email"]
    output_rows = []

    for row in rows:
        username = row.get(username_col, "").strip()
        if not username:
            continue

        try:
            email = get_alma_preferred_email(username)

            if email is None:
                log.debug(f"No Alma account or no preferred email for: {username}")
                row["Alma Email"] = ""
                skip_count += 1
            else:
                row["Alma Email"] = email
                log.info(f"Found  {username}  →  {email}")
                success_count += 1

        except requests.HTTPError as exc:
            log.error(f"HTTP error for {username}: {exc}")
            row["Alma Email"] = ""
            failed_records.append({"username": username, "reason": str(exc)})

        except Exception as exc:
            log.error(f"Unexpected error for {username}: {exc}")
            row["Alma Email"] = ""
            failed_records.append({"username": username, "reason": str(exc)})

        output_rows.append(row)

    # Step 3 — Write enriched output CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    log.info(f"Output written to: {output_csv}")

    # Step 4 — Write failed records log
    if failed_records:
        with open(failed_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["username", "reason"])
            writer.writeheader()
            writer.writerows(failed_records)
        log.warning(f"{len(failed_records)} failed record(s) written to: {failed_csv}")

    # Step 5 — Summary
    log.info("=" * 60)
    log.info(
        f"Sync complete — "
        f"Emails found: {success_count} | "
        f"Failed: {len(failed_records)} | "
        f"Not in Alma: {skip_count}"
    )
    log.info("=" * 60)


if __name__ == "__main__":
    main()
