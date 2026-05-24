"""High-level client wrapper for the Byte-Watt integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant

from .api.neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)


class ByteWattClient:
    """Thin wrapper exposing the low-level API client and inverter metadata.

    Settings reads/writes go through SettingsManager (in settings_manager.py),
    not through this class — historical per-setting methods have been removed.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        host_system_id: str = "",
        host_sys_sn: str = "",
    ) -> None:
        self.hass = hass
        self.username = username
        self.password = password
        self.api_client = NeovoltClient(
            hass, username, password,
            host_system_id=host_system_id,
            host_sys_sn=host_sys_sn,
        )

    async def initialize(self) -> bool:
        """Authenticate against the Byte-Watt API."""
        return await self.api_client.async_login()

    async def get_battery_data(self, station_id: Optional[str] = None) -> Dict[str, Any]:
        """Poll the real-time + cumulative battery data endpoints.

        Raises ``ByteWattAPIError`` on failure — the caller (coordinator)
        relies on this so its circuit-breaker accounting sees real failures
        instead of silently treating None as success.
        """
        return await self.api_client.async_get_battery_data(station_id)

    async def get_device_list(self) -> Optional[Dict[str, Any]]:
        return await self.api_client.async_get_device_list()

    async def fetch_inverter_list(self) -> list:
        """List the inverters on this account (config flow / migration use)."""
        return await self.api_client.fetch_inverter_list()
