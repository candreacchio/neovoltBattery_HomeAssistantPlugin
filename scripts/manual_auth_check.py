#!/usr/bin/env python3
"""Manual authentication test for the Byte-Watt portal.

Usage:
    python3 scripts/manual_auth_check.py <username> <password> [base_url]

Imports the integration's own ``encrypt_password`` so the script always
matches the production code path — there is no duplicated copy of the
encryption algorithm that could drift over time.
"""
from __future__ import annotations

import logging
import os
import sys

import requests

# Make the integration importable when running this script directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.bytewatt.api.neovolt_auth import (  # noqa: E402
    EncryptionError,
    encrypt_password,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

_KNOWN_VECTORS = [
    {"username": "caraa",  "password": "1", "expected": "CH1iL1FqYK9bhTd9izZyMA=="},
    {"username": "carraa", "password": "1", "expected": "oFzzKemj3O4WP92FBSjZzw=="},
]


def test_encryption() -> bool:
    """Smoke-test the encryption against known vectors."""
    all_passed = True
    for i, case in enumerate(_KNOWN_VECTORS, start=1):
        try:
            encrypted = encrypt_password(case["password"], case["username"])
        except EncryptionError as exc:
            logging.error("Test case %d FAILED with exception: %s", i, exc)
            all_passed = False
            continue
        if encrypted == case["expected"]:
            logging.info("Test case %d PASSED", i)
        else:
            logging.error(
                "Test case %d FAILED — expected %s, got %s",
                i, case["expected"], encrypted,
            )
            all_passed = False
    return all_passed


def test_api_login(username: str, password: str, base_url: str) -> bool:
    """Live-fire login against the Byte-Watt API."""
    login_url = f"{base_url}/api/usercenter/cloud/user/login"

    try:
        encrypted = encrypt_password(password, username)
    except EncryptionError as exc:
        logging.error("Cannot test login: encryption failed (%s)", exc)
        return False

    logging.info("Encrypted password: %s", encrypted)
    payload = {"username": username, "password": encrypted}

    try:
        logging.info("POST %s (encrypted)", login_url)
        response = requests.post(
            login_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        logging.info("Response status: %s", response.status_code)
        if response.status_code != 200:
            logging.error("Request failed: %s", response.text[:500])
            return False
        result = response.json()
        if result.get("code") not in (0, 200):
            logging.error("Login rejected with code %s: %s",
                          result.get("code"), result.get("msg"))
            return False
        token = result.get("token") or (result.get("data") or {}).get("token")
        if not token:
            logging.warning("Login succeeded but no token in response")
            return False
        logging.info("Token received: %s...", token[:10])
        return True
    except requests.RequestException as exc:
        logging.error("Request error: %s", exc)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/manual_auth_check.py <username> <password> [base_url]")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    base_url = sys.argv[3] if len(sys.argv) > 3 else "https://monitor.byte-watt.com"

    print("\nTesting encryption function against known vectors...")
    if test_encryption():
        print("[OK] Encryption matches known vectors")
    else:
        print("[FAIL] Encryption function broken")
        sys.exit(1)

    print(f"\nTesting API login as {username}...")
    if test_api_login(username, password, base_url):
        print("[OK] Login succeeded — authentication works")
    else:
        print("[FAIL] Login failed")
        sys.exit(1)
