"""Number entities for the Byte-Watt integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator
from .grid_feedin import async_setup_number_entry as _feedin_setup
from .settings_manager import SettingsManager, SettingsValidationError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]

    await _feedin_setup(hass, config_entry, async_add_entities)

    async_add_entities([
        ByteWattChargeCapNumber(coordinator, config_entry, manager),
        ByteWattMinimumSOCNumber(coordinator, config_entry, manager),
        ByteWattChargePowerNumber(coordinator, config_entry, manager),
        ByteWattDischargePowerNumber(coordinator, config_entry, manager),
    ])


class _BatteryNumberBase(CoordinatorEntity, NumberEntity):
    """Number that reads/writes a numeric battery setting via the manager."""

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
        min_value: float,
        max_value: float,
        step: float,
        unit: str,
        device_class: Optional[NumberDeviceClass] = None,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._manager = manager
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

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
    def native_value(self) -> Optional[float]:
        value = self._manager.effective_battery(self._field)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            self._manager.stage_battery(self._field, value)
        except SettingsValidationError as ex:
            raise HomeAssistantError(str(ex)) from ex
        self.async_write_ha_state()


class ByteWattMinimumSOCNumber(_BatteryNumberBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Minimum SOC", unique_id="minimum_soc", icon="mdi:battery-low",
            field="minimum_soc",
            min_value=5, max_value=95, step=1, unit="%",
            device_class=NumberDeviceClass.BATTERY,
        )


class ByteWattChargeCapNumber(_BatteryNumberBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Battery Charge Cap", unique_id="charge_cap", icon="mdi:battery-high",
            field="charge_cap",
            min_value=50, max_value=100, step=1, unit="%",
            device_class=NumberDeviceClass.BATTERY,
        )


class ByteWattChargePowerNumber(_BatteryNumberBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Battery Charge Power", unique_id="charge_power",
            icon="mdi:battery-charging-high",
            field="charge_power",
            min_value=500, max_value=10000, step=100, unit="W",
            device_class=NumberDeviceClass.POWER,
        )


class ByteWattDischargePowerNumber(_BatteryNumberBase):
    def __init__(self, coordinator, config_entry, manager) -> None:
        super().__init__(
            coordinator, config_entry, manager,
            name="Battery Discharge Power", unique_id="discharge_power",
            icon="mdi:battery-minus",
            field="discharge_power",
            min_value=500, max_value=10000, step=100, unit="W",
            device_class=NumberDeviceClass.POWER,
        )
