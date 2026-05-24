"""Config flow for Byte-Watt integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .bytewatt_client import ByteWattClient
from .const import (
    CONF_HOST_SYSTEM_ID,
    CONF_HOST_SYS_SN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CURRENT_ENTRY_VERSION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _pre_select_host(inverters: list[dict[str, Any]]) -> str | None:
    """Pick a sensible default for the Host inverter dropdown."""
    candidates = []
    for inv in inverters:
        remark = (inv.get("remark") or "").lower()
        if "master" in remark or "host" in remark:
            candidates.append(inv.get("systemId", ""))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        _LOGGER.debug(
            "Multiple inverters marked master/host (%s); user must pick", candidates
        )
        return None
    if inverters:
        return inverters[0].get("systemId", "")
    return None


def _build_inverter_options(inverters: list[dict[str, Any]]) -> list[SelectOptionDict]:
    options: list[SelectOptionDict] = []
    for inv in inverters:
        system_id = inv.get("systemId", "")
        sys_sn = inv.get("sysSn", system_id)
        remark = inv.get("remark", "")
        label = f"{sys_sn} ({remark})" if remark else sys_sn
        options.append(SelectOptionDict(value=system_id, label=label))
    return options


class ByteWattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Byte-Watt."""

    VERSION = CURRENT_ENTRY_VERSION

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._client: ByteWattClient | None = None
        self._inverters: list[dict[str, Any]] = []
        self._reconfigure_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Prevent the same account being configured twice — the
            # username uniquely identifies a Byte-Watt account.
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            client = ByteWattClient(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            success = await client.initialize()
            if not success:
                errors["base"] = "auth"
            else:
                self._client = client
                self._user_input = user_input
                self._inverters = await client.fetch_inverter_list()
                if len(self._inverters) > 1:
                    return await self.async_step_select_inverter()
                if len(self._inverters) == 1:
                    inv = self._inverters[0]
                    self._user_input[CONF_HOST_SYSTEM_ID] = inv.get("systemId", "")
                    self._user_input[CONF_HOST_SYS_SN] = inv.get("sysSn", "")
                    return self._create_entry()
                # Could not enumerate inverters — let the user proceed, but the
                # grid feed-in features will be disabled until reconfigure.
                _LOGGER.warning(
                    "No inverters returned during setup — grid feed-in will be unavailable"
                )
                self._user_input[CONF_HOST_SYSTEM_ID] = ""
                self._user_input[CONF_HOST_SYS_SN] = ""
                return self._create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
            }),
            errors=errors,
        )

    async def async_step_select_inverter(self, user_input=None):
        if user_input is not None:
            selected_id = user_input[CONF_HOST_SYSTEM_ID]
            sys_sn = next(
                (i.get("sysSn", "") for i in self._inverters if i.get("systemId") == selected_id),
                "",
            )
            self._user_input[CONF_HOST_SYSTEM_ID] = selected_id
            self._user_input[CONF_HOST_SYS_SN] = sys_sn
            return self._create_entry()

        options = _build_inverter_options(self._inverters)
        default = _pre_select_host(self._inverters)

        return self.async_show_form(
            step_id="select_inverter",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST_SYSTEM_ID, default=default): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                ),
            }),
            description_placeholders={"count": str(len(self._inverters))},
        )

    def _create_entry(self):
        return self.async_create_entry(
            title=f"Byte-Watt ({self._user_input[CONF_USERNAME]})",
            data=self._user_input,
        )

    # ---------- Reconfigure (change Host inverter without losing entity history) ----------

    async def async_step_reconfigure(self, user_input=None):
        """Re-run the Host inverter selection for an existing entry."""
        self._reconfigure_entry = self._get_reconfigure_entry()
        creds = self._reconfigure_entry.data
        client = ByteWattClient(self.hass, creds[CONF_USERNAME], creds[CONF_PASSWORD])
        if not await client.initialize():
            return self.async_abort(reason="auth")
        self._inverters = await client.fetch_inverter_list()
        if not self._inverters:
            return self.async_abort(reason="no_inverters")
        return await self.async_step_reconfigure_select()

    async def async_step_reconfigure_select(self, user_input=None):
        entry = self._reconfigure_entry
        assert entry is not None
        if user_input is not None:
            selected_id = user_input[CONF_HOST_SYSTEM_ID]
            sys_sn = next(
                (i.get("sysSn", "") for i in self._inverters if i.get("systemId") == selected_id),
                "",
            )
            new_data = {
                **entry.data,
                CONF_HOST_SYSTEM_ID: selected_id,
                CONF_HOST_SYS_SN: sys_sn,
            }
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            # Reload explicitly so the abort is shown to the user only AFTER
            # the integration is running with the new Host inverter — gives
            # deterministic completion ordering for the reconfigure flow.
            # (The update listener also fires on data changes, but as a
            # fire-and-forget task — HA's async_reload is idempotent under
            # concurrent calls so the double-reload is harmless.)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        options = _build_inverter_options(self._inverters)
        # Only use the stored ID as default if it's still in the dropdown —
        # otherwise the SelectSelector would render with no selection.
        stored_id = entry.data.get(CONF_HOST_SYSTEM_ID)
        valid_ids = {opt["value"] for opt in options}
        if stored_id in valid_ids:
            default = stored_id
        else:
            default = _pre_select_host(self._inverters)
        return self.async_show_form(
            step_id="reconfigure_select",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST_SYSTEM_ID, default=default): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                ),
            }),
            description_placeholders={"count": str(len(self._inverters))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ByteWattOptionsFlowHandler(config_entry)


class ByteWattOptionsFlowHandler(config_entries.OptionsFlow):
    """Options: scan interval only."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
            }),
        )
