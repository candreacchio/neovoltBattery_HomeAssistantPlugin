"""Switch entities for the Byte-Watt integration."""
import logging
from typing import Optional, Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Byte-Watt switch entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    from .grid_feedin import async_setup_switch_entry as _feedin_setup
    await _feedin_setup(hass, config_entry, async_add_entities)

    entities = [
        ByteWattGridChargeSwitch(coordinator, config_entry),
        ByteWattDischargeControlSwitch(coordinator, config_entry),
    ]

    async_add_entities(entities)


class ByteWattSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Base class for Byte-Watt switch entities."""

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_id: str,
        icon: str,
        attribute: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG
        self._attribute = attribute

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

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the switch is on, checking pending store first."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            # Check pending store first
            pending_key = "discharge_time_control" if self._attribute == "ctr_dis" else "grid_charging"
            if pending is not None:
                pending_val = pending.get_battery(pending_key)
                if pending_val is not None:
                    return bool(pending_val)
            # Fall back to API cache
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                value = getattr(settings, self._attribute, None)
                if value is not None:
                    return bool(int(value))
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting {self._attr_name} state: {ex}")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            return hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache is not None
        except Exception:
            return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state(False)

    async def _async_set_state(self, state: bool) -> None:
        """Set the switch state."""
        # This method will be overridden by child classes
        pass


class ByteWattDischargeControlSwitch(ByteWattSwitchEntity):
    """Switch entity for battery discharge time control."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the discharge control switch entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Battery Discharge Time Control",
            unique_id="discharge_time_control",
            icon="mdi:battery-clock",
            attribute="ctr_dis",
        )

    async def _async_set_state(self, state: bool) -> None:
        """Stage the discharge control state in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(discharge_time_control=state)
                _LOGGER.debug("Staged discharge_time_control=%s (pending submit)", state)
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for discharge time control")
        except Exception as ex:
            _LOGGER.error(f"Error staging discharge time control: {ex}")


class ByteWattGridChargeSwitch(ByteWattSwitchEntity):
    """Switch entity for grid charging battery."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the grid charge switch entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Grid Charging Battery",
            unique_id="grid_charging_battery",
            icon="mdi:transmission-tower",
            attribute="grid_charge",
        )

    async def _async_set_state(self, state: bool) -> None:
        """Stage the grid charging state in pending store."""
        try:
            from .pending import get_pending
            pending = get_pending(self.hass, self._config_entry.entry_id)
            if pending is not None:
                pending.set_battery(grid_charging=state)
                _LOGGER.debug("Staged grid_charging=%s (pending submit)", state)
                self.async_write_ha_state()
            else:
                _LOGGER.error("No pending store found for grid charging")
        except Exception as ex:
            _LOGGER.error(f"Error staging grid charging: {ex}")