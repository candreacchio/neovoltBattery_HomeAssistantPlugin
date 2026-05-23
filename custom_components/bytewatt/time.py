"""Time entities for the Byte-Watt integration."""
import logging
from datetime import time
from typing import Optional

from homeassistant.components.time import TimeEntity
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
    """Set up Byte-Watt time entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    from .grid_feedin import async_setup_time_entry as _feedin_setup
    await _feedin_setup(hass, config_entry, async_add_entities)

    entities = [
        ByteWattChargeStartTime(coordinator, config_entry),
        ByteWattChargeEndTime(coordinator, config_entry),
        ByteWattDischargeStartTime(coordinator, config_entry),
        ByteWattDischargeEndTime(coordinator, config_entry),
    ]

    async_add_entities(entities)


class ByteWattTimeEntity(CoordinatorEntity, TimeEntity):
    """Base class for Byte-Watt time entities."""

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_id: str,
        icon: str,
        attribute_name: str,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG
        self._attribute_name = attribute_name

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

    def _parse_time_string(self, time_str: str) -> Optional[time]:
        """Parse a time string (HH:MM) into a time object."""
        try:
            if time_str and ":" in time_str:
                hour, minute = time_str.split(":", 1)
                return time(int(hour), int(minute))
        except (ValueError, AttributeError) as ex:
            _LOGGER.debug(f"Error parsing time string '{time_str}': {ex}")
        return None

    def _format_time_for_api(self, time_obj: time) -> str:
        """Format a time object for the API (HH:MM)."""
        return f"{time_obj.hour:02d}:{time_obj.minute:02d}"


class ByteWattChargeStartTime(ByteWattTimeEntity):
    """Time entity for charge start time."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the charge start time entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Charge Start Time",
            unique_id="charge_start_time",
            icon="mdi:battery-plus",
            attribute_name="time_chaf1a",
        )

    @property
    def native_value(self) -> Optional[time]:
        """Return pending value if staged, else current API cache value."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("charge_start_time")
                if val is not None:
                    return self._parse_time_string(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "14:30")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting charge start time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Stage charge start time in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(charge_start_time=self._format_time_for_api(value))
                _LOGGER.debug("Staged charge_start_time=%s (pending submit)", value)
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for charge start time")
        except Exception as ex:
            _LOGGER.error(f"Error staging charge start time to {value}: {ex}")


class ByteWattChargeEndTime(ByteWattTimeEntity):
    """Time entity for charge end time."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the charge end time entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Charge End Time",
            unique_id="charge_end_time",
            icon="mdi:battery-plus-outline",
            attribute_name="time_chae1a",
        )

    @property
    def native_value(self) -> Optional[time]:
        """Return pending value if staged, else current API cache value."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("charge_end_time")
                if val is not None:
                    return self._parse_time_string(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "16:00")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting charge end time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Stage charge end time in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(charge_end_time=self._format_time_for_api(value))
                _LOGGER.debug("Staged charge_end_time=%s (pending submit)", value)
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for charge end time")
        except Exception as ex:
            _LOGGER.error(f"Error staging charge end time to {value}: {ex}")


class ByteWattDischargeStartTime(ByteWattTimeEntity):
    """Time entity for discharge start time."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the discharge start time entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Discharge Start Time",
            unique_id="discharge_start_time",
            icon="mdi:battery-minus",
            attribute_name="time_disf1a",
        )

    @property
    def native_value(self) -> Optional[time]:
        """Return pending value if staged, else current API cache value."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("discharge_start_time")
                if val is not None:
                    return self._parse_time_string(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "16:00")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharge start time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Stage discharge start time in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(discharge_start_time=self._format_time_for_api(value))
                _LOGGER.debug("Staged discharge_start_time=%s (pending submit)", value)
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for discharge start time")
        except Exception as ex:
            _LOGGER.error(f"Error staging discharge start time to {value}: {ex}")


class ByteWattDischargeEndTime(ByteWattTimeEntity):
    """Time entity for discharge end time."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the discharge end time entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Discharge End Time",
            unique_id="discharge_end_time",
            icon="mdi:battery-minus-outline",
            attribute_name="time_dise1a",
        )

    @property
    def native_value(self) -> Optional[time]:
        """Return pending value if staged, else current API cache value."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                val = pending.get_battery("discharge_end_time")
                if val is not None:
                    return self._parse_time_string(val)
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "23:00")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharge end time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Stage discharge end time in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(discharge_end_time=self._format_time_for_api(value))
                _LOGGER.debug("Staged discharge_end_time=%s (pending submit)", value)
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for discharge end time")
        except Exception as ex:
            _LOGGER.error(f"Error staging discharge end time to {value}: {ex}")