#!/usr/bin/env python3
"""
Student Email Address Update
BCC/CUNY Library — Tokunbo Adeshina Jr.

Syncs preferred email addresses from Alma to ILLiad for all patrons
that exist in both systems (active and expired).
Runs on a schedule. Failed records are logged for manual review.
"""

import os
import csv
import logging
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

ALMA_API_KEY  = os.getenv("ALMA_API_KEY")
ALMA_BASE_URL = os.getenv("ALMA_BASE_URL", "").rstrip("/")
ILLIAD_API_KEY  = os.getenv("ILLIAD_API_KEY")
ILLIAD_BASE_URL = os.getenv("ILLIAD_BASE_URL", "").rstrip("/")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
run_log      = os.path.join(LOG_DIR, f"sync_{timestamp}.log")
failed_csv   = os.path.join(LOG_DIR, f"failed_updates_{timestamp}.csv")

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
# Alma helpers
# ---------------------------------------------------------------------------
ALMA_HEADERS = {
    "Authorization": f"apikey {ALMA_API_KEY}",
    "Accept": "application/json",
}

def get_all_alma_user_ids():
    """Fetch all Alma user primary IDs with pagination (active + expired)."""
    url    = f"{ALMA_BASE_URL}/almaws/v1/users"
    limit  = 100
    offset = 0
    ids    = []

    while True:
        resp = requests.get(
            url,
            headers=ALMA_HEADERS,
            params={"limit": limit, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        data  = resp.json()
        users = data.get("user", [])

        if not users:
            break

        for u in users:
            primary_id = u.get("primary_id")
            if primary_id:
                ids.append(primary_id)

        total   = int(data.get("total_record_count", 0))
        offset += limit
        log.info(f"Alma users fetched so far: {min(offset, total)} / {total}")

        if offset >= total:
            break

    log.info(f"Total Alma users retrieved: {len(ids)}")
    return ids


def get_alma_preferred_email(user_id):
    """
    Return the preferred email address for an Alma user, or None if not found.
    """
    url  = f"{ALMA_BASE_URL}/almaws/v1/users/{user_id}"
    resp = requests.get(url, headers=ALMA_HEADERS, timeout=30)
    resp.raise_for_status()

    emails = resp.json().get("contact_info", {}).get("email", [])
    for entry in emails:
        if entry.get("preferred"):
            return entry.get("email_address")
    return None


# ---------------------------------------------------------------------------
# ILLiad helpers
# ---------------------------------------------------------------------------
ILLIAD_HEADERS = {
    "ApiKey":       ILLIAD_API_KEY,
    "Accept":       "application/json",
    "Content-Type": "application/json",
}

def illiad_user_exists(user_id):
    """Return True if the patron exists in ILLiad."""
    url  = f"{ILLIAD_BASE_URL}/Users/{user_id}"
    resp = requests.get(url, headers=ILLIAD_HEADERS, timeout=30)
    return resp.status_code == 200


def update_illiad_email(user_id, email):
    """Patch the EMailAddress field for an ILLiad patron."""
    url  = f"{ILLIAD_BASE_URL}/Users/{user_id}"
    resp = requests.patch(
        url,
        headers=ILLIAD_HEADERS,
        json={"EMailAddress": email},
        timeout=30,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("=" * 60)
    log.info("Student Email Address Sync — START")
    log.info("=" * 60)

    failed_records = []
    success_count  = 0
    skip_count     = 0

    # Step 1 — Retrieve all Alma user IDs
    try:
        alma_ids = get_all_alma_user_ids()
    except Exception as exc:
        log.critical(f"Failed to retrieve Alma user list: {exc}")
        raise SystemExit(1)

    # Step 2 — Process each user
    for user_id in alma_ids:
        try:
            # Skip patrons not found in ILLiad
            if not illiad_user_exists(user_id):
                log.debug(f"Not in ILLiad, skipping: {user_id}")
                skip_count += 1
                continue

            # Get preferred email from Alma
            email = get_alma_preferred_email(user_id)
            if not email:
                log.warning(f"No preferred email in Alma for: {user_id}")
                failed_records.append({
                    "user_id": user_id,
                    "reason":  "No preferred email found in Alma",
                })
                continue

            # Update ILLiad
            update_illiad_email(user_id, email)
            log.info(f"Updated  {user_id}  →  {email}")
            success_count += 1

        except requests.HTTPError as exc:
            log.error(f"HTTP error for {user_id}: {exc}")
            failed_records.append({"user_id": user_id, "reason": str(exc)})

        except Exception as exc:
            log.error(f"Unexpected error for {user_id}: {exc}")
            failed_records.append({"user_id": user_id, "reason": str(exc)})

    # Step 3 — Write failed records to CSV for manual review
    if failed_records:
        with open(failed_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["user_id", "reason"])
            writer.writeheader()
            writer.writerows(failed_records)
        log.warning(f"{len(failed_records)} failed record(s) written to: {failed_csv}")

    # Step 4 — Summary
    log.info("=" * 60)
    log.info(
        f"Sync complete — "
        f"Updated: {success_count} | "
        f"Failed: {len(failed_records)} | "
        f"Skipped (not in ILLiad): {skip_count}"
    )
    log.info("=" * 60)


if __name__ == "__main__":
    main()
