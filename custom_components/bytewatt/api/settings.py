"""Stateless transport for battery + grid feed-in settings.

Endpoints, payload construction, retries, and 6069 re-login live here.
Caching, pending-diff bookkeeping, and validation live in SettingsManager.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from ..models import CycleStrategy, GridFeedInSettings

if TYPE_CHECKING:
    from .neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)

# Retry parameters — applied uniformly to GET/PUT/POST
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0


async def _with_relogin(api_client: "NeovoltClient", op):
    """Run op (a no-arg async callable returning a response dict),
    re-login once and retry if the server returns session-expiry code 6069."""
    response = await op()
    if response and response.get("code") == 6069:
        _LOGGER.warning("Session expired (code 6069), re-logging in")
        if await api_client.async_login():
            response = await op()
    return response


class BatterySettingsAPI:
    """Stateless transport for the current battery charge-config API."""

    GET_ENDPOINT = "api/iterate/sysSet/getChargeConfigInfo?id="
    PUT_ENDPOINT = "api/iterate/sysSet/updateChargeConfigInfo"

    def __init__(self, api_client: "NeovoltClient") -> None:
        self._client = api_client

    def _host_id(self) -> str:
        """Return the configured host systemId, or empty for single-inverter installs.

        The Byte-Watt API tolerates ``id=`` (empty) for accounts with one
        inverter — confirmed against HAR captures. For multi-inverter
        accounts the behaviour is undefined; we warn ONCE per process so
        operators see the signal in the log without spamming it on every
        poll. The repair-issue flow surfaces the same prompt in the UI.
        """
        host_id = getattr(self._client, "host_system_id", "") or ""
        if not host_id and not getattr(self._client, "_warned_empty_host_id", False):
            _LOGGER.warning(
                "Battery settings requests are using an empty host_system_id. "
                "This is safe for single-inverter accounts but ambiguous for "
                "multi-inverter accounts — open Settings → Devices & Services "
                "→ Byte-Watt → Reconfigure to pick the Host inverter explicitly."
            )
            self._client._warned_empty_host_id = True
        return host_id

    @staticmethod
    def _from_charge_config(data, system_id: str) -> CycleStrategy:
        """Translate the current charge-config response into CycleStrategy."""

        # CycleStrategy already contains the parsing logic for charge and
        # discharge slots. The current API uses different field names, so
        # translate those names to the model's existing API representation.
        model_data = {
            "gridChargeCycle": data.get("gridCharge", 1),
            "ctrDisCycle": data.get("ctrDis", 0),
            "batUseCap": data.get("batUseCap", 10),
            "executeCycleType": data.get("chargeModeSetting", 0),
            "upsReserve": data.get("upsReserve", 0),
            "loadcutoutEn": data.get("loadcutoutEn", 0),
            "cutoffSoc": data.get("cutoffSoc", 0),
            "wakeupSoc": data.get("wakeupSoc", 0),
            "isSupportDischargeSoc": data.get(
                "isSupportOffGridSocControl", True
            ),
            "isSupportChargerPower": True,
            "poinv": data.get("poinv", 10000),

            "dayChargeTimeList": [
                {
                    "beginTime": data.get("timeChaf1", "00:00"),
                    "endTime": data.get("timeChae1", "00:00"),
                    "chargeLimit": data.get("batHighCap", 100),
                    "chargePower": 8000,
                    "sort": 1,
                },
                {
                    "beginTime": data.get("timeChaf2", "00:00"),
                    "endTime": data.get("timeChae2", "00:00"),
                    "chargeLimit": data.get("batHighCap", 100),
                    "chargePower": 8000,
                    "sort": 2,
                },
            ],

            "dayDischargeTimeList": [
                {
                    "beginTime": data.get("timeDisf1", "00:00"),
                    "endTime": data.get("timeDise1", "00:00"),
                    "chargeLimit": data.get("batUseCap", 10),
                    "chargePower": 10000,
                    "sort": 1,
                },
                {
                    "beginTime": data.get("timeDisf2", "00:00"),
                    "endTime": data.get("timeDise2", "00:00"),
                    "chargeLimit": data.get("batUseCap", 10),
                    "chargePower": 10000,
                    "sort": 2,
                },
            ],
        }

        settings = CycleStrategy.from_api_response(model_data)
        settings.raw_data = dict(data)
        settings.host_system_id = system_id
        return settings

    @staticmethod
    def _to_charge_config(settings: CycleStrategy, system_id: str):
        """Translate CycleStrategy back to the current charge-config API."""

        # Start with the complete GET response. This preserves fields that
        # the integration does not expose, such as battery model information,
        # reserve settings, and firmware-dependent options.
        payload = dict(settings.raw_data)
        payload["id"] = system_id

        payload["gridCharge"] = settings.grid_charge_cycle
        payload["ctrDis"] = settings.ctr_dis_cycle
        payload["batUseCap"] = settings.bat_use_cap

        if settings.charge_slots:
            slot = settings.charge_slots[0]
            payload["timeChaf1"] = slot.begin_time
            payload["timeChae1"] = slot.end_time
            payload["batHighCap"] = slot.charge_limit

        if len(settings.charge_slots) > 1:
            slot = settings.charge_slots[1]
            payload["timeChaf2"] = slot.begin_time
            payload["timeChae2"] = slot.end_time

        if settings.discharge_slots:
            slot = settings.discharge_slots[0]
            payload["timeDisf1"] = slot.begin_time
            payload["timeDise1"] = slot.end_time

        if len(settings.discharge_slots) > 1:
            slot = settings.discharge_slots[1]
            payload["timeDisf2"] = slot.begin_time
            payload["timeDise2"] = slot.end_time

        payload["upsReserve"] = settings.ups_reserve
        payload["loadcutoutEn"] = settings.loadcutout_en
        payload["cutoffSoc"] = settings.cutoff_soc
        payload["wakeupSoc"] = settings.wakeup_soc

        return payload

    async def fetch_current_settings(
        self,
        max_retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> Optional[CycleStrategy]:
        endpoint = f"{self.GET_ENDPOINT}{self._host_id()}"

        for attempt in range(max_retries):
            response = await _with_relogin(
                self._client,
                lambda: self._client._async_get(endpoint),
            )

            if response and response.get("code") == 200 and "data" in response:
                settings = self._from_charge_config(
                    response["data"],
                    self._host_id(),
                )

                _LOGGER.debug(
                    "Fetched charge config (id=%s): batUseCap=%.0f%%, "
                    "%d charge slot(s), %d discharge slot(s)",
                    self._host_id(),
                    settings.bat_use_cap,
                    len(settings.charge_slots),
                    len(settings.discharge_slots),
                )
                return settings

            _LOGGER.debug(
                "Charge config fetch attempt %d/%d returned: %s",
                attempt + 1,
                max_retries,
                response,
            )

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return None

    async def put(
        self,
        settings: CycleStrategy,
        max_retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> bool:
        payload = self._to_charge_config(settings, self._host_id())

        for attempt in range(max_retries):
            response = await _with_relogin(
                self._client,
                lambda: self._client._async_put(
                    self.PUT_ENDPOINT,
                    payload,
                ),
            )

            if response and response.get("code") == 200:
                return True

            if response and response.get("code") == 9007:
                _LOGGER.warning(
                    "updateChargeConfigInfo transient error 9007 (attempt %d/%d), retrying",
                    attempt + 1, max_retries,
                )
            else:
                _LOGGER.debug(
                    "updateChargeConfigInfo attempt %d/%d returned: %s",
                    attempt + 1, max_retries,
                    response,
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return False


class GridFeedInSettingsAPI:
    """Stateless transport for getFeedStrategyList / saveFeedStrategy."""

    GET_ENDPOINT = "api/iterate/sysSet/getFeedStrategyList?id="
    POST_ENDPOINT = "api/iterate/sysSet/v2/saveFeedStrategy"

    def __init__(self, api_client: "NeovoltClient") -> None:
        self._client = api_client

    def _host_id(self) -> str:
        return getattr(self._client, "host_system_id", "") or ""

    async def fetch_current_settings(
        self,
        max_retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> Optional[GridFeedInSettings]:
        host_id = self._host_id()
        if not host_id:
            _LOGGER.debug(
                "Skipping grid feed-in fetch — no host_system_id configured. "
                "Reconfigure the integration to select the Host inverter."
            )
            return None
        endpoint = f"{self.GET_ENDPOINT}{host_id}"
        for attempt in range(max_retries):
            response = await _with_relogin(self._client, lambda: self._client._async_get(endpoint))
            if response and response.get("code") == 200 and "data" in response:
                settings = GridFeedInSettings.from_api_response(response["data"], host_id)
                _LOGGER.debug(
                    "Fetched grid feed-in (id=%s): enabled=%s, %d slot(s)",
                    host_id, bool(settings.battery_en), len(settings.slots),
                )
                return settings
            _LOGGER.debug(
                "Grid feed-in fetch attempt %d/%d returned: %s",
                attempt + 1, max_retries, response,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        return None

    async def post(
        self,
        settings: GridFeedInSettings,
        max_retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> bool:
        payload = settings.to_dict()
        payload["id"] = self._host_id()
        for attempt in range(max_retries):
            response = await _with_relogin(
                self._client, lambda: self._client._async_post(self.POST_ENDPOINT, payload)
            )
            if response and response.get("code") == 200:
                return True

            if response and response.get("code") == 9007:
                _LOGGER.warning(
                    "saveFeedStrategy transient error 9007 (attempt %d/%d), retrying",
                    attempt + 1, max_retries,
                )
            else:
                _LOGGER.debug(
                    "saveFeedStrategy attempt %d/%d returned: %s",
                    attempt + 1, max_retries,
                    response,
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        return False
