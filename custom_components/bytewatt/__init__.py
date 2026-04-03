"""The Byte-Watt integration."""
import asyncio
import logging
import json

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .bytewatt_client import ByteWattClient
from .coordinator import ByteWattDataUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_CONTROL_VARIANT,
    CONF_CONTROL_TARGET_SYSTEM_ID,
    CONF_RECOVERY_ENABLED,
    CONF_HEARTBEAT_INTERVAL,
    CONF_MAX_DATA_AGE,
    CONF_STALE_CHECKS_THRESHOLD,
    CONF_NOTIFY_ON_RECOVERY,
    CONF_DIAGNOSTICS_MODE,
    CONF_AUTO_RECONNECT_TIME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_CONTROL_VARIANT,
    DEFAULT_CONTROL_TARGET_SYSTEM_ID,
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
    SERVICE_UPDATE_CYCLE_STRATEGY,
    SERVICE_SET_CYCLE_DAY_SCHEDULE,
    SERVICE_FORCE_RECONNECT,
    SERVICE_HEALTH_CHECK,
    SERVICE_TOGGLE_DIAGNOSTICS,
    SERVICE_FORCE_CHARGE,
    SERVICE_STOP_FORCE_CHARGE,
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
    
    # Get all configuration options with defaults
    options = entry.options or {}
    scan_interval = options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    control_variant = options.get(CONF_CONTROL_VARIANT, entry.data.get(CONF_CONTROL_VARIANT, DEFAULT_CONTROL_VARIANT))
    control_target_system_id = options.get(
        CONF_CONTROL_TARGET_SYSTEM_ID,
        entry.data.get(CONF_CONTROL_TARGET_SYSTEM_ID, DEFAULT_CONTROL_TARGET_SYSTEM_ID),
    )
    
    # Recovery options (can be added to config flow for future customization)
    recovery_options = {
        CONF_CONTROL_VARIANT: control_variant,
        CONF_CONTROL_TARGET_SYSTEM_ID: control_target_system_id,
        CONF_RECOVERY_ENABLED: options.get(CONF_RECOVERY_ENABLED, DEFAULT_RECOVERY_ENABLED),
        CONF_HEARTBEAT_INTERVAL: options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL),
        CONF_MAX_DATA_AGE: options.get(CONF_MAX_DATA_AGE, DEFAULT_MAX_DATA_AGE),
        CONF_STALE_CHECKS_THRESHOLD: options.get(CONF_STALE_CHECKS_THRESHOLD, DEFAULT_STALE_CHECKS_THRESHOLD),
        CONF_NOTIFY_ON_RECOVERY: options.get(CONF_NOTIFY_ON_RECOVERY, DEFAULT_NOTIFY_ON_RECOVERY),
        CONF_DIAGNOSTICS_MODE: options.get(CONF_DIAGNOSTICS_MODE, DEFAULT_DIAGNOSTICS_MODE),
        CONF_AUTO_RECONNECT_TIME: options.get(CONF_AUTO_RECONNECT_TIME, DEFAULT_AUTO_RECONNECT_TIME)
    }

    client = ByteWattClient(hass, username, password)

    coordinator = ByteWattDataUpdateCoordinator(
        hass,
        client=client,
        scan_interval=scan_interval,
        entry_id=entry.entry_id,
        options=recovery_options
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

    def _get_primary_coordinator():
        for entry in hass.config_entries.async_entries(DOMAIN):
            entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if entry_data and entry_data.get("coordinator"):
                return entry_data["coordinator"]
        return None

    def _store_force_charge_diagnostics(coordinator, action: str, limit: int | None, results: dict):
        diagnostics = {
            "last_force_charge_action": action,
            "last_force_charge_requested_limit": limit,
            "last_force_charge_results": results,
            "last_force_charge_updated_at": dt_util.now().isoformat(),
        }
        control_data = dict((coordinator.data or {}).get("control_variant", {}))
        control_data.update(diagnostics)
        coordinator._last_force_charge_diagnostics = diagnostics
        coordinator._control_variant_info = control_data
        if coordinator.data is not None:
            coordinator.data["control_variant"] = control_data

    def _resolve_force_charge_targets(call: ServiceCall, coordinator) -> list[dict]:
        control_data = (coordinator.data or {}).get("control_variant", {})
        inverters_data = (coordinator.data or {}).get("inverters", {})
        candidate_map = {
            candidate.get("system_id"): candidate
            for candidate in (control_data.get("system_candidates") or [])
            if candidate.get("system_id")
        }
        requested_system_id = call.data.get("system_id")
        requested_sys_sn = call.data.get("sys_sn")
        requested_charge_power = call.data.get("charge_power")

        if requested_system_id:
            candidate = candidate_map.get(requested_system_id, {})
            resolved_sys_sn = requested_sys_sn or candidate.get("sys_sn")
            current_soc = None
            if resolved_sys_sn:
                current_soc = (inverters_data.get(resolved_sys_sn) or {}).get("soc")
            return [{
                "system_id": requested_system_id,
                "sys_sn": resolved_sys_sn,
                "charge_power": requested_charge_power,
                "current_soc": current_soc,
            }]

        raw_targets = control_data.get("system_candidates") or []
        targets = []
        seen_system_ids = set()
        for candidate in raw_targets:
            system_id = candidate.get("system_id")
            if not system_id or system_id in seen_system_ids:
                continue
            seen_system_ids.add(system_id)
            try:
                default_power = int(float(candidate.get("poinv") or 5000))
            except (TypeError, ValueError):
                default_power = 5000
            targets.append({
                "system_id": system_id,
                "sys_sn": candidate.get("sys_sn"),
                "charge_power": requested_charge_power if requested_charge_power is not None else default_power,
                "current_soc": (inverters_data.get(candidate.get("sys_sn")) or {}).get("soc"),
            })

        if targets:
            return targets

        fallback_system_id = (
            control_data.get("control_system_id")
            or control_data.get("target_system_id")
            or control_data.get("system_id")
        )
        if not fallback_system_id:
            return []
        return [{
            "system_id": fallback_system_id,
            "sys_sn": requested_sys_sn,
            "charge_power": requested_charge_power,
            "current_soc": (inverters_data.get(requested_sys_sn) or {}).get("soc") if requested_sys_sn else None,
        }]

    async def handle_force_charge(call: ServiceCall):
        """Handle force-charge control for one or more ByteWatt systems."""
        coordinator = _get_primary_coordinator()
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False

        targets = _resolve_force_charge_targets(call, coordinator)
        if not targets:
            _LOGGER.error("No ByteWatt systems available for force charge")
            return False

        limit = int(call.data.get("limit", 95))
        results = {}
        all_ok = True
        attempted = False

        for target in targets:
            system_id = target["system_id"]
            current_soc = target.get("current_soc")
            if current_soc is not None and float(current_soc) >= limit:
                results[system_id] = {
                    "sys_sn": target.get("sys_sn"),
                    "charge_power": target.get("charge_power"),
                    "current_soc": current_soc,
                    "skipped": True,
                    "skip_reason": "soc_at_or_above_limit",
                    "api_ok": True,
                }
                continue

            attempted = True
            ok = await coordinator.client.force_charge(
                system_id=system_id,
                sys_sn=target.get("sys_sn"),
                limit=limit,
                charge_power=target.get("charge_power"),
            )
            results[system_id] = {
                "sys_sn": target.get("sys_sn"),
                "charge_power": target.get("charge_power"),
                "current_soc": current_soc,
                "api_ok": ok,
            }
            all_ok = all_ok and ok

        await asyncio.sleep(2)
        for system_id, result in results.items():
            result["status"] = await coordinator.client.get_force_charge_status(system_id)
            result["limit"] = await coordinator.client.get_force_charge_limit(system_id)

        verified_ok = True
        for result in results.values():
            if result.get("skipped"):
                continue
            applied_limit = result.get("limit")
            limit_matches = applied_limit is not None and abs(float(applied_limit) - limit) < 0.01
            if not (result.get("api_ok") and (result.get("status") is True or limit_matches)):
                verified_ok = False
                break

        if not attempted:
            _LOGGER.warning("Force charge skipped for all targets because SOC is already at or above %s%%", limit)
        _store_force_charge_diagnostics(coordinator, "force_charge", limit, results)
        _LOGGER.info("Force charge results: %s", results)
        await coordinator.async_request_refresh()
        return all_ok and verified_ok

    async def handle_stop_force_charge(call: ServiceCall):
        """Handle stopping force charge for one or more ByteWatt systems."""
        coordinator = _get_primary_coordinator()
        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False

        targets = _resolve_force_charge_targets(call, coordinator)
        if not targets:
            _LOGGER.error("No ByteWatt systems available to stop force charge")
            return False

        results = {}
        all_ok = True
        for target in targets:
            system_id = target["system_id"]
            ok = await coordinator.client.stop_force_charge(system_id=system_id)
            results[system_id] = {"api_ok": ok}
            all_ok = all_ok and ok

        await asyncio.sleep(2)
        for system_id, result in results.items():
            result["status"] = await coordinator.client.get_force_charge_status(system_id)
            result["limit"] = await coordinator.client.get_force_charge_limit(system_id)

        verified_ok = all(
            result["api_ok"] and result.get("status") is False
            for result in results.values()
            if result.get("status") is not None
        )
        _store_force_charge_diagnostics(coordinator, "stop_force_charge", None, results)
        _LOGGER.info("Stop force charge results: %s", results)
        await coordinator.async_request_refresh()
        return all_ok and verified_ok
    
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
        charge_start_time_2 = call.data.get("start_charge_2")
        charge_end_time_2 = call.data.get("end_charge_2")
        discharge_start_time_2 = call.data.get("start_discharge_2")
        discharge_end_time_2 = call.data.get("end_discharge_2")
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        charge_cap = call.data.get(ATTR_CHARGE_CAP)
        ups_reserve = call.data.get("ups_reserve")
        charge_mode_setting = call.data.get("charge_mode_setting")
        export_limit_w1 = call.data.get("export_limit_w1")
        export_limit_w2 = call.data.get("export_limit_w2")
        
        # Check if at least one parameter is provided
        if (discharge_start_time is None and discharge_end_time is None and
                charge_start_time is None and charge_end_time is None and
                charge_start_time_2 is None and charge_end_time_2 is None and
                discharge_start_time_2 is None and discharge_end_time_2 is None and
                minimum_soc is None and charge_cap is None and ups_reserve is None and
                charge_mode_setting is None and export_limit_w1 is None and export_limit_w2 is None):
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

        control_data = (coordinator.data or {}).get("control_variant", {})
        effective_variant = control_data.get("effective_variant")
        if effective_variant and effective_variant != "charge_config":
            _LOGGER.error(
                "Refusing legacy update_battery_settings write while control variant is '%s'; "
                "system appears to be using cycle-strategy controls",
                effective_variant,
            )
            return False
        
        # Update battery settings
        success = await coordinator.client.update_battery_settings(
            discharge_start_time=discharge_start_time,
            discharge_end_time=discharge_end_time,
            charge_start_time=charge_start_time,
            charge_end_time=charge_end_time,
            charge_start_time_2=charge_start_time_2,
            charge_end_time_2=charge_end_time_2,
            discharge_start_time_2=discharge_start_time_2,
            discharge_end_time_2=discharge_end_time_2,
            minimum_soc=minimum_soc,
            charge_cap=charge_cap,
            ups_reserve=ups_reserve,
            charge_mode_setting=charge_mode_setting,
            export_limit_w1=export_limit_w1,
            export_limit_w2=export_limit_w2,
        )
        
        if success:
            _LOGGER.info("Successfully updated battery settings")
        else:
            _LOGGER.error("Failed to update battery settings")
        
        return success

    async def handle_update_cycle_strategy(call: ServiceCall):
        """Handle cycle-strategy based discharge control updates."""
        charge_start_time = call.data.get(ATTR_START_CHARGE)
        charge_end_time = call.data.get(ATTR_END_CHARGE)
        charge_cap = call.data.get(ATTR_CHARGE_CAP)
        charge_power = call.data.get("charge_power")
        charge_enabled = call.data.get("charge_enabled")
        discharge_start_time = call.data.get(ATTR_START_DISCHARGE)
        discharge_end_time = call.data.get(ATTR_END_DISCHARGE)
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        discharge_power = call.data.get("discharge_power")
        discharge_enabled = call.data.get("discharge_enabled")

        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break

        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False

        control_data = (coordinator.data or {}).get("control_variant", {})
        system_id = control_data.get("system_id")
        target_system_id = call.data.get("system_id") or control_data.get("target_system_id") or system_id
        effective_variant = control_data.get("effective_variant")

        if effective_variant != "cycle_strategy":
            _LOGGER.error(
                "Refusing cycle strategy update because active control variant is '%s'",
                effective_variant,
            )
            return False

        if not target_system_id:
            _LOGGER.error("No cycle-strategy system_id detected")
            return False

        success = await coordinator.client.update_cycle_strategy(
            system_id=target_system_id,
            charge_start_time=charge_start_time,
            charge_end_time=charge_end_time,
            charge_cap=charge_cap,
            charge_power=charge_power,
            charge_enabled=charge_enabled,
            discharge_start_time=discharge_start_time,
            discharge_end_time=discharge_end_time,
            minimum_soc=minimum_soc,
            discharge_power=discharge_power,
            discharge_enabled=discharge_enabled,
        )

        if success:
            _LOGGER.info("Successfully updated cycle strategy")
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to update cycle strategy")

        return success

    async def handle_set_cycle_day_schedule(call: ServiceCall):
        """Handle full day cycle schedule updates for cycle-strategy systems."""
        coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            break

        if not coordinator:
            _LOGGER.error("No ByteWatt integration found")
            return False

        control_data = (coordinator.data or {}).get("control_variant", {})
        system_id = control_data.get("system_id")
        target_system_id = call.data.get("system_id") or control_data.get("target_system_id") or system_id
        effective_variant = control_data.get("effective_variant")

        if effective_variant != "cycle_strategy":
            _LOGGER.error(
                "Refusing cycle day schedule update because active control variant is '%s'",
                effective_variant,
            )
            return False

        if not target_system_id:
            _LOGGER.error("No cycle-strategy system_id detected")
            return False

        charge_windows = call.data.get("charge_windows")
        discharge_windows = call.data.get("discharge_windows")
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        charge_cap = call.data.get(ATTR_CHARGE_CAP)
        charge_power = call.data.get("charge_power")
        discharge_power = call.data.get("discharge_power")

        if isinstance(charge_windows, str):
            charge_windows = json.loads(charge_windows)
        if isinstance(discharge_windows, str):
            discharge_windows = json.loads(discharge_windows)

        _LOGGER.info(
            "Requested cycle day schedule update for %s with %s charge windows and %s discharge windows",
            target_system_id,
            len(charge_windows or []),
            len(discharge_windows or []),
        )

        success = await coordinator.client.update_cycle_strategy(
            system_id=target_system_id,
            charge_windows=charge_windows,
            discharge_windows=discharge_windows,
            charge_cap=charge_cap,
            minimum_soc=minimum_soc,
            charge_power=charge_power,
            discharge_power=discharge_power,
            charge_enabled=bool(charge_windows),
            discharge_enabled=bool(discharge_windows),
        )

        if success:
            _LOGGER.info(
                "Successfully updated cycle day schedule (%s charge windows, %s discharge windows)",
                len(charge_windows or []),
                len(discharge_windows or []),
            )
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to update cycle day schedule")

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
            vol.Optional(ATTR_CHARGE_CAP): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional("start_charge_2"): cv.string,
            vol.Optional("end_charge_2"): cv.string,
            vol.Optional("start_discharge_2"): cv.string,
            vol.Optional("end_discharge_2"): cv.string,
            vol.Optional("ups_reserve"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional("charge_mode_setting"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
            vol.Optional("export_limit_w1"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
            vol.Optional("export_limit_w2"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
        })
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CYCLE_STRATEGY,
        handle_update_cycle_strategy,
        schema=vol.Schema({
            vol.Optional(ATTR_START_CHARGE): cv.string,
            vol.Optional(ATTR_END_CHARGE): cv.string,
            vol.Optional(ATTR_CHARGE_CAP): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional("charge_power"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
            vol.Optional("charge_enabled"): cv.boolean,
            vol.Optional(ATTR_START_DISCHARGE): cv.string,
            vol.Optional(ATTR_END_DISCHARGE): cv.string,
            vol.Optional(ATTR_MINIMUM_SOC): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional("discharge_power"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
            vol.Optional("discharge_enabled"): cv.boolean,
            vol.Optional("system_id"): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CYCLE_DAY_SCHEDULE,
        handle_set_cycle_day_schedule,
        schema=vol.Schema({
            vol.Optional("charge_windows"): vol.Any(cv.string, list),
            vol.Optional("discharge_windows"): vol.Any(cv.string, list),
            vol.Optional(ATTR_MINIMUM_SOC): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional(ATTR_CHARGE_CAP): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional("charge_power"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
            vol.Optional("discharge_power"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
            vol.Optional("system_id"): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_CHARGE,
        handle_force_charge,
        schema=vol.Schema({
            vol.Optional("limit", default=95): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional("charge_power"): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
            vol.Optional("system_id"): cv.string,
            vol.Optional("sys_sn"): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_FORCE_CHARGE,
        handle_stop_force_charge,
        schema=vol.Schema({
            vol.Optional("system_id"): cv.string,
            vol.Optional("sys_sn"): cv.string,
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
