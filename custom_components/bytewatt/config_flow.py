"""Config flow for Byte-Watt integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .bytewatt_client import ByteWattClient
from .const import (
    DOMAIN, 
    CONF_USERNAME, 
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_INVERTER_SNS,
    CONF_CONTROL_VARIANT,
    CONF_CONTROL_TARGET_SYSTEM_ID,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    DEFAULT_INVERTER_SNS,
    DEFAULT_CONTROL_VARIANT,
    DEFAULT_CONTROL_TARGET_SYSTEM_ID,
    CONTROL_VARIANT_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

class ByteWattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Byte-Watt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the credentials
            client = ByteWattClient(self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            success = await client.initialize()

            if success:
                return self.async_create_entry(
                    title=f"Byte-Watt ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )
            else:
                errors["base"] = "auth"

        # Show the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                    vol.Optional(
                        CONF_INVERTER_SNS, default=DEFAULT_INVERTER_SNS
                    ): str,
                    vol.Optional(
                        CONF_CONTROL_VARIANT, default=DEFAULT_CONTROL_VARIANT
                    ): vol.In(CONTROL_VARIANT_OPTIONS),
                    vol.Optional(
                        CONF_CONTROL_TARGET_SYSTEM_ID, default=DEFAULT_CONTROL_TARGET_SYSTEM_ID
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ByteWattOptionsFlowHandler(config_entry)


class ByteWattOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Byte-Watt."""

    def __init__(self, config_entry):
        """Initialize options flow."""
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
                    vol.Optional(
                        CONF_INVERTER_SNS,
                        default=self.config_entry.options.get(
                            CONF_INVERTER_SNS, DEFAULT_INVERTER_SNS
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CONTROL_VARIANT,
                        default=self.config_entry.options.get(
                            CONF_CONTROL_VARIANT,
                            self.config_entry.data.get(CONF_CONTROL_VARIANT, DEFAULT_CONTROL_VARIANT),
                        ),
                    ): vol.In(CONTROL_VARIANT_OPTIONS),
                    vol.Optional(
                        CONF_CONTROL_TARGET_SYSTEM_ID,
                        default=self.config_entry.options.get(
                            CONF_CONTROL_TARGET_SYSTEM_ID,
                            self.config_entry.data.get(
                                CONF_CONTROL_TARGET_SYSTEM_ID,
                                DEFAULT_CONTROL_TARGET_SYSTEM_ID,
                            ),
                        ),
                    ): str,
                }
            ),
        )
