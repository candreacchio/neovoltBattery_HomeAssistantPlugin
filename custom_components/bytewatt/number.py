"""Number entities for the Byte-Watt integration."""
import logging
from typing import Optional

from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Byte-Watt number entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    from .grid_feedin import async_setup_number_entry as _feedin_setup
    await _feedin_setup(hass, config_entry, async_add_entities)

    entities = [
        ByteWattChargeCapNumber(coordinator, config_entry),
        ByteWattMinimumSOCNumber(coordinator, config_entry),
        ByteWattChargePowerNumber(coordinator, config_entry),
        ByteWattDischargePowerNumber(coordinator, config_entry),
    ]

    async_add_entities(entities)


class ByteWattNumberEntity(CoordinatorEntity, NumberEntity):
    """Base class for Byte-Watt number entities."""

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_id: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        device_class: Optional[NumberDeviceClass] = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_device_class = device_class
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }


class ByteWattMinimumSOCNumber(ByteWattNumberEntity):
    """Number entity for minimum state of charge."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the minimum SOC number entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Minimum SOC",
            unique_id="minimum_soc",
            icon="mdi:battery-low",
            min_value=5,
            max_value=95,
            step=1,
            device_class=NumberDeviceClass.BATTERY,
        )
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> Optional[float]:
        """Return pending value if staged, else current API cache value."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("minimum_soc")
                if val is not None:
                    return float(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                return float(getattr(settings, "bat_use_cap", 6))
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting minimum SOC value: {ex}")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Stage minimum SOC in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(minimum_soc=int(value))
                _LOGGER.debug("Staged minimum_soc=%s (pending submit)", int(value))
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for minimum SOC")
        except Exception as ex:
            _LOGGER.error(f"Error staging minimum SOC to {value}%: {ex}")


class ByteWattChargeCapNumber(ByteWattNumberEntity):
    """Number entity for battery charge cap."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the charge cap number entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Battery Charge Cap",
            unique_id="charge_cap",
            icon="mdi:battery-high",
            min_value=50,
            max_value=100,
            step=1,
            device_class=NumberDeviceClass.BATTERY,
        )
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> Optional[float]:
        """Return pending value if staged, else current API cache value."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("charge_cap")
                if val is not None:
                    return float(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                value = getattr(settings, "bat_high_cap", "100")
                return float(value) if isinstance(value, (str, int, float)) else 100.0
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting charge cap value: {ex}")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Stage charge cap in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(charge_cap=int(value))
                _LOGGER.debug("Staged charge_cap=%s (pending submit)", int(value))
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for charge cap")
        except Exception as ex:
            _LOGGER.error(f"Error staging charge cap to {value}%: {ex}")

class ByteWattChargePowerNumber(ByteWattNumberEntity):
    """Number entity for battery charge power rate."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Battery Charge Power",
            unique_id="charge_power",
            icon="mdi:battery-charging-high",
            min_value=500,
            max_value=10000,
            step=100,
            device_class=NumberDeviceClass.POWER,
        )
        self._attr_native_unit_of_measurement = "W"

    @property
    def native_value(self) -> Optional[float]:
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("charge_power")
                if val is not None:
                    return float(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                if settings.charge_slots:
                    return float(settings.charge_slots[0].charge_power)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting charge power value: {ex}")
        return None

    async def async_set_native_value(self, value: float) -> None:
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(charge_power=int(value))
                _LOGGER.debug("Staged charge_power=%sW (pending submit)", int(value))
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for charge power")
        except Exception as ex:
            _LOGGER.error(f"Error staging charge power to {value}W: {ex}")


class ByteWattDischargePowerNumber(ByteWattNumberEntity):
    """Number entity for battery discharge power rate."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Battery Discharge Power",
            unique_id="discharge_power",
            icon="mdi:battery-minus",
            min_value=500,
            max_value=10000,
            step=100,
            device_class=NumberDeviceClass.POWER,
        )
        self._attr_native_unit_of_measurement = "W"

    @property
    def native_value(self) -> Optional[float]:
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("discharge_power")
                if val is not None:
                    return float(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                if settings.discharge_slots:
                    return float(settings.discharge_slots[0].charge_power)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting discharge power value: {ex}")
        return None

    async def async_set_native_value(self, value: float) -> None:
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(discharge_power=int(value))
                _LOGGER.debug("Staged discharge_power=%sW (pending submit)", int(value))
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for discharge power")
        except Exception as ex:
            _LOGGER.error(f"Error staging discharge power to {value}W: {ex}")