"""Config flow for Byte-Watt integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)

from .bytewatt_client import ByteWattClient
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_HOST_SYSTEM_ID,
    CONF_HOST_SYS_SN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

SYSTEM_LIST_ENDPOINT = "api/stable/home/getCustomMenuEssList?inverterMode=0"


class ByteWattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Byte-Watt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self._user_input = {}
        self._client = None
        self._inverters = []

    async def async_step_user(self, user_input=None):
        """Handle the initial credentials step."""
        errors = {}

        if user_input is not None:
            client = ByteWattClient(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            success = await client.initialize()

            if success:
                self._client = client
                self._user_input = user_input

                # Fetch inverter list to decide whether to show selection step
                inverters = await self._fetch_inverters()
                self._inverters = inverters

                if len(inverters) > 1:
                    # Multiple inverters — ask user to pick the Host
                    return await self.async_step_select_inverter()
                elif len(inverters) == 1:
                    # Single inverter — use it automatically, no need to ask
                    inv = inverters[0]
                    self._user_input[CONF_HOST_SYSTEM_ID] = inv["systemId"]
                    self._user_input[CONF_HOST_SYS_SN] = inv["sysSn"]
                    return self._create_entry()
                else:
                    # Couldn't fetch inverter list — continue without it
                    _LOGGER.warning("Could not fetch inverter list during setup")
                    return self._create_entry()
            else:
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                }
            ),
            errors=errors,
        )

    async def async_step_select_inverter(self, user_input=None):
        """Let the user pick which inverter is the Host for Grid Feed-in control."""
        errors = {}

        if user_input is not None:
            selected_id = user_input[CONF_HOST_SYSTEM_ID]
            # Find the matching sysSn
            sys_sn = next(
                (i["sysSn"] for i in self._inverters if i["systemId"] == selected_id),
                ""
            )
            self._user_input[CONF_HOST_SYSTEM_ID] = selected_id
            self._user_input[CONF_HOST_SYS_SN] = sys_sn
            return self._create_entry()

        # Build dropdown options — label shows sysSn + remark if available
        options = []
        default = None
        for inv in self._inverters:
            system_id = inv.get("systemId", "")
            sys_sn = inv.get("sysSn", system_id)
            remark = inv.get("remark", "")
            label = f"{sys_sn} ({remark})" if remark else sys_sn
            options.append(SelectOptionDict(value=system_id, label=label))
            # Pre-select the one labelled Master/Host if present
            if default is None:
                remark_lower = remark.lower()
                if "master" in remark_lower or "host" in remark_lower:
                    default = system_id

        if default is None and options:
            default = options[0]["value"]

        return self.async_show_form(
            step_id="select_inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST_SYSTEM_ID, default=default): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            description_placeholders={
                "count": str(len(self._inverters)),
            },
            errors=errors,
        )

    def _create_entry(self):
        return self.async_create_entry(
            title=f"Byte-Watt ({self._user_input[CONF_USERNAME]})",
            data=self._user_input,
        )

    async def _fetch_inverters(self) -> list:
        """Fetch the inverter list via the API."""
        try:
            response = await self._client.api_client._async_get(SYSTEM_LIST_ENDPOINT)
            if response and response.get("code") == 200:
                return response.get("data") or []
        except Exception as ex:
            _LOGGER.error("Error fetching inverter list: %s", ex)
        return []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ByteWattOptionsFlowHandler(config_entry)


class ByteWattOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Byte-Watt."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                }
            ),
        )