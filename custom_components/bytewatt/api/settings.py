"""Battery settings API interface for Byte-Watt integration."""
import asyncio
import logging
from typing import Optional, Dict, Any

from homeassistant.util import dt as dt_util

from ..models import CycleStrategy
from ..utilities.time_utils import sanitize_time_format
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)


class BatterySettingsAPI:
    """API client for battery cycle strategy settings.

    Uses getCycleStrategy / setCycleStrategy — the endpoints the
    Byte-Watt website actually uses.
    """

    GET_ENDPOINT = "api/iterate/sysSet/getCycleStrategy?id="
    PUT_ENDPOINT = "api/iterate/sysSet/setCycleStrategy"

    def __init__(self, api_client: 'NeovoltClient'):
        self.api_client = api_client
        self._settings_cache: Optional[CycleStrategy] = None
        self._settings_loaded = False

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch_current_settings(self, max_retries: int = 3, retry_delay: int = 1) -> Optional[CycleStrategy]:
        """Fetch cycle strategy from the API and cache it."""
        for attempt in range(max_retries):
            response = await self.api_client._async_get(self.GET_ENDPOINT)

            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            if response.get("code") == 6069:
                _LOGGER.warning("Session expired fetching cycle strategy, re-logging in")
                if await self.api_client.async_login():
                    response = await self.api_client._async_get(self.GET_ENDPOINT)

            if response and response.get("code") == 200 and "data" in response:
                settings = CycleStrategy.from_api_response(response["data"])
                settings.last_updated = dt_util.utcnow().isoformat()
                self._settings_cache = settings
                self._settings_loaded = True
                _LOGGER.debug(
                    "Fetched cycle strategy: charge=%s-%s, discharge=%s-%s, batUseCap=%.0f%%",
                    settings.time_chaf1a, settings.time_chae1a,
                    settings.time_disf1a, settings.time_dise1a,
                    settings.bat_use_cap,
                )
                return settings

            _LOGGER.error("Unexpected response fetching cycle strategy (attempt %d/%d): %s",
                          attempt + 1, max_retries, response)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return self._settings_cache  # cached fallback

    async def get_current_settings(self) -> CycleStrategy:
        """Return cached settings, fetching if not yet loaded."""
        if not self._settings_loaded or self._settings_cache is None:
            result = await self.fetch_current_settings()
            if result:
                return result
        return self._settings_cache or CycleStrategy()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_battery_settings(self,
                                      discharge_start_time: str = None,
                                      discharge_end_time: str = None,
                                      charge_start_time: str = None,
                                      charge_end_time: str = None,
                                      minimum_soc: int = None,
                                      charge_cap: int = None,
                                      discharge_time_control: bool = None,
                                      grid_charging: bool = None,
                                      max_retries: int = 5,
                                      retry_delay: int = 1) -> bool:
        """Merge changes into current settings and PUT to the API."""
        current = await self.get_current_settings()

        # Apply time changes via the alias properties
        if charge_start_time:
            sanitized = sanitize_time_format(charge_start_time)
            if sanitized:
                current.time_chaf1a = sanitized

        if charge_end_time:
            sanitized = sanitize_time_format(charge_end_time)
            if sanitized:
                current.time_chae1a = sanitized

        if discharge_start_time:
            sanitized = sanitize_time_format(discharge_start_time)
            if sanitized:
                current.time_disf1a = sanitized

        if discharge_end_time:
            sanitized = sanitize_time_format(discharge_end_time)
            if sanitized:
                current.time_dise1a = sanitized

        if minimum_soc is not None:
            current.bat_use_cap = float(minimum_soc)

        if charge_cap is not None:
            current.bat_high_cap = str(charge_cap)

        if discharge_time_control is not None:
            current.ctr_dis_cycle = 1 if discharge_time_control else 0

        if grid_charging is not None:
            current.grid_charge_cycle = 1 if grid_charging else 0

        return await self._send_settings(current, max_retries, retry_delay)

    async def _send_settings(self, settings: CycleStrategy,
                             max_retries: int = 5, retry_delay: int = 1) -> bool:
        """PUT settings to the API."""
        payload = settings.to_dict()

        for attempt in range(max_retries):
            response = await self.api_client._async_put(self.PUT_ENDPOINT, payload)

            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            if response.get("code") == 6069:
                _LOGGER.warning("Session expired sending cycle strategy, re-logging in")
                if await self.api_client.async_login():
                    response = await self.api_client._async_put(self.PUT_ENDPOINT, payload)

            if response and response.get("code") == 200 and response.get("msg") == "Success":
                self._settings_cache = settings
                self._settings_loaded = True
                _LOGGER.info("Cycle strategy updated successfully")
                return True

            _LOGGER.error("Failed to update cycle strategy (attempt %d/%d): %s",
                          attempt + 1, max_retries, response)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return False

    # Legacy method kept for backward compatibility
    async def set_battery_settings(self, end_discharge="23:00", max_retries: int = 5, retry_delay: int = 1) -> bool:
        return await self.update_battery_settings(
            discharge_end_time=sanitize_time_format(end_discharge),
            max_retries=max_retries,
            retry_delay=retry_delay,
        )


