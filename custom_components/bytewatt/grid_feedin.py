"""Grid Feed-in Control entities for the Byte-Watt integration.

Entities write to the PendingStore instead of calling the API directly.
The Submit Settings button in pending.py pushes everything to the API.
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
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SLOT = 0  # Only manage Time Period 1


def _cache(hass, entry_id):
    try:
        client = hass.data[DOMAIN][entry_id]["client"]
        return getattr(client.api_client, "_grid_feedin_cache", None)
    except Exception:
        return None


def _parse_time(time_str: str) -> Optional[time]:
    try:
        if time_str and ":" in time_str:
            h, m = time_str.split(":", 1)
            return time(int(h), int(m))
    except (ValueError, AttributeError):
        pass
    return None


def _fmt_time(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


class _FeedInBase(CoordinatorEntity):
    def __init__(self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }

    @property
    def available(self) -> bool:
        return _cache(self.hass, self._config_entry.entry_id) is not None


class ByteWattGridFeedInSwitch(_FeedInBase, SwitchEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Grid Feed-in Function"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_enabled"
        self._attr_icon = "mdi:transmission-tower-export"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> Optional[bool]:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            val = pending.get_feedin("enabled")
            if val is not None:
                return bool(val)
        c = _cache(self.hass, self._config_entry.entry_id)
        return c.enabled if c else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._stage(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._stage(False)

    async def _stage(self, state: bool) -> None:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            pending.set_feedin(enabled=state)
            _LOGGER.debug("Staged grid feed-in enabled=%s (pending submit)", state)
            self.async_write_ha_state()
        else:
            _LOGGER.error("No pending store found for grid feed-in switch")


class ByteWattGridFeedInCutoffSOC(_FeedInBase, NumberEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Grid Feed-in Discharging Cutoff SOC"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_cutoff_soc"
        self._attr_icon = "mdi:battery-arrow-down"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = NumberDeviceClass.BATTERY

    @property
    def native_value(self) -> Optional[float]:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            val = pending.get_feedin("cutoff_soc")
            if val is not None:
                return float(val)
        c = _cache(self.hass, self._config_entry.entry_id)
        return float(c.battery_feed_cutoff_soc) if c else None

    async def async_set_native_value(self, value: float) -> None:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            pending.set_feedin(cutoff_soc=value)
            _LOGGER.debug("Staged grid feed-in cutoff_soc=%s (pending submit)", value)
            self.async_write_ha_state()
        else:
            _LOGGER.error("No pending store found for grid feed-in cutoff SOC")


class ByteWattGridFeedInSlotPower(_FeedInBase, NumberEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Grid Feed-in Time1 Power"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_slot0_power"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_min_value = 0
        self._attr_native_max_value = 20000
        self._attr_native_step = 100
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = NumberDeviceClass.POWER

    @property
    def available(self) -> bool:
        c = _cache(self.hass, self._config_entry.entry_id)
        return bool(c) and len(c.slots) > SLOT

    @property
    def native_value(self) -> Optional[float]:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            val = pending.get_feedin_slot(SLOT, "slot_power")
            if val is not None:
                return float(val)
        c = _cache(self.hass, self._config_entry.entry_id)
        if not c or len(c.slots) <= SLOT:
            return None
        return float(c.slots[SLOT].feed_power)

    async def async_set_native_value(self, value: float) -> None:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            pending.set_feedin_slot(SLOT, power=int(value))
            _LOGGER.debug("Staged grid feed-in Time1 power=%s (pending submit)", int(value))
            self.async_write_ha_state()
        else:
            _LOGGER.error("No pending store found for grid feed-in slot power")


class ByteWattGridFeedInSlotStartTime(_FeedInBase, TimeEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Grid Feed-in Time1 Start"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_slot0_start"
        self._attr_icon = "mdi:clock-start"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        c = _cache(self.hass, self._config_entry.entry_id)
        return bool(c) and len(c.slots) > SLOT

    @property
    def native_value(self) -> Optional[time]:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            val = pending.get_feedin_slot(SLOT, "slot_start")
            if val is not None:
                return _parse_time(val)
        c = _cache(self.hass, self._config_entry.entry_id)
        if not c or len(c.slots) <= SLOT:
            return None
        return _parse_time(c.slots[SLOT].start)

    async def async_set_value(self, value: time) -> None:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            pending.set_feedin_slot(SLOT, start=_fmt_time(value))
            _LOGGER.debug("Staged grid feed-in Time1 start=%s (pending submit)", _fmt_time(value))
            self.async_write_ha_state()
        else:
            _LOGGER.error("No pending store found for grid feed-in slot start")


class ByteWattGridFeedInSlotEndTime(_FeedInBase, TimeEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Grid Feed-in Time1 End"
        self._attr_unique_id = f"{config_entry.entry_id}_grid_feedin_slot0_end"
        self._attr_icon = "mdi:clock-end"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        c = _cache(self.hass, self._config_entry.entry_id)
        return bool(c) and len(c.slots) > SLOT

    @property
    def native_value(self) -> Optional[time]:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            val = pending.get_feedin_slot(SLOT, "slot_end")
            if val is not None:
                return _parse_time(val)
        c = _cache(self.hass, self._config_entry.entry_id)
        if not c or len(c.slots) <= SLOT:
            return None
        return _parse_time(c.slots[SLOT].end)

    async def async_set_value(self, value: time) -> None:
        from .pending import get_pending
        pending = get_pending(self.hass, self._config_entry.entry_id)
        if pending is not None:
            pending.set_feedin_slot(SLOT, end=_fmt_time(value))
            _LOGGER.debug("Staged grid feed-in Time1 end=%s (pending submit)", _fmt_time(value))
            self.async_write_ha_state()
        else:
            _LOGGER.error("No pending store found for grid feed-in slot end")


async def async_setup_switch_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([ByteWattGridFeedInSwitch(coordinator, config_entry)])


async def async_setup_number_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([
        ByteWattGridFeedInCutoffSOC(coordinator, config_entry),
        ByteWattGridFeedInSlotPower(coordinator, config_entry),
    ])


async def async_setup_time_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([
        ByteWattGridFeedInSlotStartTime(coordinator, config_entry),
        ByteWattGridFeedInSlotEndTime(coordinator, config_entry),
    ])