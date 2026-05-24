#!/usr/bin/env python3
"""Manual test for the Byte-Watt battery data endpoint.

Usage:
    python3 scripts/manual_battery_data_check.py <username> <password> [station_id]

Imports the integration's own ``encrypt_password`` so the script always
matches the production code path — no duplicated encryption logic.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime

import requests

# Make the integration importable when running this script directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.bytewatt.api.neovolt_auth import (  # noqa: E402
    EncryptionError,
    encrypt_password,
)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_battery_data")

def login(username: str, password: str, base_url: str = "https://monitor.byte-watt.com") -> str:
    """Log in to the API and return the authentication token."""
    login_url = f"{base_url}/api/usercenter/cloud/user/login"
    
    try:
        encrypted_password = encrypt_password(password, username)
    except EncryptionError as exc:
        logger.error("Cannot log in: encryption failed (%s)", exc)
        return None

    payload = {"username": username, "password": encrypted_password}
    
    logger.info(f"Logging in to {login_url}")
    
    try:
        response = requests.post(
            login_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Login failed with status {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        
        if result.get("code") != 0 and result.get("code") != 200:
            logger.error(f"Login failed with code {result.get('code')}: {result.get('msg')}")
            return None
        
        # Extract token
        token = None
        if "token" in result:
            token = result["token"]
        elif "data" in result and result["data"] and "token" in result["data"]:
            token = result["data"]["token"]
        
        if token:
            logger.info(f"Login successful, token: {token[:10]}...")
            return token
        else:
            logger.error("No token found in response")
            return None
    
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return None

def get_battery_data(token: str, station_id: str = None, base_url: str = "https://monitor.byte-watt.com") -> dict:
    """Get battery data using the new API endpoint."""
    url = f"{base_url}/api/report/energyStorage/getLastPowerData"
    
    params = {
        "sysSn": "All",
        "stationId": station_id or ""
    }
    
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "language": "en-US",
        "operationDate": current_date,
        "platform": "AK9D8H",
        "System": "alphacloud"
    }
    
    logger.info(f"Getting battery data from {url}")
    
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get battery data with status {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        
        if result.get("code") != 0 and result.get("code") != 200:
            logger.error(f"Failed to get battery data with code {result.get('code')}: {result.get('msg')}")
            return None
        
        data = result.get("data")
        logger.info(f"Received battery data: {json.dumps(data, indent=2)}")
        return data
    
    except Exception as e:
        logger.error(f"Error getting battery data: {str(e)}")
        return None

def print_battery_values(data: dict) -> None:
    """Print the important battery values in a readable format."""
    if not data:
        print("No battery data available")
        return
    
    # Key metrics to display
    metrics = {
        "soc": "Battery state of charge (%)",
        "pbat": "Battery power (W)",
        "ppv": "Solar generation (W)",
        "pload": "Load consumption (W)",
        "pgrid": "Grid power (W)"
    }
    
    print("\n=== Battery Status ===")
    for key, description in metrics.items():
        if key in data:
            print(f"{description}: {data[key]}")
    
    # Extra values that might be useful
    if "ppv1" in data:
        print(f"Solar string 1 (W): {data['ppv1']}")
    if "ppv2" in data:
        print(f"Solar string 2 (W): {data['ppv2']}")
    
    # Battery charging/discharging state
    if "pbat" in data:
        bat_power = data["pbat"]
        if bat_power > 0:
            print(f"Battery status: CHARGING at {bat_power}W")
        elif bat_power < 0:
            print(f"Battery status: DISCHARGING at {abs(bat_power)}W")
        else:
            print("Battery status: IDLE")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_battery_data.py <username> <password> [station_id]")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    station_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Login to get token
    token = login(username, password)
    
    if not token:
        print("❌ Authentication failed, cannot test battery data")
        sys.exit(1)
    
    # Get battery data
    battery_data = get_battery_data(token, station_id)
    
    if battery_data:
        print("✅ Successfully retrieved battery data!")
        print_battery_values(battery_data)
    else:
        print("❌ Failed to retrieve battery data")