# ---------------------------------------------------------------------------
# Grid feed-in settings API (unchanged from previous work)
# ---------------------------------------------------------------------------

class GridFeedInSettingsAPI:
    """API client for grid feed-in control settings."""

    GET_ENDPOINT = "api/iterate/sysSet/getFeedStrategyList"
    POST_ENDPOINT = "api/iterate/sysSet/saveFeedStrategy"
    SYSTEM_LIST_ENDPOINT = "api/stable/home/getCustomMenuEssList?inverterMode=0"

    def __init__(self, api_client: 'NeovoltClient'):
        self.api_client = api_client
        self._cache = None

    async def _get_system_id(self) -> str:
        """Return the configured Host inverter systemId.

        Uses the value set during config flow setup. Falls back to fetching
        the list and picking the first entry for single-inverter setups or
        legacy configs that predate the inverter selection step.
        """
        # Use the pre-configured value if available
        if getattr(self.api_client, "host_system_id", ""):
            return self.api_client.host_system_id

        # Fallback: fetch list and take first entry (single inverter or legacy)
        _LOGGER.warning(
            "No host_system_id configured — fetching inverter list and using first entry. "
            "Re-configure the integration to select the correct Host inverter."
        )
        response = await self.api_client._async_get(self.SYSTEM_LIST_ENDPOINT)
        if response and response.get("code") == 200:
            data = response.get("data") or []
            if data:
                system_id = data[0].get("systemId", "")
                _LOGGER.warning("Using systemId=%s as fallback", system_id)
                return system_id
        _LOGGER.error("Could not resolve systemId for grid feed-in")
        return ""

    async def fetch_current_settings(self, max_retries: int = 3, retry_delay: int = 1):
        from ..models import GridFeedInSettings

        system_id = await self._get_system_id()
        if not system_id:
            return self._cache

        endpoint = f"{self.GET_ENDPOINT}?id={system_id}"

        for attempt in range(max_retries):
            response = await self.api_client._async_get(endpoint)

            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            if response.get("code") == 6069:
                if await self.api_client.async_login():
                    response = await self.api_client._async_get(endpoint)

            if response and response.get("code") == 200 and "data" in response:
                settings = GridFeedInSettings.from_api_response(response["data"], system_id)
                self._cache = settings
                return settings

            _LOGGER.error("Unexpected response fetching grid feed-in (attempt %d/%d): %s",
                          attempt + 1, max_retries, response)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return self._cache

    async def update_settings(self,
                              enabled: bool = None,
                              cutoff_soc: float = None,
                              slot_index: int = None,
                              slot_start: str = None,
                              slot_end: str = None,
                              slot_power: int = None,
                              max_retries: int = 5,
                              retry_delay: int = 1) -> bool:
        from ..models import GridFeedInSettings, GridFeedInSlot

        current = await self.fetch_current_settings()
        if current is None:
            current = GridFeedInSettings()

        if enabled is not None:
            current.enabled = enabled
        if cutoff_soc is not None:
            current.battery_feed_cutoff_soc = float(cutoff_soc)
        if slot_index is not None:
            while len(current.slots) <= slot_index:
                current.slots.append(GridFeedInSlot(sort=len(current.slots) + 1))
            slot = current.slots[slot_index]
            if slot_start is not None:
                slot.start = slot_start
            if slot_end is not None:
                slot.end = slot_end
            if slot_power is not None:
                slot.feed_power = slot_power

        payload = current.to_dict()

        for attempt in range(max_retries):
            response = await self.api_client._async_post(self.POST_ENDPOINT, payload)

            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            if response.get("code") == 6069:
                if await self.api_client.async_login():
                    response = await self.api_client._async_post(self.POST_ENDPOINT, payload)

            if response and response.get("code") == 200:
                self._cache = current
                _LOGGER.info("Grid feed-in settings saved successfully")
                return True

            _LOGGER.error("Failed to save grid feed-in (attempt %d/%d): %s",
                          attempt + 1, max_retries, response)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return False