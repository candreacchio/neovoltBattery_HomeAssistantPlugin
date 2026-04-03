"""API client for Neovolt battery systems."""
import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .neovolt_auth import encrypt_password

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_BASE_URL = "https://monitor.byte-watt.com"
RATE_LIMIT_BACKOFF_SECONDS = 10


def _normalize_cycle_windows(
    raw_windows: Optional[List[Dict[str, Any]]],
    default_power: int,
    default_limit: float,
) -> List[Dict[str, Any]]:
    """Normalize charge/discharge window definitions for ByteWatt API."""
    if not raw_windows:
        return []

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_windows, start=1):
        if not isinstance(item, dict):
            continue
        begin = item.get("beginTime") or item.get("start") or item.get("begin")
        end = item.get("endTime") or item.get("end")
        if not begin or not end:
            continue
        normalized.append(
            {
                "chargeLimit": float(item.get("chargeLimit", default_limit)),
                "beginTime": str(begin),
                "endTime": str(end),
                "sort": int(item.get("sort", idx)),
                "chargePower": int(item.get("chargePower", default_power)),
                "weeks": item.get("weeks") or [7, 1, 2, 3, 4, 5, 6],
                "feedMode": int(item.get("feedMode", 0)),
                "equipGroupId": int(item.get("equipGroupId", 0)),
                "feedPower": int(item.get("feedPower", 0)),
            }
        )
    return normalized

