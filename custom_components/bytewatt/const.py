"""Constants for the Byte-Watt integration."""

DOMAIN = "bytewatt"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RECOVERY_ENABLED = "recovery_enabled"
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"
CONF_MAX_DATA_AGE = "max_data_age"
CONF_STALE_CHECKS_THRESHOLD = "stale_checks_threshold"
CONF_NOTIFY_ON_RECOVERY = "notify_on_recovery"
CONF_DIAGNOSTICS_MODE = "diagnostics_mode"
CONF_AUTO_RECONNECT_TIME = "auto_reconnect_time"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # 1 minute
MIN_SCAN_INTERVAL = 30  # 30 seconds
DEFAULT_RECOVERY_ENABLED = True
DEFAULT_HEARTBEAT_INTERVAL = 120  # 2 minutes
DEFAULT_MAX_DATA_AGE = 300  # 5 minutes
DEFAULT_STALE_CHECKS_THRESHOLD = 3
DEFAULT_NOTIFY_ON_RECOVERY = True
DEFAULT_DIAGNOSTICS_MODE = False
DEFAULT_AUTO_RECONNECT_TIME = "03:30:00"  # 3:30 AM

# Services
SERVICE_SET_DISCHARGE_TIME = "set_discharge_time"  # Legacy service
SERVICE_SET_DISCHARGE_START_TIME = "set_discharge_start_time"
SERVICE_SET_CHARGE_START_TIME = "set_charge_start_time"
SERVICE_SET_CHARGE_END_TIME = "set_charge_end_time"
SERVICE_SET_MINIMUM_SOC = "set_minimum_soc"
SERVICE_SET_CHARGE_CAP = "set_charge_cap"
SERVICE_UPDATE_BATTERY_SETTINGS = "update_battery_settings"
SERVICE_FORCE_RECONNECT = "force_reconnect"  # Force client reconnection for troubleshooting
SERVICE_HEALTH_CHECK = "health_check"  # Check connection health and return diagnostics
SERVICE_TOGGLE_DIAGNOSTICS = "toggle_diagnostics"  # Toggle diagnostic logging

# Service attributes
ATTR_END_DISCHARGE = "end_discharge"
ATTR_START_DISCHARGE = "start_discharge"
ATTR_START_CHARGE = "start_charge"
ATTR_END_CHARGE = "end_charge"
ATTR_MINIMUM_SOC = "minimum_soc"
ATTR_CHARGE_CAP = "charge_cap"
ATTR_ENTRY_ID = "entry_id"

# Sensor types
SENSOR_SOC = "soc"
SENSOR_GRID_CONSUMPTION = "grid_consumption"
SENSOR_HOUSE_CONSUMPTION = "house_consumption"
SENSOR_BATTERY_POWER = "battery_power"
SENSOR_PV = "pv_power"
SENSOR_LAST_UPDATE = "last_update"

# Grid stats sensor types
SENSOR_TOTAL_SOLAR = "total_solar_generation"
SENSOR_TOTAL_FEED_IN = "total_feed_in"
SENSOR_TOTAL_BATTERY_CHARGE = "total_battery_charge"
SENSOR_TOTAL_BATTERY_DISCHARGE = "total_battery_discharge"
SENSOR_PV_POWER_HOUSE = "pv_power_house"
SENSOR_PV_CHARGING_BATTERY = "pv_charging_battery"
SENSOR_TOTAL_HOUSE_CONSUMPTION = "total_house_consumption"
SENSOR_GRID_BATTERY_CHARGE = "grid_battery_charge"
SENSOR_GRID_POWER_CONSUMPTION = "grid_power_consumption"

# Daily stats sensor types
SENSOR_PV_GENERATED_TODAY = "pv_generated_today"
SENSOR_CONSUMED_TODAY = "consumed_today"
SENSOR_FEED_IN_TODAY = "feed_in_today"
SENSOR_GRID_IMPORT_TODAY = "grid_import_today"
SENSOR_BATTERY_CHARGED_TODAY = "battery_charged_today"
SENSOR_BATTERY_DISCHARGED_TODAY = "battery_discharged_today"
SENSOR_SELF_CONSUMPTION = "self_consumption"
SENSOR_SELF_SUFFICIENCY = "self_sufficiency"
SENSOR_TREES_PLANTED = "trees_planted"
SENSOR_CO2_REDUCTION = "co2_reduction_tons"

# Circuit breaker and connection constants
MAX_DIAGNOSTIC_LOGS = 100
RECENT_DATA_THRESHOLD = 300  # 5 minutes in seconds
STALE_DATA_THRESHOLD = 3600  # 1 hour in seconds
HTTPS_PORT = 443

# Grid Feed-in Control constants
SERVICE_SET_GRID_FEEDIN_ENABLED = "set_grid_feedin_enabled"
SERVICE_SET_GRID_FEEDIN_CUTOFF_SOC = "set_grid_feedin_cutoff_soc"
SERVICE_UPDATE_GRID_FEEDIN_SLOT = "update_grid_feedin_slot"

ATTR_FEEDIN_ENABLED = "feedin_enabled"
ATTR_FEEDIN_CUTOFF_SOC = "feedin_cutoff_soc"
ATTR_FEEDIN_SLOT = "slot"
ATTR_FEEDIN_START = "start_time"
ATTR_FEEDIN_END = "end_time"
ATTR_FEEDIN_POWER = "power_watts"

# Host inverter selection
CONF_HOST_SYSTEM_ID = "host_system_id"
CONF_HOST_SYS_SN = "host_sys_sn"

# Config entry schema version — bump and add an async_migrate_entry branch
# whenever you change the shape of entry.data.
CURRENT_ENTRY_VERSION = 2

# Maximum number of feed-in slots the inverter supports (per the
# timePeriodLimit field on getFeedStrategyList — confirmed against a HAR
# capture from the Byte-Watt portal).
FEEDIN_MAX_SLOTS = 6

# Practical max feed-in power in watts — hardware top end is ~20 kW on
# the inverters Byte-Watt targets. Used for both service-call validation
# and entity slider max.
FEEDIN_MAX_POWER_W = 20000

# Default charge power (watts) applied when auto-creating a charge slot that
# the inverter did not return. Matches the charge-power slider max in number.py.
DEFAULT_CHARGE_POWER_W = 10000


def signal_pending_changed(entry_id: str) -> str:
    """Dispatcher signal name for pending-store changes on a given entry."""
    return f"bytewatt_pending_{entry_id}"