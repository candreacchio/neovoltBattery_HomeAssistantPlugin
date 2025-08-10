"""The Byte-Watt integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

from .bytewatt_client import ByteWattClient
from .coordinator import ByteWattDataUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_SN,
    CONF_SCAN_INTERVAL,
    CONF_RECOVERY_ENABLED,
    CONF_HEARTBEAT_INTERVAL,
    CONF_MAX_DATA_AGE,
    CONF_STALE_CHECKS_THRESHOLD,
    CONF_NOTIFY_ON_RECOVERY,
    CONF_DIAGNOSTICS_MODE,
    CONF_AUTO_RECONNECT_TIME,
    DEFAULT_DEVICE_SN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_RECOVERY_ENABLED,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_MAX_DATA_AGE,
    DEFAULT_STALE_CHECKS_THRESHOLD,
    DEFAULT_NOTIFY_ON_RECOVERY,
    DEFAULT_DIAGNOSTICS_MODE,
    DEFAULT_AUTO_RECONNECT_TIME,
    SERVICE_SET_DISCHARGE_TIME,
    SERVICE_SET_DISCHARGE_START_TIME,
    SERVICE_SET_CHARGE_START_TIME,
    SERVICE_SET_CHARGE_END_TIME,
    SERVICE_SET_MINIMUM_SOC,
    SERVICE_SET_CHARGE_CAP,
    SERVICE_UPDATE_BATTERY_SETTINGS,
    SERVICE_FORCE_RECONNECT,
    SERVICE_HEALTH_CHECK,
    SERVICE_TOGGLE_DIAGNOSTICS,
    ATTR_END_DISCHARGE,
    ATTR_START_DISCHARGE,
    ATTR_START_CHARGE,
    ATTR_END_CHARGE,
    ATTR_MINIMUM_SOC,
    ATTR_CHARGE_CAP,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["sensor", "number", "time", "switch"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Byte-Watt component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Byte-Watt from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device_sn = entry.data.get(CONF_DEVICE_SN, DEFAULT_DEVICE_SN)  # Default to "All" for existing configs
    
    # Get all configuration options with defaults
    options = entry.options or {}
    scan_interval = options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    
    # Recovery options (can be added to config flow for future customization)
    recovery_options = {
        CONF_RECOVERY_ENABLED: options.get(CONF_RECOVERY_ENABLED, DEFAULT_RECOVERY_ENABLED),
        CONF_HEARTBEAT_INTERVAL: options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL),
        CONF_MAX_DATA_AGE: options.get(CONF_MAX_DATA_AGE, DEFAULT_MAX_DATA_AGE),
        CONF_STALE_CHECKS_THRESHOLD: options.get(CONF_STALE_CHECKS_THRESHOLD, DEFAULT_STALE_CHECKS_THRESHOLD),
        CONF_NOTIFY_ON_RECOVERY: options.get(CONF_NOTIFY_ON_RECOVERY, DEFAULT_NOTIFY_ON_RECOVERY),
        CONF_DIAGNOSTICS_MODE: options.get(CONF_DIAGNOSTICS_MODE, DEFAULT_DIAGNOSTICS_MODE),
        CONF_AUTO_RECONNECT_TIME: options.get(CONF_AUTO_RECONNECT_TIME, DEFAULT_AUTO_RECONNECT_TIME)
    }

    client = ByteWattClient(hass, username, password)
    
    _LOGGER.info("Setting up ByteWatt integration for device: %s", device_sn)

    coordinator = ByteWattDataUpdateCoordinator(
        hass,
        client=client,
        scan_interval=scan_interval,
        entry_id=entry.entry_id,
        options=recovery_options,
        device_sn=device_sn
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    # Start the heartbeat monitoring service if enabled
    if recovery_options[CONF_RECOVERY_ENABLED]:
        await coordinator.start_heartbeat()
        _LOGGER.info(
            f"ByteWatt heartbeat monitoring started (interval: {recovery_options[CONF_HEARTBEAT_INTERVAL]}s, "
            f"stale threshold: {recovery_options[CONF_MAX_DATA_AGE]}s)"
        )

    # Register all battery control services and recovery services
    await register_battery_services(hass, client, coordinator)

    # Setup platforms - use the newer async_forward_entry_setups to avoid deprecation warning
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Stop the heartbeat service first
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
        if coordinator:
            await coordinator.stop_heartbeat()
            _LOGGER.info("ByteWatt heartbeat monitoring service stopped")
    
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def register_battery_services(hass: HomeAssistant, client: ByteWattClient, coordinator=None):
    """Register all battery control services and maintenance services."""
    
    # Register Force Reconnect service - retrieves all coordinator objects and triggers recovery
    async def handle_force_reconnect(call: ServiceCall):
        """Handle the service call to force a reconnection for all ByteWatt integrations."""
        _LOGGER.warning("Manual reconnect triggered for ByteWatt integration")
        reconnected = False
        
        for entry_id, entry_data in hass.data[DOMAIN].items():
            if "coordinator" in entry_data:
                coordinator = entry_data["coordinator"]
                _LOGGER.info(f"Forcing recovery for ByteWatt integration (entry_id: {entry_id})")
                try:
                    # Execute the recovery process
                    await coordinator._perform_recovery()
                    reconnected = True
                    _LOGGER.info(f"Recovery process completed for ByteWatt integration (entry_id: {entry_id})")
                except Exception as err:
                    _LOGGER.error(f"Failed to recover ByteWatt integration (entry_id: {entry_id}): {err}")
        
        if not reconnected:
            _LOGGER.error("No active ByteWatt integrations found to reconnect")
    
    # Register Health Check service
    async def handle_health_check(call: ServiceCall):
        """Handle the service call to run a health check."""
        results = {}
        
        # Get specific entry_id from service call if provided
        entry_id = call.data.get('entry_id')
        
        if entry_id:
            # Run health check for specific integration
            if entry_id in hass.data[DOMAIN] and "coordinator" in hass.data[DOMAIN][entry_id]:
                coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
                results[entry_id] = await coordinator.run_health_check()
            else:
                _LOGGER.error(f"No ByteWatt integration found with entry_id: {entry_id}")
        else:
            # Run health check for all integrations
            for entry_id, entry_data in hass.data[DOMAIN].items():
                if "coordinator" in entry_data:
                    coordinator = entry_data["coordinator"]
                    results[entry_id] = await coordinator.run_health_check()
        
        # Create persistent notification with health check results
        if results:
            summary = []
            for entry_id, result in results.items():
                status = result.get("connection_status", "unknown")
                color = {
                    "healthy": "green",
                    "limited": "orange",
                    "disconnected": "red",
                    "unknown": "grey"
                }.get(status, "grey")
                
                auth_success = result.get("authentication", {}).get("success", False)
                api_success = all(
                    endpoint.get("success", False) 
                    for endpoint in result.get("api_checks", {}).values()
                )
                
                summary.append(
                    f"Integration {entry_id}: "
                    f"<span style='color:{color};'>{status}</span><br>"
                    f"Authentication: {'✓' if auth_success else '✗'}, "
                    f"API: {'✓' if api_success else '✗'}"
                )
            
            message = "<br>".join(summary)
            try:
                await hass.components.persistent_notification.async_create(
                    message,
                    title="ByteWatt Health Check Results",
                    notification_id="bytewatt_health_check"
                )
            except (AttributeError, TypeError) as e:
                _LOGGER.error(f"Could not create health check notification: {e}")
        else:
            _LOGGER.error("No ByteWatt integrations found for health check")
    
    # Register Toggle Diagnostics service
    async def handle_toggle_diagnostics(call: ServiceCall):
        """Handle the service call to toggle diagnostics mode."""
        enable = call.data.get('enable')
        entry_id = call.data.get('entry_id')
        
        results = {}
        
        if entry_id:
            # Toggle diagnostics for specific integration
            if entry_id in hass.data[DOMAIN] and "coordinator" in hass.data[DOMAIN][entry_id]:
                coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
                results[entry_id] = coordinator.toggle_diagnostics_mode(enable)
            else:
                _LOGGER.error(f"No ByteWatt integration found with entry_id: {entry_id}")
        else:
            # Toggle diagnostics for all integrations
            for entry_id, entry_data in hass.data[DOMAIN].items():
                if "coordinator" in entry_data:
                    coordinator = entry_data["coordinator"]
                    results[entry_id] = coordinator.toggle_diagnostics_mode(enable)
        
        # Create persistent notification
        if results:
            message = "Diagnostics Mode: "
            message += "Enabled" if list(results.values())[0].get("diagnostics_mode", False) else "Disabled"
            try:
                await hass.components.persistent_notification.async_create(
                    message,
                    title="ByteWatt Diagnostics",
                    notification_id="bytewatt_diagnostics"
                )
            except (AttributeError, TypeError) as e:
                _LOGGER.error(f"Could not create diagnostics notification: {e}")
        else:
            _LOGGER.error("No ByteWatt integrations found to toggle diagnostics")
    
    # Legacy service - set discharge end time only
    async def handle_set_discharge_time(call: ServiceCall):
        """Handle the service call to set discharge end time."""
        end_discharge = call.data.get(ATTR_END_DISCHARGE)
        if not end_discharge:
            _LOGGER.error("No end_discharge time provided")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            discharge_end_time=end_discharge
        )
        
        if success:
            _LOGGER.debug(f"Successfully set discharge end time to {end_discharge}")
        else:
            _LOGGER.error(f"Failed to set discharge end time to {end_discharge}")
        
        return success
    
    # New service - set discharge start time
    async def handle_set_discharge_start_time(call: ServiceCall):
        """Handle the service call to set discharge start time."""
        start_discharge = call.data.get(ATTR_START_DISCHARGE)
        if not start_discharge:
            _LOGGER.error("No start_discharge time provided")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            discharge_start_time=start_discharge
        )
        
        if success:
            _LOGGER.debug(f"Successfully set discharge start time to {start_discharge}")
        else:
            _LOGGER.error(f"Failed to set discharge start time to {start_discharge}")
        
        return success
    
    # New service - set charge start time
    async def handle_set_charge_start_time(call: ServiceCall):
        """Handle the service call to set charge start time."""
        start_charge = call.data.get(ATTR_START_CHARGE)
        if not start_charge:
            _LOGGER.error("No start_charge time provided")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            charge_start_time=start_charge
        )
        
        if success:
            _LOGGER.debug(f"Successfully set charge start time to {start_charge}")
        else:
            _LOGGER.error(f"Failed to set charge start time to {start_charge}")
        
        return success
    
    # New service - set charge end time
    async def handle_set_charge_end_time(call: ServiceCall):
        """Handle the service call to set charge end time."""
        end_charge = call.data.get(ATTR_END_CHARGE)
        if not end_charge:
            _LOGGER.error("No end_charge time provided")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            charge_end_time=end_charge
        )
        
        if success:
            _LOGGER.debug(f"Successfully set charge end time to {end_charge}")
        else:
            _LOGGER.error(f"Failed to set charge end time to {end_charge}")
        
        return success
    
    # New service - set minimum SOC
    async def handle_set_minimum_soc(call: ServiceCall):
        """Handle the service call to set minimum state of charge."""
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        if minimum_soc is None:
            _LOGGER.error("No minimum_soc provided")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            minimum_soc=minimum_soc
        )
        
        if success:
            _LOGGER.debug(f"Successfully set minimum SOC to {minimum_soc}%")
        else:
            _LOGGER.error(f"Failed to set minimum SOC to {minimum_soc}%")
        
        return success
    
    async def handle_set_charge_cap(call: ServiceCall):
        """Handle the service call to set charge cap."""
        charge_cap = call.data.get(ATTR_CHARGE_CAP)
        if charge_cap is None:
            _LOGGER.error("No charge_cap provided")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            charge_cap=charge_cap
        )
        
        if success:
            _LOGGER.debug(f"Successfully set charge cap to {charge_cap}%")
        else:
            _LOGGER.error(f"Failed to set charge cap to {charge_cap}%")
        
        return success
    
    # New service - update multiple battery settings at once
    async def handle_update_battery_settings(call: ServiceCall):
        """Handle the service call to update multiple battery settings at once."""
        discharge_start_time = call.data.get(ATTR_START_DISCHARGE)
        discharge_end_time = call.data.get(ATTR_END_DISCHARGE)
        charge_start_time = call.data.get(ATTR_START_CHARGE)
        charge_end_time = call.data.get(ATTR_END_CHARGE)
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        charge_cap = call.data.get(ATTR_CHARGE_CAP)
        
        # Check if at least one parameter is provided
        if (discharge_start_time is None and discharge_end_time is None and
                charge_start_time is None and charge_end_time is None and
                minimum_soc is None and charge_cap is None):
            _LOGGER.error("No battery settings provided to update")
            return

        # Get the first ByteWatt coordinator
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break
        
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            discharge_start_time=discharge_start_time,
            discharge_end_time=discharge_end_time,
            charge_start_time=charge_start_time,
            charge_end_time=charge_end_time,
            minimum_soc=minimum_soc,
            charge_cap=charge_cap
        )
        
        if success:
            _LOGGER.info("Successfully updated battery settings")
        else:
            _LOGGER.error("Failed to update battery settings")
        
        return success

    # Register all services
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_DISCHARGE_TIME,
        handle_set_discharge_time,
        schema=vol.Schema({
            vol.Required(ATTR_END_DISCHARGE): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_DISCHARGE_START_TIME,
        handle_set_discharge_start_time,
        schema=vol.Schema({
            vol.Required(ATTR_START_DISCHARGE): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_CHARGE_START_TIME,
        handle_set_charge_start_time,
        schema=vol.Schema({
            vol.Required(ATTR_START_CHARGE): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_CHARGE_END_TIME,
        handle_set_charge_end_time,
        schema=vol.Schema({
            vol.Required(ATTR_END_CHARGE): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_MINIMUM_SOC,
        handle_set_minimum_soc,
        schema=vol.Schema({
            vol.Required(ATTR_MINIMUM_SOC): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_CHARGE_CAP,
        handle_set_charge_cap,
        schema=vol.Schema({
            vol.Required(ATTR_CHARGE_CAP): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_UPDATE_BATTERY_SETTINGS,
        handle_update_battery_settings,
        schema=vol.Schema({
            vol.Optional(ATTR_START_DISCHARGE): cv.string,
            vol.Optional(ATTR_END_DISCHARGE): cv.string,
            vol.Optional(ATTR_START_CHARGE): cv.string,
            vol.Optional(ATTR_END_CHARGE): cv.string,
            vol.Optional(ATTR_MINIMUM_SOC): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        })
    )
    
    # Register maintenance services
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_RECONNECT,
        handle_force_reconnect,
        schema=vol.Schema({})  # No parameters required
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_HEALTH_CHECK,
        handle_health_check,
        schema=vol.Schema({
            vol.Optional('entry_id'): cv.string
        })
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_TOGGLE_DIAGNOSTICS,
        handle_toggle_diagnostics,
        schema=vol.Schema({
            vol.Optional('enable'): cv.boolean,
            vol.Optional('entry_id'): cv.string
        })
    )
