"""Time entities for the Byte-Watt integration."""
from __future__ import annotations

import logging
from datetime import time
from typing import Any, Optional

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator
from .grid_feedin import async_setup_time_entry as _feedin_setup
from .settings_manager import SettingsManager, SettingsValidationError

_LOGGER = logging.getLogger(__name__)


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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]

    await _feedin_setup(hass, config_entry, async_add_entities)

    async_add_entities([
        ByteWattChargeStartTime(coordinator, config_entry, manager),
        ByteWattChargeEndTime(coordinator, config_entry, manager),
        ByteWattDischargeStartTime(coordinator, config_entry, manager),
        ByteWattDischargeEndTime(coordinator, config_entry, manager),
    ])


class _BatteryTimeBase(CoordinatorEntity, TimeEntity):
    """Time entity that reads/writes a HH:MM battery setting via the manager."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        manager: SettingsManager,
        name: str,
        unique_id: str,
        icon: str,
        field: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._manager = manager
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon

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
        return self._manager.battery_cache is not None

    @property
    def native_value(self) -> Optional[time]:
        value = self._manager.effective_battery(self._field)
        return _parse_time(value) if value else None

    async def async_set_value(self, value: time) -> None:
        try:
            self._manager.stage_battery(self._field, _fmt_time(value))
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class ByteWattChargeStartTime(_BatteryTimeBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Charge Start Time", unique_id="charge_start_time",
            icon="mdi:battery-plus", field="charge_start_time",
        )


class ByteWattChargeEndTime(_BatteryTimeBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Charge End Time", unique_id="charge_end_time",
            icon="mdi:battery-plus-outline", field="charge_end_time",
        )


class ByteWattDischargeStartTime(_BatteryTimeBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Discharge Start Time", unique_id="discharge_start_time",
            icon="mdi:battery-minus", field="discharge_start_time",
        )


class ByteWattDischargeEndTime(_BatteryTimeBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Discharge End Time", unique_id="discharge_end_time",
            icon="mdi:battery-minus-outline", field="discharge_end_time",
        )
