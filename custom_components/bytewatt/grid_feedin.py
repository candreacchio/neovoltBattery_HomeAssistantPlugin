"""Grid Feed-in Control entities for the Byte-Watt integration.

Entities go through SettingsManager; the Submit button pushes the
staged payload to the API. There is no per-entity API write path.
"""
from __future__ import annotations

import logging
from datetime import time
from typing import Any, Optional

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FEEDIN_MAX_POWER_W
from .coordinator import ByteWattDataUpdateCoordinator
from .settings_manager import SettingsManager, SettingsValidationError

_LOGGER = logging.getLogger(__name__)

# Only Time Period 1 is exposed as entities. Services support up to 6.
TIME_PERIOD_1 = 0


def _parse_time(time_str: str) -> Optional[time]:
    if not time_str or ":" not in time_str:
        return None
    try:
        hour, minute = time_str.split(":", 1)
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return None


def _fmt_time(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


class _FeedInBase(CoordinatorEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        manager: SettingsManager,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._manager = manager

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
        }

    @property
    def available(self) -> bool:
        return self._manager.feedin_cache is not None


class ByteWattGridFeedInSwitch(_FeedInBase, SwitchEntity):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(coordinator, config_entry, manager)
        self._attr_name = "Grid Feed-in Function"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_enabled"
        self._attr_icon = "mdi:transmission-tower-export"

    @property
    def is_on(self) -> Optional[bool]:
        val = self._manager.effective_feedin("enabled")
        return bool(val) if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._stage(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._stage(False)

    async def _stage(self, state: bool) -> None:
        try:
            self._manager.stage_feedin("enabled", state)
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class ByteWattGridFeedInCutoffSOC(_FeedInBase, NumberEntity):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(coordinator, config_entry, manager)
        self._attr_name = "Grid Feed-in Discharging Cutoff SOC"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_cutoff_soc"
        self._attr_icon = "mdi:battery-arrow-down"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = NumberDeviceClass.BATTERY

    @property
    def native_value(self) -> Optional[float]:
        val = self._manager.effective_feedin("cutoff_soc")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            self._manager.stage_feedin("cutoff_soc", value)
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class _FeedInSlotBase(_FeedInBase):
    """Shared availability for Time Period 1 slot entities."""

    @property
    def available(self) -> bool:
        return self._manager.feedin_slot_available(TIME_PERIOD_1)


class ByteWattGridFeedInSlotPower(_FeedInSlotBase, NumberEntity):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(coordinator, config_entry, manager)
        self._attr_name = "Grid Feed-in Time1 Power"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_slot0_power"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_native_min_value = 0
        self._attr_native_max_value = FEEDIN_MAX_POWER_W
        self._attr_native_step = 100
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = NumberDeviceClass.POWER

    @property
    def native_value(self) -> Optional[float]:
        val = self._manager.effective_feedin_slot(TIME_PERIOD_1, "power")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            self._manager.stage_feedin_slot(TIME_PERIOD_1, "power", value)
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class ByteWattGridFeedInSlotStartTime(_FeedInSlotBase, TimeEntity):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(coordinator, config_entry, manager)
        self._attr_name = "Grid Feed-in Time1 Start"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_slot0_start"
        self._attr_icon = "mdi:clock-start"

    @property
    def native_value(self) -> Optional[time]:
        val = self._manager.effective_feedin_slot(TIME_PERIOD_1, "start")
        return _parse_time(val) if val else None

    async def async_set_value(self, value: time) -> None:
        try:
            self._manager.stage_feedin_slot(TIME_PERIOD_1, "start", _fmt_time(value))
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class ByteWattGridFeedInSlotEndTime(_FeedInSlotBase, TimeEntity):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(coordinator, config_entry, manager)
        self._attr_name = "Grid Feed-in Time1 End"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_slot0_end"
        self._attr_icon = "mdi:clock-end"

    @property
    def native_value(self) -> Optional[time]:
        val = self._manager.effective_feedin_slot(TIME_PERIOD_1, "end")
        return _parse_time(val) if val else None

    async def async_set_value(self, value: time) -> None:
        try:
            self._manager.stage_feedin_slot(TIME_PERIOD_1, "end", _fmt_time(value))
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Platform setup helpers — switch.py / number.py / time.py call into these
# ---------------------------------------------------------------------------

async def async_setup_switch_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]
    async_add_entities([ByteWattGridFeedInSwitch(coordinator, config_entry, manager)])


async def async_setup_number_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]
    async_add_entities([
        ByteWattGridFeedInCutoffSOC(coordinator, config_entry, manager),
        ByteWattGridFeedInSlotPower(coordinator, config_entry, manager),
    ])


async def async_setup_time_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]
    async_add_entities([
        ByteWattGridFeedInSlotStartTime(coordinator, config_entry, manager),
        ByteWattGridFeedInSlotEndTime(coordinator, config_entry, manager),
    ])