class NeovoltClient:
    """API Client for Neovolt battery systems."""
    
    def __init__(
        self, 
        hass: HomeAssistant, 
        username: str, 
        password: str, 
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.username = username
        self.password = password
        self.base_url = base_url
        self.session = async_get_clientsession(hass)
        self.token: Optional[str] = None
        self._settings_cache = None
        self._fresh_settings_update = False
        self._settings_update_time = None
        self._control_variant_data: Dict[str, Any] = {}
    
    async def async_login(self) -> bool:
        """Login to the Neovolt API using encrypted password."""
        _LOGGER.debug("Logging in to Neovolt API as %s", self.username)
        
        login_url = f"{self.base_url}/api/usercenter/cloud/user/login"
        
        # Encrypt password using the correct method
        encrypted_password = encrypt_password(self.password, self.username)
        
        # JSON payload with encrypted password
        payload = {
            "username": self.username,
            "password": encrypted_password
        }
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.post(
                    url=login_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status != 200:
                    if response.status == 429:
                        _LOGGER.warning("Rate limited fetching device list, backing off for %ss", RATE_LIMIT_BACKOFF_SECONDS)
                        await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                        return None
                    _LOGGER.error(
                        "Login failed with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    return await self._async_login_fallback()
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    _LOGGER.error(
                        "Login failed with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return await self._async_login_fallback()
                
                # Extract token - handle different response formats
                if "token" in result:
                    self.token = result["token"]
                elif "data" in result and result["data"] and "token" in result["data"]:
                    self.token = result["data"]["token"]
                else:
                    _LOGGER.error("No token found in login response")
                    return False
                
                _LOGGER.debug("Successfully logged in to Neovolt API")
                return True
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error connecting to Neovolt API: %s", error)
            return await self._async_login_fallback()
    
    async def _async_login_fallback(self) -> bool:
        """Fallback login method using form data with unencrypted password."""
        _LOGGER.debug("Trying fallback login with unencrypted password")
        
        login_url = f"{self.base_url}/api/usercenter/cloud/user/login"
        
        # Form data with original password
        form_data = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.post(
                    url=login_url,
                    data=form_data
                )
                
                if response.status != 200:
                    if response.status == 429:
                        _LOGGER.warning("Rate limited fetching battery data, backing off for %ss", RATE_LIMIT_BACKOFF_SECONDS)
                        await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                        return None
                    _LOGGER.error(
                        "Fallback login failed with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    return False
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    _LOGGER.error(
                        "Fallback login failed with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return False
                
                # Extract token - handle different response formats
                if "token" in result:
                    self.token = result["token"]
                elif "data" in result and result["data"] and "token" in result["data"]:
                    self.token = result["data"]["token"]
                else:
                    _LOGGER.error("No token found in fallback login response")
                    return False
                
                _LOGGER.debug("Successfully logged in with fallback method")
                return True
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error connecting to Neovolt API with fallback method: %s", error)
            return False
    
    async def async_get_device_list(self) -> Optional[Dict[str, Any]]:
        """Get the list of devices."""
        if not self.token:
            if not await self.async_login():
                return None
        
        url = f"{self.base_url}/api/devices/list"
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.get(
                    url=url,
                    headers=self._get_auth_headers()
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to get device list with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    
                    # Try refreshing token and retrying the request
                    if response.status == 401:
                        if await self.async_login():
                            return await self.async_get_device_list()
                    
                    return None
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    # Check for session expiry
                    if result.get("code") == 6069:
                        _LOGGER.warning("Session expired (code 6069), attempting to re-login")
                        if await self.async_login():
                            return await self.async_get_device_list()
                    
                    _LOGGER.error(
                        "Failed to get device list with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return None
                
                return result.get("data")
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error fetching device list: %s", error)
            return None
    
    async def async_get_battery_data(self, station_id: str = None) -> Optional[Dict[str, Any]]:
        """Get data for a specific battery using the new API endpoint."""
        if not self.token:
            if not await self.async_login():
                return None
        
        # First get the real-time power data
        url = f"{self.base_url}/api/report/energyStorage/getLastPowerData"
        
        params = {
            "sysSn": "All",
            "stationId": station_id or ""
        }
        
        # Use timezone-aware datetime to avoid midnight issues
        current_date = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
        
        headers = self._get_auth_headers()
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "language": "en-US",
            "operationDate": current_date,
            "platform": "AK9D8H",
            "System": "alphacloud"
        })
        
        try:
            battery_data = {}
            
            # Get real-time power data
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.get(
                    url=url,
                    params=params,
                    headers=headers
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to get battery power data with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    
                    # Try refreshing token and retrying the request
                    if response.status == 401:
                        if await self.async_login():
                            return await self.async_get_battery_data(station_id)
                    
                    return None
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    # Check for session expiry
                    if result.get("code") == 6069:
                        _LOGGER.warning("Session expired (code 6069), attempting to re-login")
                        if await self.async_login():
                            return await self.async_get_battery_data(station_id)
                    
                    _LOGGER.error(
                        "Failed to get battery power data with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return None
                
                # Store power data
                power_data = result.get("data", {})
                _LOGGER.debug("Received battery power data: %s", power_data)
                _LOGGER.debug("Available power data attributes: %s", list(power_data.keys()) if power_data else None)
                
                # Merge power data into our result
                battery_data.update(power_data)
            
            # Now get the energy statistics
            stats_url = f"{self.base_url}/api/report/energy/getEnergyStatistics"
            
            # Get date range from 2020-01-01 to tomorrow
            # TIMEZONE FIX: Using tomorrow's date as endDate prevents the midnight reset issue
            # where cumulative totals temporarily show yesterday's values for ~30 minutes
            # after midnight in timezones ahead of the API server (e.g., UTC+9:30)
            # This ensures the API always returns complete data for "today"
            now = dt_util.now()
            end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            begin_date = "2020-01-01"
            
            _LOGGER.debug("Fetching statistics for date range: %s to %s (tomorrow used for timezone fix, current time: %s)", 
                         begin_date, end_date, now.strftime("%Y-%m-%d %H:%M:%S %Z"))
            
            stats_params = {
                "sysSn": "All", 
                "stationId": station_id or "",
                "beginDate": begin_date,
                "endDate": end_date
            }
            
            _LOGGER.debug("Fetching energy statistics from: %s with params: %s", stats_url, stats_params)
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                # Add try/except for stats request to avoid breaking the whole function if stats fails
                try:
                    stats_response = await self.session.get(
                        url=stats_url,
                        params=stats_params,
                        headers=headers
                    )
                except (asyncio.TimeoutError, aiohttp.ClientError) as stats_error:
                    _LOGGER.error("Error fetching energy statistics: %s", stats_error)
                    # Return the power data we already have instead of failing completely
                    _LOGGER.debug("Returning only power data due to statistics fetch error")
                    return battery_data
                
                if stats_response.status == 200:
                    stats_result = await stats_response.json()
                    _LOGGER.debug("Energy statistics response: %s", stats_result)
                    
                    if stats_result.get("code") == 200 or stats_result.get("code") == 0:
                        stats_data = stats_result.get("data", {})
                        _LOGGER.debug("Energy statistics data fields: %s", list(stats_data.keys()) if stats_data else "No data")
                        
                        # Map the statistics data to the grid sensor names
                        if stats_data:
                            # Total solar generation
                            battery_data["Total_Solar_Generation"] = stats_data.get("epvT")
                            # Total feed in (grid export)
                            battery_data["Total_Feed_In"] = stats_data.get("eout")
                            # Total battery charge
                            battery_data["Total_Battery_Charge"] = stats_data.get("echarge")
                            # Total battery discharge
                            battery_data["Total_Battery_Discharge"] = stats_data.get("edischarge")
                            # PV to house
                            battery_data["PV_Power_House"] = stats_data.get("epv2load")
                            # PV charging battery
                            battery_data["PV_Charging_Battery"] = stats_data.get("epvcharge")
                            # Total house consumption
                            battery_data["Total_House_Consumption"] = stats_data.get("eload")
                            # Grid charging battery
                            battery_data["Grid_Based_Battery_Charge"] = stats_data.get("egridCharge")
                            # Grid power consumption
                            battery_data["Grid_Power_Consumption"] = stats_data.get("einput")
                    elif stats_result.get("code") == 6069:
                        # Session expired while fetching statistics
                        _LOGGER.warning("Session expired (code 6069) during statistics fetch, attempting to re-login")
                        if await self.async_login():
                            return await self.async_get_battery_data(station_id)
                    else:
                        _LOGGER.error(
                            "Failed to get energy statistics with code %s: %s", 
                            stats_result.get("code"), 
                            stats_result.get("msg")
                        )
                else:
                    _LOGGER.error(
                        "Failed to get energy statistics with status %s", 
                        stats_response.status
                    )
            
            # Now get today's stats
            today_url = f"{self.base_url}/api/stable/home/getSumDataForCustomer"
            today_date = now.strftime("%Y-%m-%d")
            
            today_params = {
                "sn": "All",
                "stationId": station_id or "",
                "tday": today_date
            }
            
            _LOGGER.debug("Fetching today's stats from: %s with params: %s", today_url, today_params)
            
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                try:
                    today_response = await self.session.get(
                        url=today_url,
                        params=today_params,
                        headers=headers
                    )
                except (asyncio.TimeoutError, aiohttp.ClientError) as today_error:
                    _LOGGER.error("Error fetching today's stats: %s", today_error)
                    # Return what we have so far
                    return battery_data
                
                if today_response.status == 200:
                    today_result = await today_response.json()
                    _LOGGER.debug("Today's stats response: %s", today_result)
                    
                    if today_result.get("code") == 200:
                        today_data = today_result.get("data", {})
                        _LOGGER.debug("Today's stats data fields: %s", list(today_data.keys()) if today_data else "No data")
                        
                        # Map today's stats to battery data
                        if today_data:
                            # Energy stats for today
                            battery_data["PV_Generated_Today"] = today_data.get("epvtoday")
                            battery_data["Total_PV_Generation"] = today_data.get("epvtotal")
                            battery_data["Consumed_Today"] = today_data.get("eload")
                            battery_data["Feed_In_Today"] = today_data.get("eoutput")
                            battery_data["Grid_Import_Today"] = today_data.get("einput")
                            battery_data["Battery_Charged_Today"] = today_data.get("echarge")
                            battery_data["Battery_Discharged_Today"] = today_data.get("edischarge")
                            
                            # Percentages (multiply by 100 to get percentage)
                            self_consumption = today_data.get("eselfConsumption")
                            if self_consumption is not None:
                                battery_data["Self_Consumption"] = round(self_consumption * 100, 2)
                            
                            self_sufficiency = today_data.get("eselfSufficiency")
                            if self_sufficiency is not None:
                                battery_data["Self_Sufficiency"] = round(self_sufficiency * 100, 2)
                            
                            # Environmental stats
                            battery_data["Trees_Planted"] = today_data.get("treeNum")
                            carbon_kg = today_data.get("carbonNum")
                            if carbon_kg is not None:
                                battery_data["CO2_Reduction_Tons"] = round(carbon_kg / 1000, 2)
                            
                            # Financial (optional)
                            battery_data["Today_Income"] = today_data.get("todayIncome")
                            battery_data["Total_Income"] = today_data.get("totalIncome")
                    elif today_result.get("code") == 6069:
                        # Session expired while fetching today's stats
                        _LOGGER.warning("Session expired (code 6069) during today's stats fetch, attempting to re-login")
                        if await self.async_login():
                            return await self.async_get_battery_data(station_id)
                    else:
                        _LOGGER.error(
                            "Failed to get today's stats with code %s: %s", 
                            today_result.get("code"), 
                            today_result.get("msg")
                        )
                else:
                    _LOGGER.error(
                        "Failed to get today's stats with status %s", 
                        today_response.status
                    )

            # Now get today's statistics
            today_stats_url = f"{self.base_url}/api/report/power/staticsByDay"
            today_stats_date = now.strftime("%Y-%m-%d")
            today_stats_params = {
                "sysSn": "",
                "date": today_stats_date,
            }

            _LOGGER.debug("Fetching today's detailed stats from: %s with params: %s", today_stats_url, today_stats_params)
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                try:
                    today_stats_response = await self.session.get(
                        url=today_stats_url,
                        params=today_stats_params,
                        headers=headers
                    )
                except (asyncio.TimeoutError, aiohttp.ClientError) as today_stats_error:
                    _LOGGER.error("Error fetching today's detailed stats: %s", today_stats_error)
                    # Return what we have so far
                    return battery_data

                if today_stats_response.status == 200:
                    today_stats_result = await today_stats_response.json()
                    _LOGGER.debug("Today's detailed stats response: %s", today_stats_result)

                    if today_stats_result.get("code") == 200:
                        stats_data = today_stats_result.get("data", {})
                        _LOGGER.debug("Today's detailed stats data fields: %s", list(stats_data.keys()) if stats_data else "No data")

                        # Map today's detailed stats to battery data
                        if stats_data:
                            battery_data["PV_Generated_Today"] = stats_data.get("epvtoday")
                            battery_data["Consumed_Today"] = stats_data.get("ehomeload")
                            battery_data["Feed_In_Today"] = stats_data.get("efeedIn")
                            battery_data["Grid_Import_Today"] = stats_data.get("einput")
                            battery_data["Battery_Charged_Today"] = stats_data.get("echarge")

                            # Then we need to calculate the battery discharged
                            total_gained = battery_data["PV_Generated_Today"] + battery_data["Grid_Import_Today"]
                            total_used = battery_data["Consumed_Today"] + battery_data["Feed_In_Today"] + battery_data["Battery_Charged_Today"]
                            # Nagative value indicates discharge, but we want positive displaying
                            # Avoidng using of abs() for in case we got a positive value due to data issues
                            battery_data["Battery_Discharged_Today"] = 0 - (total_gained - total_used)
                    elif today_stats_result.get("code") == 6069:
                        # Session expired while fetching today's detailed stats
                        _LOGGER.warning("Session expired (code 6069) during today's detailed stats fetch, attempting to re-login")
                        if await self.async_login():
                            return await self.async_get_battery_data(station_id)
                    else:
                        _LOGGER.error(
                            "Failed to get today's detailed stats with code %s: %s",
                            today_stats_result.get("code"),
                            today_stats_result.get("msg")
                        )
                else:
                    _LOGGER.error(
                        "Failed to get today's detailed stats with status %s",
                        today_stats_response.status
                    )

            _LOGGER.debug("Combined battery data: %s", battery_data)
            return battery_data
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error fetching battery data: %s", error)
            return None
    
    async def async_get_inverter_list(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get the list of inverters from the API.
        
        Returns:
            List of inverter dictionaries with their SN and capabilities
        """
        if not self.token:
            if not await self.async_login():
                return None
        
        # Use the correct endpoint discovered from browser traffic
        url = f"{self.base_url}/api/stable/home/getCustomMenuEssList"
        params = {"inverterMode": "0"}
        
        # Use extended headers like the web interface
        current_date = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
        
        headers = self._get_auth_headers()
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-GB,en;q=0.9",
            "language": "en-US",
            "operationDate": current_date,
            "platform": "AK9D8H",
            "System": "alphacloud",
            "Referer": f"{self.base_url}/basicSettings/systemSettings"
        })
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.get(
                    url=url,
                    params=params,
                    headers=headers
                )
                
                if response.status != 200:
                    _LOGGER.error("Failed to get inverter list: status %s", response.status)
                    return None
                
                result = await response.json()
                
                if result.get("code") != 200:
                    _LOGGER.error("Failed to get inverter list: code %s", result.get("code"))
                    return None
                
                inverters = result.get("data", [])
                _LOGGER.info("Discovered %d inverters from API", len(inverters))
                
                # Log key info for each inverter
                for inv in inverters:
                    _LOGGER.info(
                        "Inverter: %s, onGridCap: %s, popv: %s, cobat: %s",
                        inv.get("sysSn"),
                        inv.get("onGridCap"),
                        inv.get("popv"),
                        inv.get("cobat")
                    )
                
                return inverters
                
        except Exception as e:
            _LOGGER.error("Error fetching inverter list: %s", e)
            return None
    
    async def async_get_per_inverter_data(self, inverter_sns: List[str] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Get power data for each inverter individually.
        
        Args:
            inverter_sns: List of inverter serial numbers to query. 
                          If None, will try to discover from API.
        
        Returns:
            Dict mapping inverter serial numbers to their power data
        """
        if not self.token:
            if not await self.async_login():
                return None
        
        # If no SNs provided, try to discover them
        if not inverter_sns:
            inverters = await self.async_get_inverter_list()
            if inverters:
                inverter_sns = [inv.get("sysSn") for inv in inverters if inv.get("sysSn")]
                _LOGGER.info("Auto-discovered inverters: %s", inverter_sns)
        
        if not inverter_sns:
            _LOGGER.warning("No inverter SNs available for per-inverter queries")
            return None
        
        inverter_data = {}
        
        # Use timezone-aware datetime
        current_date = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
        
        headers = self._get_auth_headers()
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "language": "en-US",
            "operationDate": current_date,
            "platform": "AK9D8H",
            "System": "alphacloud"
        })
        
        url = f"{self.base_url}/api/report/energyStorage/getLastPowerData"
        
        for sn in inverter_sns:
            try:
                params = {
                    "sysSn": sn,
                    "stationId": ""
                }
                
                async with asyncio.timeout(DEFAULT_TIMEOUT):
                    response = await self.session.get(
                        url=url,
                        params=params,
                        headers=headers
                    )
                    
                    if response.status != 200:
                        _LOGGER.warning(f"Failed to get data for inverter {sn}: status {response.status}")
                        continue
                    
                    result = await response.json()
                    
                    if result.get("code") != 0 and result.get("code") != 200:
                        _LOGGER.warning(f"Failed to get data for inverter {sn}: code {result.get('code')}")
                        continue
                    
                    data = result.get("data", {})
                    if data:
                        inverter_data[sn] = {
                            "ppv": data.get("ppv", 0),
                            "pbat": data.get("pbat", 0),
                            "pgrid": data.get("pgrid", 0),
                            "pload": data.get("pload", 0),
                            "soc": data.get("soc", 0),
                            "ppv1": data.get("ppv1", 0),
                            "ppv2": data.get("ppv2", 0),
                            "ppv3": data.get("ppv3", 0),
                            "ppv4": data.get("ppv4", 0),
                            "prealL1": data.get("prealL1", 0),
                            "prealL2": data.get("prealL2", 0),
                            "prealL3": data.get("prealL3", 0),
                            "forceChargeMode": data.get("forceChargeMode", False),
                            "inverterMode": data.get("inverterMode"),
                        }
                        _LOGGER.debug(f"Got data for inverter {sn}: PPV={data.get('ppv')}, PGrid={data.get('pgrid')}, PBat={data.get('pbat')}")
                
            except Exception as e:
                _LOGGER.error(f"Error fetching data for inverter {sn}: {e}")
                continue
        
        _LOGGER.debug(f"Per-inverter data: {inverter_data}")
        return inverter_data if inverter_data else None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get the authentication headers."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
    
    async def async_get_battery_settings(self):
        """Get current battery settings and cache them."""
        try:
            from .settings import BatterySettingsAPI
            
            settings_api = BatterySettingsAPI(self)
            settings = await settings_api.fetch_current_settings()
            
            if settings:
                self._settings_cache = settings
                _LOGGER.debug("Cached battery settings: %s", settings)
            
            return settings
            
        except Exception as error:
            _LOGGER.error("Error fetching battery settings: %s", error)
            return None

    async def async_force_charge(
        self,
        system_id: str,
        sys_sn: Optional[str] = None,
        limit: int = 95,
        charge_power: Optional[int] = None,
    ) -> bool:
        """Start force charge for a system."""
        payload: Dict[str, Any] = {
            "id": system_id,
            "batUseCap": int(limit),
        }
        if sys_sn:
            payload["sysSn"] = sys_sn
        if charge_power is not None:
            payload["chargePower"] = int(charge_power)

        response = await self._async_put("api/iterate/sysSet/forceCharge", payload)
        if response and response.get("code") == 200:
            return True
        _LOGGER.error("Force charge failed for %s (%s): %s", system_id, sys_sn, response)
        return False

    async def async_stop_force_charge(self, system_id: str) -> bool:
        """Stop force charge for a system."""
        response = await self._async_put(
            "api/iterate/sysSet/stopCharge",
            {"id": system_id},
        )
        if response and response.get("code") == 200:
            return True
        _LOGGER.error("Stop force charge failed for %s: %s", system_id, response)
        return False

    async def async_get_force_charge_status(self, system_id: str) -> Optional[bool]:
        """Get current force-charge status for a system."""
        response = await self._async_get(f"api/iterate/sysSet/getForceChargeStatus?id={system_id}")
        if response and response.get("code") == 200:
            return response.get("data")
        return None

    async def async_get_force_charge_limit(self, system_id: str) -> Optional[float]:
        """Get current force-charge limit for a system."""
        response = await self._async_get(f"api/iterate/sysSet/getForceChargeLimit?id={system_id}")
        if response and response.get("code") == 200:
            try:
                return float(response.get("data"))
            except (TypeError, ValueError):
                return None
        return None

    async def async_get_cycle_strategy(self, system_id: str) -> Optional[Dict[str, Any]]:
        """Get cycle-strategy control payload for a system."""
        response = await self._async_get(f"api/iterate/sysSet/getCycleStrategy?id={system_id}")
        if response and response.get("code") == 200:
            return response.get("data")
        return None

    async def async_get_system_detail(self, system_id: str) -> Optional[Dict[str, Any]]:
        """Get system detail for a system id."""
        response = await self._async_get(f"api/stable/essSystemData/getSystemDetail?systemId={system_id}")
        if response and response.get("code") == 200:
            return response.get("data")
        return None

    async def async_get_system_setting_menu_visible(self, sys_sn: str) -> Optional[Dict[str, Any]]:
        """Get menu/capability flags for an inverter SN."""
        response = await self._async_get(f"api/base/columnControl/getSystemSettingMenuVisible?sysSn={sys_sn}")
        if response and response.get("code") == 200:
            return response.get("data")
        return None

    async def async_detect_control_variant(self, preferred_variant: str = "auto") -> Dict[str, Any]:
        """Detect the active Byte-Watt control variant and collect related metadata."""
        result: Dict[str, Any] = {
            "configured_variant": preferred_variant,
            "detected_variant": "charge_config",
            "variant_source": "fallback",
            "system_id": None,
            "system_detail": None,
            "cycle_strategy": None,
            "force_charge_status": None,
            "force_charge_limit": None,
            "menu_visible": {},
            "summary": "legacy charge-config controls",
        }

        try:
            inverter_list = await self.async_get_inverter_list()
            if inverter_list:
                result["inverter_list"] = inverter_list
                host_candidate = inverter_list[0]
                result["system_id"] = host_candidate.get("systemId")
                result["host_sys_sn"] = host_candidate.get("sysSn")

                menu_visible = {}
                for inv in inverter_list:
                    sys_sn = inv.get("sysSn")
                    if not sys_sn:
                        continue
                    visible = await self.async_get_system_setting_menu_visible(sys_sn)
                    if visible is not None:
                        menu_visible[sys_sn] = visible
                result["menu_visible"] = menu_visible

                # Evaluate all known systems to select best cycle-strategy target.
                system_candidates = []
                for inv in inverter_list:
                    candidate_system_id = inv.get("systemId")
                    if not candidate_system_id:
                        continue
                    candidate_cycle = await self.async_get_cycle_strategy(candidate_system_id)
                    candidate_detail = await self.async_get_system_detail(candidate_system_id)
                    has_schedule = bool((candidate_cycle or {}).get("dayDischargeTimeList") or (candidate_cycle or {}).get("dayChargeTimeList"))
                    try:
                        poinv = float((candidate_cycle or {}).get("poinv") or inv.get("poinv") or (candidate_detail or {}).get("poinv") or 0)
                    except (TypeError, ValueError):
                        poinv = 0.0
                    system_candidates.append({
                        "system_id": candidate_system_id,
                        "sys_sn": inv.get("sysSn"),
                        "has_schedule": has_schedule,
                        "poinv": poinv,
                        "cycle_strategy": candidate_cycle,
                        "system_detail": candidate_detail,
                    })

                if system_candidates:
                    host_system_id = result.get("system_id")
                    sorted_candidates = sorted(
                        system_candidates,
                        key=lambda c: (
                            0 if c["system_id"] == host_system_id else 1,
                            0 if c["has_schedule"] else 1,
                            -c["poinv"],
                            c["system_id"],
                        ),
                    )
                    target = sorted_candidates[0]
                    result["target_system_id"] = target["system_id"]
                    result["target_sys_sn"] = target["sys_sn"]
                    if target["system_id"] == host_system_id:
                        result["target_selection_source"] = "auto_host_primary"
                    elif target["has_schedule"]:
                        result["target_selection_source"] = "auto_scheduled_fallback"
                    else:
                        result["target_selection_source"] = "auto_largest_poinv_fallback"
                    result["system_candidates"] = [
                        {
                            "system_id": c["system_id"],
                            "sys_sn": c["sys_sn"],
                            "has_schedule": c["has_schedule"],
                            "poinv": c["poinv"],
                        }
                        for c in sorted_candidates
                    ]

            # Use selected target system for control-variant and cycle-strategy evaluation,
            # while still keeping the original discovered host system id in `system_id`.
            control_system_id = result.get("target_system_id") or result.get("system_id")
            if control_system_id:
                result["control_system_id"] = control_system_id
                result["system_detail"] = await self.async_get_system_detail(control_system_id)
                result["cycle_strategy"] = await self.async_get_cycle_strategy(control_system_id)
                result["force_charge_status"] = await self.async_get_force_charge_status(control_system_id)
                result["force_charge_limit"] = await self.async_get_force_charge_limit(control_system_id)

            cycle_strategy = result.get("cycle_strategy") or {}
            result["cycle_charge_active"] = bool(
                (cycle_strategy.get("gridChargeCycle") or 0) == 1
                and len(cycle_strategy.get("dayChargeTimeList") or []) > 0
            )
            result["cycle_discharge_active"] = bool(
                (cycle_strategy.get("ctrDisCycle") or 0) == 1
                and len(cycle_strategy.get("dayDischargeTimeList") or []) > 0
            )
            result["cycle_charge_count"] = len(cycle_strategy.get("dayChargeTimeList") or [])
            result["cycle_discharge_count"] = len(cycle_strategy.get("dayDischargeTimeList") or [])
            result["cycle_charge_windows_json"] = f"{len(cycle_strategy.get('dayChargeTimeList') or [])} windows"
            result["cycle_discharge_windows_json"] = f"{len(cycle_strategy.get('dayDischargeTimeList') or [])} windows"
            first_charge = (cycle_strategy.get("dayChargeTimeList") or [None])[0]
            first_discharge = (cycle_strategy.get("dayDischargeTimeList") or [None])[0]
            result["cycle_charge_start"] = first_charge.get("beginTime") if first_charge else None
            result["cycle_charge_end"] = first_charge.get("endTime") if first_charge else None
            result["cycle_discharge_start"] = first_discharge.get("beginTime") if first_discharge else None
            result["cycle_discharge_end"] = first_discharge.get("endTime") if first_discharge else None
            if cycle_strategy and any(
                cycle_strategy.get(key) not in (None, 0, [], {})
                for key in ["dayChargeTimeList", "dayDischargeTimeList", "weekChargeTimeList", "weekDischargeTimeList", "gridChargeCycle", "ctrDisCycle"]
            ):
                if first_discharge:
                    summary = (
                        "cycle-strategy controls active "
                        f"({first_discharge.get('beginTime')}->{first_discharge.get('endTime')}, "
                        f"limit={first_discharge.get('chargeLimit')}, power={first_discharge.get('chargePower')})"
                    )
                else:
                    summary = "cycle-strategy controls active"
                result["detected_variant"] = "cycle_strategy"
                result["variant_source"] = "cycle_strategy_endpoint"
                result["summary"] = summary
            else:
                result["detected_variant"] = "charge_config"
                result["variant_source"] = "charge_config_endpoint"
                result["summary"] = "legacy charge-config controls active"

            if preferred_variant and preferred_variant != "auto":
                result["effective_variant"] = preferred_variant
                result["variant_source"] = "user_config"
            else:
                result["effective_variant"] = result["detected_variant"]

            self._control_variant_data = result
            return result
        except Exception as error:
            _LOGGER.error("Error detecting control variant: %s", error)
            if preferred_variant and preferred_variant != "auto":
                result["effective_variant"] = preferred_variant
                result["variant_source"] = "user_config_fallback"
            else:
                result["effective_variant"] = result["detected_variant"]
            self._control_variant_data = result
            return result

    async def async_update_cycle_strategy(
        self,
        system_id: str,
        charge_windows: Optional[List[Dict[str, Any]]] = None,
        discharge_windows: Optional[List[Dict[str, Any]]] = None,
        charge_start_time: str = None,
        charge_end_time: str = None,
        charge_cap: int = None,
        charge_power: int = None,
        charge_enabled: bool = None,
        discharge_start_time: str = None,
        discharge_end_time: str = None,
        minimum_soc: int = None,
        discharge_power: int = None,
        discharge_enabled: bool = None,
    ) -> bool:
        """Update the primary cycle-strategy discharge window.

        This currently supports a conservative subset of cycle strategy fields,
        preserving all other server-provided values.
        """
        try:
            current = await self.async_get_cycle_strategy(system_id)
            if not current:
                _LOGGER.error("Unable to fetch current cycle strategy for %s", system_id)
                return False

            payload = dict(current)
            payload["id"] = system_id

            charge_list = list(payload.get("dayChargeTimeList") or [])
            discharge_list = list(payload.get("dayDischargeTimeList") or [])

            if charge_windows is not None:
                charge_list = _normalize_cycle_windows(
                    charge_windows,
                    default_power=int(payload.get("poinv") or 5000),
                    default_limit=float(charge_cap or 80),
                )
                payload["gridChargeCycle"] = 1 if charge_list else 0

            if discharge_windows is not None:
                discharge_list = _normalize_cycle_windows(
                    discharge_windows,
                    default_power=int(payload.get("poinv") or 5000),
                    default_limit=float(minimum_soc or payload.get("batUseCap") or 10),
                )
                payload["ctrDisCycle"] = 1 if discharge_list else 0

            if charge_windows is None and charge_enabled is False:
                payload["gridChargeCycle"] = 0
                charge_list = []
            elif charge_windows is None and any(v is not None for v in [charge_start_time, charge_end_time, charge_cap, charge_power, charge_enabled]):
                payload["gridChargeCycle"] = 1 if charge_enabled is not False else 0
                if not charge_list:
                    charge_list = [{
                        "chargeLimit": float(charge_cap or 80),
                        "beginTime": charge_start_time or "00:00",
                        "endTime": charge_end_time or "00:00",
                        "sort": 1,
                        "chargePower": int(charge_power or payload.get("poinv") or 5000),
                        "weeks": [7, 1, 2, 3, 4, 5, 6],
                        "feedMode": 0,
                        "equipGroupId": 0,
                        "feedPower": 0,
                    }]

                primary_charge = dict(charge_list[0])
                if charge_start_time is not None:
                    primary_charge["beginTime"] = charge_start_time
                if charge_end_time is not None:
                    primary_charge["endTime"] = charge_end_time
                if charge_cap is not None:
                    primary_charge["chargeLimit"] = float(charge_cap)
                if charge_power is not None:
                    primary_charge["chargePower"] = int(charge_power)
                primary_charge.setdefault("sort", 1)
                primary_charge.setdefault("weeks", [7, 1, 2, 3, 4, 5, 6])
                primary_charge.setdefault("feedMode", 0)
                primary_charge.setdefault("equipGroupId", 0)
                primary_charge.setdefault("feedPower", 0)
                charge_list[0] = primary_charge

            if discharge_windows is None and discharge_enabled is False:
                payload["ctrDisCycle"] = 0
                discharge_list = []
            elif discharge_windows is None:
                payload["ctrDisCycle"] = 1
                if not discharge_list:
                    discharge_list = [{
                        "chargeLimit": float(payload.get("batUseCap", 10)),
                        "beginTime": discharge_start_time or "16:00",
                        "endTime": discharge_end_time or "07:15",
                        "sort": 1,
                        "chargePower": int(discharge_power or payload.get("poinv") or 5000),
                        "weeks": [7, 1, 2, 3, 4, 5, 6],
                        "feedMode": 0,
                        "equipGroupId": 0,
                        "feedPower": 0,
                    }]

                primary = dict(discharge_list[0])
                if discharge_start_time is not None:
                    primary["beginTime"] = discharge_start_time
                if discharge_end_time is not None:
                    primary["endTime"] = discharge_end_time
                if minimum_soc is not None:
                    primary["chargeLimit"] = float(minimum_soc)
                    payload["batUseCap"] = float(minimum_soc)
                if discharge_power is not None:
                    primary["chargePower"] = int(discharge_power)
                primary.setdefault("sort", 1)
                primary.setdefault("weeks", [7, 1, 2, 3, 4, 5, 6])
                primary.setdefault("feedMode", 0)
                primary.setdefault("equipGroupId", 0)
                primary.setdefault("feedPower", 0)
                discharge_list[0] = primary

            charge_list = sorted(charge_list, key=lambda item: int(item.get("sort", 0)))
            discharge_list = sorted(discharge_list, key=lambda item: int(item.get("sort", 0)))

            payload["dayChargeTimeList"] = charge_list
            payload["dayDischargeTimeList"] = discharge_list
            payload["chargeTimeList"] = charge_list if charge_list else None
            payload["dischargeTimeList"] = discharge_list if discharge_list else None

            _LOGGER.info(
                "Updating cycle strategy for %s with %s charge windows and %s discharge windows",
                system_id,
                len(charge_list),
                len(discharge_list),
            )
            _LOGGER.debug(
                "Cycle strategy payload summary: %s",
                json.dumps(
                    {
                        "id": payload.get("id"),
                        "gridChargeCycle": payload.get("gridChargeCycle"),
                        "ctrDisCycle": payload.get("ctrDisCycle"),
                        "chargeTimeList": payload.get("chargeTimeList"),
                        "dischargeTimeList": payload.get("dischargeTimeList"),
                    }
                )[:4000],
            )

            endpoint = "api/iterate/sysSet/setCycleStrategy"
            response = await self._async_put(endpoint, payload)
            if response and response.get("code") == 200 and response.get("msg") == "Success":
                _LOGGER.info("Successfully updated cycle strategy for %s", system_id)
                return True

            _LOGGER.error("Failed to update cycle strategy for %s: %s", system_id, response)
            return False
        except Exception as error:
            _LOGGER.error("Error updating cycle strategy for %s: %s", system_id, error)
            return False
    
    async def async_update_battery_settings(self, 
                                          discharge_start_time: str = None,
                                          discharge_end_time: str = None,
                                          charge_start_time: str = None,
                                          charge_end_time: str = None,
                                          charge_start_time_2: str = None,
                                          charge_end_time_2: str = None,
                                          discharge_start_time_2: str = None,
                                          discharge_end_time_2: str = None,
                                          minimum_soc: int = None,
                                          charge_cap: int = None,
                                          ups_reserve: int = None,
                                          charge_mode_setting: int = None,
                                          export_limit_w1: int = None,
                                          export_limit_w2: int = None,
                                          discharge_time_control: bool = None,
                                          grid_charging: bool = None) -> bool:
        """Update battery settings."""
        try:
            # Import the settings API
            from .settings import BatterySettingsAPI
            
            # Create settings API instance
            settings_api = BatterySettingsAPI(self)
            
            # Use the async method directly
            result = await settings_api.update_battery_settings(
                discharge_start_time=discharge_start_time,
                discharge_end_time=discharge_end_time,
                charge_start_time=charge_start_time,
                charge_end_time=charge_end_time,
                charge_start_time_2=charge_start_time_2,
                charge_end_time_2=charge_end_time_2,
                discharge_start_time_2=discharge_start_time_2,
                discharge_end_time_2=discharge_end_time_2,
                minimum_soc=minimum_soc,
                charge_cap=charge_cap,
                ups_reserve=ups_reserve,
                charge_mode_setting=charge_mode_setting,
                export_limit_w1=export_limit_w1,
                export_limit_w2=export_limit_w2,
                discharge_time_control=discharge_time_control,
                grid_charging=grid_charging,
            )
            
            # If successful, set fresh update flag and schedule auto-fetch from API
            if result:
                # Set fresh update flag to prevent coordinator from overwriting
                self._fresh_settings_update = True
                self._settings_update_time = dt_util.utcnow()
                _LOGGER.debug("Settings update successful, scheduling auto-fetch from API in 3 seconds")
                
                # Schedule auto-fetch with delay to allow server propagation
                asyncio.create_task(self._auto_fetch_updated_settings())
            
            return result
            
        except Exception as error:
            _LOGGER.error("Error updating battery settings: %s", error)
            return False
    
    async def _auto_fetch_updated_settings(self):
        """Auto-fetch updated settings from API after successful update with delay."""
        try:
            # Wait 3 seconds to allow server propagation
            await asyncio.sleep(3)
            
            _LOGGER.debug("Auto-fetching updated settings from API after successful update")
            
            # Fetch fresh settings from API
            from .settings import BatterySettingsAPI
            settings_api = BatterySettingsAPI(self)
            settings = await settings_api.fetch_current_settings()
            
            if settings:
                self._settings_cache = settings
                _LOGGER.debug("Auto-fetch successful: updated cache with fresh settings from API")
            else:
                _LOGGER.warning("Auto-fetch failed: could not get updated settings from API")
                
        except Exception as ex:
            _LOGGER.error(f"Error during auto-fetch of updated settings: {ex}")
        finally:
            # Clear fresh update flag after auto-fetch attempt (success or failure)
            # This ensures coordinator can fetch settings again after some time
            try:
                # Clear flag after 30 more seconds as safety net
                await asyncio.sleep(30)
                self._fresh_settings_update = False
                _LOGGER.debug("Cleared fresh_settings_update flag after 30 second safety timeout")
            except asyncio.CancelledError:
                # Handle task cancellation gracefully
                self._fresh_settings_update = False
                _LOGGER.debug("Auto-fetch task cancelled, cleared fresh_settings_update flag")
            except Exception as ex:
                _LOGGER.error(f"Error during flag cleanup: {ex}")
                self._fresh_settings_update = False
    
    def has_fresh_settings_update(self) -> bool:
        """Check if we recently updated settings and should skip coordinator fetch."""
        if not self._fresh_settings_update:
            return False
            
        # Check if update was recent (within last 60 seconds)
        if self._settings_update_time:
            time_diff = dt_util.utcnow() - self._settings_update_time
            if time_diff.total_seconds() > 60:
                self._fresh_settings_update = False
                _LOGGER.debug("Fresh settings update flag expired after 60 seconds")
                return False
                
        return True
    
    async def _async_get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make an async GET request."""
        if not self.token and not await self.async_login():
            return None
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_auth_headers()
        
        try:
            async with self.session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT) as response:
                if response.status == 429:
                    _LOGGER.warning("Rate limited on GET %s, backing off for %ss", endpoint, RATE_LIMIT_BACKOFF_SECONDS)
                    await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    return None
                if response.status == 401:
                    _LOGGER.warning("GET %s returned 401, refreshing token", endpoint)
                    self.token = None
                    if await self.async_login():
                        return await self._async_get(endpoint)
                    return None
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("GET request failed with status %s", response.status)
                    return None
        except Exception as error:
            _LOGGER.error("Error making GET request: %s", error)
            return None
    
    async def _async_post(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make an async POST request."""
        if not self.token and not await self.async_login():
            return None
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_auth_headers()
        # Add specific headers for settings update
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "language": "en-US",
            "platform": "AK9D8H",
            "System": "alphacloud"
        })
        
        try:
            async with self.session.post(url, headers=headers, json=data, timeout=DEFAULT_TIMEOUT) as response:
                if response.status == 429:
                    _LOGGER.warning("Rate limited on POST %s, backing off for %ss", endpoint, RATE_LIMIT_BACKOFF_SECONDS)
                    await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    return None
                if response.status == 401:
                    _LOGGER.warning("POST %s returned 401, refreshing token", endpoint)
                    self.token = None
                    if await self.async_login():
                        return await self._async_post(endpoint, data)
                    return None
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("POST request failed with status %s for URL %s", response.status, url)
                    _LOGGER.error("Request headers: %s", headers)
                    _LOGGER.error("Request data: %s", data)
                    response_text = await response.text()
                    _LOGGER.error("Response text: %s", response_text)
                    return None
        except Exception as error:
            _LOGGER.error("Error making POST request: %s", error)
            return None
    
    async def _async_put(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make an async PUT request."""
        if not self.token and not await self.async_login():
            return None
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_auth_headers()
        # Add specific headers for settings update
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "language": "en-US",
            "platform": "AK9D8H",
            "System": "alphacloud"
        })
        
        try:
            async with self.session.put(url, headers=headers, json=data, timeout=DEFAULT_TIMEOUT) as response:
                if response.status == 429:
                    _LOGGER.warning("Rate limited on PUT %s, backing off for %ss", endpoint, RATE_LIMIT_BACKOFF_SECONDS)
                    await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    return None
                if response.status == 401:
                    _LOGGER.warning("PUT %s returned 401, refreshing token", endpoint)
                    self.token = None
                    if await self.async_login():
                        return await self._async_put(endpoint, data)
                    return None
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("PUT request failed with status %s for URL %s", response.status, url)
                    _LOGGER.error("Request headers: %s", headers)
                    _LOGGER.error("Request data: %s", data)
                    response_text = await response.text()
                    _LOGGER.error("Response text: %s", response_text)
                    return None
        except Exception as error:
            _LOGGER.error("Error making PUT request: %s", error)
            return None
