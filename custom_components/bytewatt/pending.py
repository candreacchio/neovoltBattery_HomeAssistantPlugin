"""Submit and Discard button entities for staged settings changes."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.persistent_notification import async_create as notify_create
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, signal_pending_changed
from .settings_manager import SettingsManager

_LOGGER = logging.getLogger(__name__)


def _manager(hass: HomeAssistant, entry_id: str) -> SettingsManager:
    return hass.data[DOMAIN][entry_id]["manager"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Submit + Discard buttons."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([
        ByteWattSubmitButton(coordinator, config_entry),
        ByteWattDiscardButton(coordinator, config_entry),
    ])


class _PendingButtonBase(CoordinatorEntity, ButtonEntity):
    """Shared base — always available, exposes pending_count as an attribute,
    re-renders on every pending-state change via the dispatcher signal.

    Buttons are intentionally always-available (HA convention: ``available``
    is for "literally cannot act," not "nothing to do"). Pressing with
    nothing pending is a harmless no-op.
    """

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = _manager(self.hass, self._config_entry.entry_id)
        return {"pending_count": m.pending_count()}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_pending_changed(self._config_entry.entry_id),
                self._on_pending_changed,
            )
        )

    @callback
    def _on_pending_changed(self) -> None:
        self.async_write_ha_state()


class ByteWattSubmitButton(_PendingButtonBase):
    """Push all staged changes to the inverter."""

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Submit Settings"
        self._attr_unique_id = f"{config_entry.entry_id}_submit_settings"
        self._attr_icon = "mdi:content-save-check"

    async def async_press(self) -> None:
        entry_id = self._config_entry.entry_id
        m = _manager(self.hass, entry_id)

        if not m.has_pending():
            _LOGGER.debug("Submit pressed with nothing pending — no-op")
            return

        result = await m.submit()

        # Refresh sensors/data — settings cache is already updated by the
        # manager, but other coordinator-driven state may have changed.
        await self.coordinator.async_request_refresh()

        if not result.any_attempted or result.all_ok:
            return

        notification_id = f"bytewatt_submit_{entry_id}"

        # Partial or total failure — be specific about what failed and why.
        failures = []
        if result.battery_attempted and not result.battery_ok:
            detail = result.battery_error or "unknown error"
            failures.append(f"battery settings: {detail}")
        if result.feedin_attempted and not result.feedin_ok:
            detail = result.feedin_error or "unknown error"
            failures.append(f"grid feed-in settings: {detail}")

        any_success = result.battery_ok or result.feedin_ok
        title = (
            "ByteWatt: settings partially saved" if any_success
            else "ByteWatt: settings save failed"
        )
        notify_create(
            self.hass,
            "Failed after retries — " + "; ".join(failures) +
            ". Unsaved changes have been preserved — fix the issue and press Submit again.",
            title=title,
            notification_id=notification_id,
        )


class ByteWattDiscardButton(_PendingButtonBase):
    """Drop all staged changes without sending anything to the inverter."""

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Discard Pending Settings"
        self._attr_unique_id = f"{config_entry.entry_id}_discard_settings"
        self._attr_icon = "mdi:undo-variant"

    async def async_press(self) -> None:
        entry_id = self._config_entry.entry_id
        m = _manager(self.hass, entry_id)
        if not m.has_pending():
            _LOGGER.debug("Discard pressed with nothing pending — no-op")
            return
        count = m.discard()
        _LOGGER.info("Discarded %d pending settings change(s)", count)
        notify_create(
            self.hass,
            f"Discarded {count} unsaved setting change(s). Entities now reflect "
            f"the inverter's current state.",
            title="ByteWatt: pending discarded",
            notification_id=f"bytewatt_discard_{entry_id}",
        )
        await self.coordinator.async_request_refresh()
