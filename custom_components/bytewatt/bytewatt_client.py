"""Client for interacting with the Byte-Watt API."""
import logging
from typing import Dict, Any, Optional, List
import asyncio

from homeassistant.core import HomeAssistant

from .api.neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)


class ByteWattClient:
    """Client for interacting with the Byte-Watt API."""
    
    def __init__(self, hass: HomeAssistant, username: str, password: str,
                 host_system_id: str = "", host_sys_sn: str = ""):
        """Initialize with login credentials."""
        self.hass = hass
        self.username = username
        self.password = password
        self.api_client = NeovoltClient(
            hass, username, password,
            host_system_id=host_system_id,
            host_sys_sn=host_sys_sn,
        )
    
    async def initialize(self) -> bool:
        """Initialize or re-initialize the client."""
        return await self.api_client.async_login()
    
    async def get_battery_data(self, station_id: str = None) -> Optional[Dict[str, Any]]:
        """Get battery data from the API."""
        return await self.api_client.async_get_battery_data(station_id)
    
    async def get_device_list(self) -> Optional[Dict[str, Any]]:
        """Get list of devices from the API."""
        return await self.api_client.async_get_device_list()
    
    async def update_battery_settings(self, 
                                    discharge_start_time: str = None,
                                    discharge_end_time: str = None,
                                    charge_start_time: str = None,
                                    charge_end_time: str = None,
                                    minimum_soc: int = None,
                                    charge_cap: int = None,
                                    discharge_time_control: bool = None,
                                    grid_charging: bool = None,
                                    charge_power: int = None,
                                    discharge_power: int = None) -> bool:
        """Update battery settings."""
        return await self.api_client.async_update_battery_settings(
            discharge_start_time=discharge_start_time,
            discharge_end_time=discharge_end_time,
            charge_start_time=charge_start_time,
            charge_end_time=charge_end_time,
            minimum_soc=minimum_soc,
            charge_cap=charge_cap,
            discharge_time_control=discharge_time_control,
            grid_charging=grid_charging,
            charge_power=charge_power,
            discharge_power=discharge_power,
        )

    async def get_grid_feedin_settings(self):
        """Get grid feed-in settings."""
        return await self.api_client.async_get_grid_feedin_settings()

    async def update_grid_feedin_settings(self,
                                          enabled: bool = None,
                                          cutoff_soc: float = None,
                                          slot_index: int = None,
                                          slot_start: str = None,
                                          slot_end: str = None,
                                          slot_power: int = None) -> bool:
        """Update grid feed-in settings."""
        return await self.api_client.async_update_grid_feedin_settings(
            enabled=enabled,
            cutoff_soc=cutoff_soc,
            slot_index=slot_index,
            slot_start=slot_start,
            slot_end=slot_end,
            slot_power=slot_power,
        )