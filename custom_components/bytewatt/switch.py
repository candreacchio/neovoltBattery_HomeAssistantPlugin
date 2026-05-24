"""Switch entities for the Byte-Watt integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator
from .grid_feedin import async_setup_switch_entry as _feedin_setup
from .settings_manager import SettingsManager, SettingsValidationError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Byte-Watt switch entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]

    await _feedin_setup(hass, config_entry, async_add_entities)

    async_add_entities([
        ByteWattGridChargeSwitch(coordinator, config_entry, manager),
        ByteWattDischargeControlSwitch(coordinator, config_entry, manager),
    ])


class _BatterySwitchBase(CoordinatorEntity, SwitchEntity):
    """Switch that reads/writes a boolean battery setting via the manager."""

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
    def is_on(self) -> Optional[bool]:
        value = self._manager.effective_battery(self._field)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._stage(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._stage(False)

    async def _stage(self, state: bool) -> None:
        try:
            self._manager.stage_battery(self._field, state)
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class ByteWattDischargeControlSwitch(_BatterySwitchBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Battery Discharge Time Control",
            unique_id="discharge_time_control",
            icon="mdi:battery-clock",
            field="discharge_time_control",
        )


class ByteWattGridChargeSwitch(_BatterySwitchBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Grid Charging Battery",
            unique_id="grid_charging_battery",
            icon="mdi:transmission-tower",
            field="grid_charging",
        )
