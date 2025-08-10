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
    CONF_DEVICE_SN,
    CONF_SCAN_INTERVAL,
    DEFAULT_DEVICE_SN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

class ByteWattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Byte-Watt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.client = None
        self.user_data = {}
        self.devices = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Store user credentials
            self.user_data = user_input
            
            # Validate the credentials
            self.client = ByteWattClient(self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            success = await self.client.initialize()

            if success:
                # Get device list for selection
                try:
                    self.devices = await self.client.api_client.async_get_device_menu_list() or []
                    _LOGGER.debug("Found %d devices for selection", len(self.devices))
                except Exception as e:
                    _LOGGER.error("Error fetching device list: %s", e)
                    self.devices = []
                
                # If we have devices, go to device selection step
                # Otherwise, just use "All" as default
                if self.devices:
                    return await self.async_step_device()
                else:
                    # No devices found or error, just use "All"
                    self.user_data[CONF_DEVICE_SN] = DEFAULT_DEVICE_SN
                    return self.async_create_entry(
                        title=f"Byte-Watt ({user_input[CONF_USERNAME]})",
                        data=self.user_data,
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
                }
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        """Handle device selection step."""
        if user_input is not None:
            # Add selected device to config
            self.user_data[CONF_DEVICE_SN] = user_input[CONF_DEVICE_SN]
            
            # Create title with device info
            device_sn = user_input[CONF_DEVICE_SN]
            if device_sn == DEFAULT_DEVICE_SN:
                title = f"Byte-Watt ({self.user_data[CONF_USERNAME]}) - All Devices"
            else:
                # Find device info for title
                device_info = next((d for d in self.devices if d.get("sysSn") == device_sn), None)
                if device_info:
                    model = device_info.get("mbat", "Unknown")
                    title = f"Byte-Watt {device_sn[-4:]} ({model})"
                else:
                    title = f"Byte-Watt ({device_sn})"
            
            return self.async_create_entry(
                title=title,
                data=self.user_data,
            )
        
        # Build device options for selection
        device_options = {DEFAULT_DEVICE_SN: "All Devices (Combined)"}
        
        for device in self.devices:
            sn = device.get("sysSn", "")
            if sn:
                # Create descriptive label
                model = device.get("mbat", "Unknown")
                capacity = device.get("storageCap", 0)
                label = f"{sn} ({model}, {capacity}kW)"
                device_options[sn] = label
        
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_SN,
                        default=DEFAULT_DEVICE_SN
                    ): vol.In(device_options),
                }
            ),
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
                }
            ),
        )