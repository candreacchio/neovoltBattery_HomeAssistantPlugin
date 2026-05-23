"""Pending settings store and Submit button for the Byte-Watt integration.

All setting entities write their changes here instead of calling the API
immediately.  The ByteWattSubmitButton entity pushes everything to the API
in one shot, then clears the pending store on success or discards it on
failure (reverting entities to the last known-good API cache values).
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pending store — one instance per config entry, stored in hass.data
# ---------------------------------------------------------------------------

class PendingStore:
    """Holds unsaved changes for battery and grid feed-in settings."""

    def __init__(self):
        # Battery settings pending changes — keyed by kwarg name used in
        # client.update_battery_settings()
        self._battery: Dict[str, Any] = {}

        # Grid feed-in pending changes — mirrors the kwargs for
        # client.update_grid_feedin_settings(), except slot changes are
        # stored as a dict keyed by slot_index.
        self._feedin: Dict[str, Any] = {}
        self._feedin_slots: Dict[int, Dict[str, Any]] = {}

    # --- battery ---

    def set_battery(self, **kwargs) -> None:
        """Stage a battery setting change."""
        self._battery.update({k: v for k, v in kwargs.items() if v is not None})

    def get_battery(self, key: str, default=None):
        """Return a pending battery value if staged, else default."""
        return self._battery.get(key, default)

    def has_battery_pending(self) -> bool:
        return bool(self._battery)

    # --- grid feed-in ---

    def set_feedin(self, enabled: bool = None, cutoff_soc: float = None) -> None:
        """Stage a top-level grid feed-in change."""
        if enabled is not None:
            self._feedin["enabled"] = enabled
        if cutoff_soc is not None:
            self._feedin["cutoff_soc"] = cutoff_soc

    def set_feedin_slot(self, slot_index: int,
                        start: str = None, end: str = None, power: int = None) -> None:
        """Stage a slot-level grid feed-in change."""
        slot = self._feedin_slots.setdefault(slot_index, {})
        if start is not None:
            slot["slot_start"] = start
        if end is not None:
            slot["slot_end"] = end
        if power is not None:
            slot["slot_power"] = power

    def get_feedin(self, key: str, default=None):
        return self._feedin.get(key, default)

    def get_feedin_slot(self, slot_index: int, key: str, default=None):
        return self._feedin_slots.get(slot_index, {}).get(key, default)

    def has_feedin_pending(self) -> bool:
        return bool(self._feedin) or bool(self._feedin_slots)

    def has_any_pending(self) -> bool:
        return self.has_battery_pending() or self.has_feedin_pending()

    # --- lifecycle ---

    def clear(self) -> None:
        """Clear all pending changes (called after successful submit)."""
        self._battery.clear()
        self._feedin.clear()
        self._feedin_slots.clear()


def get_pending(hass: HomeAssistant, entry_id: str) -> Optional[PendingStore]:
    """Return the PendingStore for this config entry."""
    try:
        return hass.data[DOMAIN][entry_id]["pending"]
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Submit button
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the submit button platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([ByteWattSubmitButton(coordinator, config_entry)])


class ByteWattSubmitButton(CoordinatorEntity, ButtonEntity):
    """Button that pushes all pending setting changes to the API."""

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = "Submit Settings"
        self._attr_unique_id = f"{config_entry.entry_id}_submit_settings"
        self._attr_icon = "mdi:content-save-check"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }

    async def async_press(self) -> None:
        """Push all pending changes to the API."""
        entry_id = self._config_entry.entry_id
        pending = get_pending(self.hass, entry_id)
        client = self.hass.data[DOMAIN][entry_id]["client"]

        if not pending or not pending.has_any_pending():
            _LOGGER.info("Submit pressed but no pending changes")
            return

        # Snapshot pending in case we need to log what failed
        battery_snapshot = dict(pending._battery)
        feedin_snapshot = dict(pending._feedin)
        feedin_slots_snapshot = {k: dict(v) for k, v in pending._feedin_slots.items()}

        all_ok = True

        # --- Battery settings ---
        if pending.has_battery_pending():
            _LOGGER.debug("Submitting battery settings: %s", battery_snapshot)
            success = await client.update_battery_settings(**battery_snapshot)
            if success:
                _LOGGER.info("Battery settings submitted successfully")
            else:
                _LOGGER.error("Failed to submit battery settings: %s", battery_snapshot)
                all_ok = False

        # --- Grid feed-in settings ---
        if pending.has_feedin_pending():
            # Apply top-level changes
            fi_kwargs: Dict[str, Any] = {}
            if "enabled" in feedin_snapshot:
                fi_kwargs["enabled"] = feedin_snapshot["enabled"]
            if "cutoff_soc" in feedin_snapshot:
                fi_kwargs["cutoff_soc"] = feedin_snapshot["cutoff_soc"]

            if fi_kwargs:
                _LOGGER.debug("Submitting grid feed-in top-level: %s", fi_kwargs)
                success = await client.update_grid_feedin_settings(**fi_kwargs)
                if not success:
                    _LOGGER.error("Failed to submit grid feed-in settings: %s", fi_kwargs)
                    all_ok = False

            # Apply slot changes
            for slot_index, slot_kwargs in feedin_slots_snapshot.items():
                _LOGGER.debug("Submitting grid feed-in slot %d: %s", slot_index, slot_kwargs)
                success = await client.update_grid_feedin_settings(
                    slot_index=slot_index, **slot_kwargs
                )
                if not success:
                    _LOGGER.error(
                        "Failed to submit grid feed-in slot %d: %s", slot_index, slot_kwargs
                    )
                    all_ok = False

        if all_ok:
            # Clear pending — API caches now hold the truth
            pending.clear()
            _LOGGER.info("All settings submitted successfully, pending store cleared")
        else:
            # Discard pending — revert to last known good API cache values
            pending.clear()
            _LOGGER.warning(
                "One or more settings failed to submit — pending changes discarded, "
                "entities will revert to last known good values"
            )

        # Refresh coordinator so all entities re-read from the API cache
        await self.coordinator.async_request_refresh()