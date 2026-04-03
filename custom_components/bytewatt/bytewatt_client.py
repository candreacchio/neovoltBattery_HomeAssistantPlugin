"""Client for interacting with the Byte-Watt API."""
import logging
from typing import Dict, Any, Optional, List
import asyncio

from homeassistant.core import HomeAssistant

from .api.neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)


class ByteWattClient:
    """Client for interacting with the Byte-Watt API."""
    
    def __init__(self, hass: HomeAssistant, username: str, password: str):
        """Initialize with login credentials."""
        self.hass = hass
        self.username = username
        self.password = password
        self.api_client = NeovoltClient(hass, username, password)
        self._api_lock = asyncio.Lock()
    
    async def initialize(self) -> bool:
        """Initialize or re-initialize the client."""
        async with self._api_lock:
            return await self.api_client.async_login()
    
    async def get_battery_data(self, station_id: str = None) -> Optional[Dict[str, Any]]:
        """Get battery data from the API."""
        async with self._api_lock:
            return await self.api_client.async_get_battery_data(station_id)
    
    async def get_device_list(self) -> Optional[Dict[str, Any]]:
        """Get list of devices from the API."""
        async with self._api_lock:
            return await self.api_client.async_get_device_list()
    
    async def update_battery_settings(self, 
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
        async with self._api_lock:
            return await self.api_client.async_update_battery_settings(
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
                grid_charging=grid_charging
            )

    async def detect_control_variant(self, preferred_variant: str = "auto") -> Dict[str, Any]:
        """Detect active Byte-Watt control variant."""
        async with self._api_lock:
            return await self.api_client.async_detect_control_variant(preferred_variant)

    async def update_cycle_strategy(
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
        """Update primary cycle-strategy discharge settings."""
        async with self._api_lock:
            return await self.api_client.async_update_cycle_strategy(
                system_id=system_id,
                charge_windows=charge_windows,
                discharge_windows=discharge_windows,
                charge_start_time=charge_start_time,
                charge_end_time=charge_end_time,
                charge_cap=charge_cap,
                charge_power=charge_power,
                charge_enabled=charge_enabled,
                discharge_start_time=discharge_start_time,
                discharge_end_time=discharge_end_time,
                minimum_soc=minimum_soc,
                discharge_power=discharge_power,
                discharge_enabled=discharge_enabled,
            )

    async def force_charge(
        self,
        system_id: str,
        sys_sn: Optional[str] = None,
        limit: int = 95,
        charge_power: Optional[int] = None,
    ) -> bool:
        """Force charge a specific system."""
        async with self._api_lock:
            return await self.api_client.async_force_charge(
                system_id=system_id,
                sys_sn=sys_sn,
                limit=limit,
                charge_power=charge_power,
            )

    async def stop_force_charge(self, system_id: str) -> bool:
        """Stop force charge for a specific system."""
        async with self._api_lock:
            return await self.api_client.async_stop_force_charge(system_id=system_id)

    async def get_force_charge_status(self, system_id: str) -> Optional[bool]:
        """Get force-charge status for a specific system."""
        async with self._api_lock:
            return await self.api_client.async_get_force_charge_status(system_id=system_id)

    async def get_force_charge_limit(self, system_id: str) -> Optional[float]:
        """Get force-charge limit for a specific system."""
        async with self._api_lock:
            return await self.api_client.async_get_force_charge_limit(system_id=system_id)
