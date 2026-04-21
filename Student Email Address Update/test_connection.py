#!/usr/bin/env python3
"""
Connection Test — Student Email Address Update
Tests Alma API connectivity before running the full sync.
Fetches one Alma user and retrieves their preferred email.
Does NOT write any changes.
"""

import os
from dotenv import load_dotenv
import requests

load_dotenv()

ALMA_API_KEY  = os.getenv("ALMA_API_KEY")
ALMA_BASE_URL = os.getenv("ALMA_BASE_URL", "").rstrip("/")

ALMA_HEADERS = {
    "Authorization": f"apikey {ALMA_API_KEY}",
    "Accept": "application/json",
}

def test_alma_connection():
    print("\n--- Alma API ---")
    url  = f"{ALMA_BASE_URL}/almaws/v1/users"
    resp = requests.get(url, headers=ALMA_HEADERS, params={"limit": 1}, timeout=30)
    print(f"Status: {resp.status_code}")
    resp.raise_for_status()
    data  = resp.json()
    total = data.get("total_record_count", 0)
    print(f"Connection successful. Total users in Alma: {total}")
    user  = data.get("user", [])[0]
    uid   = user.get("primary_id")
    print(f"Sample user ID: {uid}")
    return uid

def test_alma_email(user_id):
    print(f"\n--- Alma Preferred Email for: {user_id} ---")
    url  = f"{ALMA_BASE_URL}/almaws/v1/users/{user_id}"
    resp = requests.get(url, headers=ALMA_HEADERS, timeout=30)
    print(f"Status: {resp.status_code}")
    resp.raise_for_status()
    emails = resp.json().get("contact_info", {}).get("email", [])
    preferred = next((e.get("email_address") for e in emails if e.get("preferred")), None)
    if preferred:
        print(f"Preferred email found: {preferred}")
    else:
        print("No preferred email found for this user.")
    return preferred

def main():
    print("=" * 50)
    print("Connection Test — Student Email Address Sync")
    print("READ-ONLY: No changes will be made.")
    print("=" * 50)

    try:
        user_id = test_alma_connection()
    except Exception as exc:
        print(f"\nAlma connection FAILED: {exc}")
        return

    try:
        test_alma_email(user_id)
    except Exception as exc:
        print(f"\nAlma email lookup FAILED: {exc}")
        return

    print("\n" + "=" * 50)
    print("Alma connection test passed. Ready to run email_sync.py.")
    print("=" * 50)

if __name__ == "__main__":
    main()
