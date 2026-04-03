"""Battery settings API interface for Byte-Watt integration."""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from homeassistant.util import dt as dt_util

from ..models import BatterySettings
from ..utilities.time_utils import sanitize_time_format
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)


class BatterySettingsAPI:
    """API client for battery settings."""
    
    def __init__(self, api_client: 'NeovoltClient'):
        """Initialize the battery settings API client."""
        self.api_client = api_client
        
        # Default settings cache (used only if API fetch fails)
        self._settings_cache = BatterySettings()
        self._settings_loaded = False
    
    def validate_settings_input(self, 
                              discharge_start_time, 
                              discharge_end_time, 
                              charge_start_time, 
                              charge_end_time, 
                              minimum_soc,
                              charge_cap=None):
        """
        Validate input parameters for battery settings.
        
        Args:
            discharge_start_time: Time to start battery discharge
            discharge_end_time: Time to end battery discharge
            charge_start_time: Time to start battery charging
            charge_end_time: Time to end battery charging
            minimum_soc: Minimum state of charge percentage
            charge_cap: Maximum charge cap percentage
            
        Returns:
            Tuple of validated values (discharge_start, discharge_end, charge_start, charge_end, min_soc, max_charge_cap)
            Invalid values will be None
        """
        # Sanitize time formats
        discharge_start = sanitize_time_format(discharge_start_time)
        discharge_end = sanitize_time_format(discharge_end_time)
        charge_start = sanitize_time_format(charge_start_time)
        charge_end = sanitize_time_format(charge_end_time)
        
        # Validate minimum SOC
        min_soc = None
        if minimum_soc is not None:
            try:
                min_soc_val = int(minimum_soc)
                if 1 <= min_soc_val <= 100:
                    min_soc = min_soc_val
                else:
                    _LOGGER.error(f"Minimum SOC must be between 1 and 100, got {minimum_soc}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid minimum SOC value: {minimum_soc}")
        
        # Validate charge cap
        max_charge_cap = None
        if charge_cap is not None:
            try:
                charge_cap_val = int(charge_cap)
                if 1 <= charge_cap_val <= 100:
                    max_charge_cap = charge_cap_val
                else:
                    _LOGGER.error(f"Charge cap must be between 1 and 100, got {charge_cap}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid charge cap value: {charge_cap}")
        
        return discharge_start, discharge_end, charge_start, charge_end, min_soc, max_charge_cap
    
    def validate_boolean_setting(self, value: any, setting_name: str) -> int:
        """
        Validate boolean setting input and convert to API integer format (0/1).
        
        Args:
            value: Boolean value to validate (can be bool, int, or string)
            setting_name: Name of the setting for logging purposes
            
        Returns:
            0 or 1 for API, or None if invalid
        """
        if value is None:
            return None
            
        try:
            # Handle different input types
            if isinstance(value, bool):
                return 1 if value else 0
            elif isinstance(value, int):
                if value in [0, 1]:
                    return value
                else:
                    _LOGGER.error(f"{setting_name} must be 0 or 1, got {value}")
                    return None
            elif isinstance(value, str):
                if value.lower() in ['true', '1', 'on', 'enabled']:
                    return 1
                elif value.lower() in ['false', '0', 'off', 'disabled']:
                    return 0
                else:
                    _LOGGER.error(f"Invalid {setting_name} value: {value}")
                    return None
            else:
                _LOGGER.error(f"Invalid {setting_name} type: {type(value)}")
                return None
        except Exception as ex:
            _LOGGER.error(f"Error validating {setting_name}: {ex}")
            return None
    
    async def fetch_current_settings(self, max_retries: int = 3, retry_delay: int = 1) -> Optional[BatterySettings]:
        """
        Fetch current battery settings directly from the API using new endpoint.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            BatterySettings if successful, None if failed
        """
        # Use new API endpoint with empty id= to get settings for all devices
        endpoint = "api/iterate/sysSet/getChargeConfigInfo?id="
        
        for attempt in range(max_retries):
            response = await self.api_client._async_get(endpoint)
            
            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            if "data" not in response or "code" not in response or response["code"] != 200:
                # Check for session expiry
                if response.get("code") == 6069:
                    _LOGGER.warning("Session expired (code 6069), attempting to re-login")
                    if await self.api_client.async_login():
                        # Retry immediately after successful re-login
                        response = await self.api_client._async_get(endpoint)
                        if response and "data" in response and response.get("code") == 200:
                            # Success! Extract the settings
                            settings = BatterySettings.from_api_response(response["data"])
                            settings.last_updated = dt_util.utcnow().isoformat()
                            
                            # Update our settings cache
                            self._settings_cache = settings
                            self._settings_loaded = True
                            
                            _LOGGER.debug(f"Successfully fetched current settings after re-login")
                            return settings
                
                _LOGGER.error(f"Unexpected response format (attempt {attempt+1}/{max_retries}): {response}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            # Success! Extract the settings
            settings = BatterySettings.from_api_response(response["data"])
            settings.last_updated = dt_util.utcnow().isoformat()
            
            # Update our settings cache
            self._settings_cache = settings
            self._settings_loaded = True
            
            _LOGGER.debug(f"Successfully fetched current settings from new API")
            _LOGGER.debug(f"Current settings: " +
                         f"Charge: {settings.time_chaf1a}-{settings.time_chae1a}, " +
                         f"Discharge: {settings.time_disf1a}-{settings.time_dise1a}, " +
                         f"Min SOC: {settings.bat_use_cap}%")
            
            return settings
        
        _LOGGER.error(f"Failed to fetch current settings after {max_retries} attempts")
        # If we failed to fetch from API, use the cached settings or defaults
        if self._settings_loaded:
            _LOGGER.warning("Using cached settings as fallback")
            return self._settings_cache
        else:
            _LOGGER.warning("Using default settings as fallback")
            return self._settings_cache
    
    async def get_current_settings(self, max_retries: int = 3, retry_delay: int = 1) -> BatterySettings:
        """
        Get current battery settings - first try API, then fallback to cache.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Current battery settings
        """
        # First try to fetch from API
        settings = await self.fetch_current_settings(max_retries, retry_delay)
        
        # If that failed but we have cached settings, use those
        if settings is None and self._settings_loaded:
            _LOGGER.warning("Using cached settings")
            return self._settings_cache
            
        # If we still don't have settings, use the defaults
        if settings is None:
            _LOGGER.warning("Using default settings")
            return self._settings_cache
            
        return settings
    
    async def update_battery_settings(self, 
                              discharge_start_time=None, 
                              discharge_end_time=None,
                              charge_start_time=None,
                              charge_end_time=None,
                              charge_start_time_2=None,
                              charge_end_time_2=None,
                              discharge_start_time_2=None,
                              discharge_end_time_2=None,
                              minimum_soc=None,
                              charge_cap=None,
                              ups_reserve=None,
                              charge_mode_setting=None,
                              export_limit_w1=None,
                              export_limit_w2=None,
                              discharge_time_control=None,
                              grid_charging=None,
                              max_retries: int = 5, 
                              retry_delay: int = 1) -> bool:
        """
        Update battery settings with API fetch to preserve existing settings.
        
        Args:
            discharge_start_time: Time to start battery discharge (format HH:MM)
            discharge_end_time: Time to end battery discharge (format HH:MM)
            charge_start_time: Time to start battery charging (format HH:MM)
            charge_end_time: Time to end battery charging (format HH:MM)
            minimum_soc: Minimum state of charge percentage to maintain (1-100)
            charge_cap: Maximum charge cap percentage (1-100)
            discharge_time_control: Enable/disable discharge time control (bool)
            grid_charging: Enable/disable grid charging (bool)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        # Validate all inputs
        discharge_start, discharge_end, charge_start, charge_end, min_soc, max_charge_cap = self.validate_settings_input(
            discharge_start_time, discharge_end_time, charge_start_time, charge_end_time, minimum_soc, charge_cap
        )
        
        # Validate boolean settings
        ctr_dis_value = self.validate_boolean_setting(discharge_time_control, "discharge_time_control")
        grid_charge_value = self.validate_boolean_setting(grid_charging, "grid_charging")
        
        # Check if any changes were made
        if (discharge_start is None and discharge_end is None and 
            charge_start is None and charge_end is None and
            charge_start_time_2 is None and charge_end_time_2 is None and
            discharge_start_time_2 is None and discharge_end_time_2 is None and
            min_soc is None and max_charge_cap is None and ups_reserve is None and
            charge_mode_setting is None and export_limit_w1 is None and export_limit_w2 is None and
            ctr_dis_value is None and grid_charge_value is None):
            _LOGGER.warning("No valid battery settings provided, nothing to update")
            return False
        
        # Get current settings from the API - this will fetch from API or use cache as fallback
        current_settings = await self.get_current_settings()
        
        # Create a copy of the current settings
        settings = current_settings
        
        # Update settings with provided values (only if they're valid)
        if discharge_start is not None:
            settings.time_disf1a = discharge_start
            _LOGGER.debug(f"Updating discharge start time to {discharge_start}")
        
        if discharge_end is not None:
            settings.time_dise1a = discharge_end
            _LOGGER.debug(f"Updating discharge end time to {discharge_end}")
        
        if charge_start is not None:
            settings.time_chaf1a = charge_start
            _LOGGER.debug(f"Updating charge start time to {charge_start}")
        
        if charge_end is not None:
            settings.time_chae1a = charge_end
            _LOGGER.debug(f"Updating charge end time to {charge_end}")

        if charge_start_time_2 is not None:
            settings.time_chaf2a = sanitize_time_format(charge_start_time_2) or settings.time_chaf2a
            _LOGGER.debug(f"Updating charge start time 2 to {settings.time_chaf2a}")

        if charge_end_time_2 is not None:
            settings.time_chae2a = sanitize_time_format(charge_end_time_2) or settings.time_chae2a
            _LOGGER.debug(f"Updating charge end time 2 to {settings.time_chae2a}")

        if discharge_start_time_2 is not None:
            settings.time_disf2a = sanitize_time_format(discharge_start_time_2) or settings.time_disf2a
            _LOGGER.debug(f"Updating discharge start time 2 to {settings.time_disf2a}")

        if discharge_end_time_2 is not None:
            settings.time_dise2a = sanitize_time_format(discharge_end_time_2) or settings.time_dise2a
            _LOGGER.debug(f"Updating discharge end time 2 to {settings.time_dise2a}")
        
        if min_soc is not None:
            settings.bat_use_cap = min_soc
            _LOGGER.debug(f"Updating minimum SOC to {min_soc}%")
        
        if max_charge_cap is not None:
            settings.bat_high_cap = str(max_charge_cap)
            _LOGGER.debug(f"Updating charge cap to {max_charge_cap}%")

        if ups_reserve is not None:
            try:
                settings.additional_fields["upsReserve"] = int(ups_reserve)
                _LOGGER.debug(f"Updating UPS reserve to {ups_reserve}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid ups_reserve value: {ups_reserve}")

        if charge_mode_setting is not None:
            try:
                settings.additional_fields["chargeModeSetting"] = int(charge_mode_setting)
                _LOGGER.debug(f"Updating charge mode setting to {charge_mode_setting}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid charge_mode_setting value: {charge_mode_setting}")

        if export_limit_w1 is not None:
            try:
                settings.additional_fields["timeExpLimW1"] = int(export_limit_w1)
                _LOGGER.debug(f"Updating export limit window 1 to {export_limit_w1}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid export_limit_w1 value: {export_limit_w1}")

        if export_limit_w2 is not None:
            try:
                settings.additional_fields["timeExpLimW2"] = int(export_limit_w2)
                _LOGGER.debug(f"Updating export limit window 2 to {export_limit_w2}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid export_limit_w2 value: {export_limit_w2}")
        
        if ctr_dis_value is not None:
            settings.ctr_dis = ctr_dis_value
            _LOGGER.debug(f"Updating discharge time control to {ctr_dis_value} ({'enabled' if ctr_dis_value else 'disabled'})")
        
        if grid_charge_value is not None:
            settings.grid_charge = grid_charge_value
            _LOGGER.debug(f"Updating grid charging to {grid_charge_value} ({'enabled' if grid_charge_value else 'disabled'})")
        
        # Send the updated settings to the server
        return await self._send_battery_settings(settings, max_retries, retry_delay)
    
    async def _send_battery_settings(self, 
                              settings: BatterySettings, 
                              max_retries: int = 5, 
                              retry_delay: int = 1) -> bool:
        """
        Internal method to send battery settings to the server.
        
        Args:
            settings: Battery settings to send
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        endpoint = "api/iterate/sysSet/updateChargeConfigInfo"
        
        for attempt in range(max_retries):
            response = await self.api_client._async_put(endpoint, settings.to_dict())
            
            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            # Check for successful response based on new API format
            if response.get("code") == 200 and response.get("msg") == "Success":
                _LOGGER.debug(f"Successfully updated battery settings using new API")
                # Update settings cache with the successfully sent settings
                self._settings_cache = settings
                self._settings_loaded = True
                
                # Log the updated settings
                _LOGGER.debug(f"Updated settings: " +
                            f"Charge: {settings.time_chaf1a}-{settings.time_chae1a}, " +
                            f"Discharge: {settings.time_disf1a}-{settings.time_dise1a}, " +
                            f"Min SOC: {settings.bat_use_cap}%")
                return True
            elif response.get("code") == 9007:
                _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {response.get('msg', 'Unknown error')}")
                # Server is reporting a network issue, let's retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            elif response.get("code") == 6069:
                # Session expired during settings update
                _LOGGER.warning("Session expired (code 6069), attempting to re-login")
                if await self.api_client.async_login():
                    # Retry immediately after successful re-login
                    response = await self.api_client._async_put(endpoint, settings.to_dict())
                    if response and response.get("code") == 200 and response.get("msg") == "Success":
                        _LOGGER.debug(f"Successfully updated battery settings after re-login")
                        # Update settings cache with the successfully sent settings
                        self._settings_cache = settings
                        self._settings_loaded = True
                        return True
                
                # If re-login or retry failed, continue to next attempt
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            else:
                _LOGGER.error(f"Unexpected response when setting battery parameters: {response}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
        
        _LOGGER.error(f"Failed to update battery settings after {max_retries} attempts")
        return False
    
    async def set_battery_settings(self, end_discharge="23:00", max_retries: int = 5, retry_delay: int = 1) -> bool:
        """
        Legacy method for backward compatibility - updates only the discharge end time.
        
        Args:
            end_discharge: Time to end battery discharge (format HH:MM)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        # Sanitize the time format
        sanitized_end_discharge = sanitize_time_format(end_discharge)
        if not sanitized_end_discharge:
            _LOGGER.error(f"Invalid end discharge time format: {end_discharge}")
            return False
            
        return await self.update_battery_settings(
            discharge_end_time=sanitized_end_discharge,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
