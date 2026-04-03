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

    entities = [
        ByteWattChargeStartTime(coordinator, config_entry),
        ByteWattChargeEndTime(coordinator, config_entry),
        ByteWattChargeStartTime2(coordinator, config_entry),
        ByteWattChargeEndTime2(coordinator, config_entry),
        ByteWattDischargeStartTime(coordinator, config_entry),
        ByteWattDischargeEndTime(coordinator, config_entry),
        ByteWattDischargeStartTime2(coordinator, config_entry),
        ByteWattDischargeEndTime2(coordinator, config_entry),
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

    def _effective_control_variant(self) -> Optional[str]:
        """Return the currently effective control variant."""
        try:
            control_data = (self.coordinator.data or {}).get("control_variant", {})
            return control_data.get("effective_variant")
        except Exception:
            return None

    @property
    def available(self) -> bool:
        """Only expose legacy time controls for legacy charge-config systems."""
        variant = self._effective_control_variant()
        if variant and variant != "charge_config":
            return False
        return super().available


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
        """Return the current charge start time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "14:30")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting charge start time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Set the charge start time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(charge_start_time=time_str)
            if success:
                _LOGGER.info(f"Successfully updated charge start time to {time_str}")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update charge start time to {time_str}")
        except Exception as ex:
            _LOGGER.error(f"Error setting charge start time to {value}: {ex}")


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
        """Return the current charge end time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "16:00")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting charge end time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Set the charge end time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(charge_end_time=time_str)
            if success:
                _LOGGER.info(f"Successfully updated charge end time to {time_str}")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update charge end time to {time_str}")
        except Exception as ex:
            _LOGGER.error(f"Error setting charge end time to {value}: {ex}")


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
        """Return the current discharge start time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "16:00")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharge start time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Set the discharge start time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(discharge_start_time=time_str)
            if success:
                _LOGGER.info(f"Successfully updated discharge start time to {time_str}")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update discharge start time to {time_str}")
        except Exception as ex:
            _LOGGER.error(f"Error setting discharge start time to {value}: {ex}")


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
        """Return the current discharge end time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                time_str = getattr(settings, self._attribute_name, "23:00")
                return self._parse_time_string(time_str)
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharge end time: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        """Set the discharge end time."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(discharge_end_time=time_str)
            if success:
                _LOGGER.info(f"Successfully updated discharge end time to {time_str}")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update discharge end time to {time_str}")
        except Exception as ex:
            _LOGGER.error(f"Error setting discharge end time to {value}: {ex}")


class ByteWattChargeStartTime2(ByteWattTimeEntity):
    """Time entity for charge start time 2."""

    def __init__(self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Charge Start Time 2",
            unique_id="charge_start_time_2",
            icon="mdi:battery-plus",
            attribute_name="time_chaf2a",
        )

    @property
    def native_value(self) -> Optional[time]:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                return self._parse_time_string(getattr(settings, self._attribute_name, "00:00"))
        except Exception as ex:
            _LOGGER.debug(f"Error getting charge start time 2: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(charge_start_time_2=time_str)
            if success:
                if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                    client.api_client._settings_cache.time_chaf2a = time_str
                _LOGGER.info(f"Successfully updated charge start time 2 to {time_str}")
                await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(f"Error setting charge start time 2 to {value}: {ex}")


class ByteWattChargeEndTime2(ByteWattTimeEntity):
    """Time entity for charge end time 2."""

    def __init__(self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Charge End Time 2",
            unique_id="charge_end_time_2",
            icon="mdi:battery-plus-outline",
            attribute_name="time_chae2a",
        )

    @property
    def native_value(self) -> Optional[time]:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                return self._parse_time_string(getattr(settings, self._attribute_name, "00:00"))
        except Exception as ex:
            _LOGGER.debug(f"Error getting charge end time 2: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(charge_end_time_2=time_str)
            if success:
                if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                    client.api_client._settings_cache.time_chae2a = time_str
                _LOGGER.info(f"Successfully updated charge end time 2 to {time_str}")
                await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(f"Error setting charge end time 2 to {value}: {ex}")


class ByteWattDischargeStartTime2(ByteWattTimeEntity):
    """Time entity for discharge start time 2."""

    def __init__(self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Discharge Start Time 2",
            unique_id="discharge_start_time_2",
            icon="mdi:battery-minus",
            attribute_name="time_disf2a",
        )

    @property
    def native_value(self) -> Optional[time]:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                return self._parse_time_string(getattr(settings, self._attribute_name, "00:00"))
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharge start time 2: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(discharge_start_time_2=time_str)
            if success:
                if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                    client.api_client._settings_cache.time_disf2a = time_str
                _LOGGER.info(f"Successfully updated discharge start time 2 to {time_str}")
                await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(f"Error setting discharge start time 2 to {value}: {ex}")


class ByteWattDischargeEndTime2(ByteWattTimeEntity):
    """Time entity for discharge end time 2."""

    def __init__(self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Discharge End Time 2",
            unique_id="discharge_end_time_2",
            icon="mdi:battery-minus-outline",
            attribute_name="time_dise2a",
        )

    @property
    def native_value(self) -> Optional[time]:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                return self._parse_time_string(getattr(settings, self._attribute_name, "00:00"))
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharge end time 2: {ex}")
        return None

    async def async_set_value(self, value: time) -> None:
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            time_str = self._format_time_for_api(value)
            success = await client.update_battery_settings(discharge_end_time_2=time_str)
            if success:
                if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                    client.api_client._settings_cache.time_dise2a = time_str
                _LOGGER.info(f"Successfully updated discharge end time 2 to {time_str}")
                await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(f"Error setting discharge end time 2 to {value}: {ex}")
