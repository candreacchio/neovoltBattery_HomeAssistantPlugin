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

# Sensor types
SENSOR_SOC = "soc"
SENSOR_GRID_CONSUMPTION = "grid_consumption"
SENSOR_HOUSE_CONSUMPTION = "house_consumption"
SENSOR_BATTERY_POWER = "battery_power"
SENSOR_PV = "pv_power"
SENSOR_LAST_UPDATE = "last_update"

# Battery settings sensor types
SENSOR_DISCHARGE_START = "discharge_start_time"
SENSOR_DISCHARGE_END = "discharge_end_time"
SENSOR_CHARGE_START = "charge_start_time"
SENSOR_CHARGE_END = "charge_end_time"
SENSOR_MIN_SOC = "minimum_soc"
SENSOR_CHARGE_CAP = "charge_cap"

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
AUTO_RECONNECT_INTERVAL_HOURS = 24  # 24 hours
HTTPS_PORT = 443
