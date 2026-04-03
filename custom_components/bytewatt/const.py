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
CONF_INVERTER_SNS = "inverter_sns"
CONF_CONTROL_VARIANT = "control_variant"
CONF_CONTROL_TARGET_SYSTEM_ID = "control_target_system_id"

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
DEFAULT_INVERTER_SNS = "25000SP2B5W00252,25000SP2B5W00253"  # Comma-separated list

# Control variants
CONTROL_VARIANT_AUTO = "auto"
CONTROL_VARIANT_CHARGE_CONFIG = "charge_config"
CONTROL_VARIANT_CYCLE_STRATEGY = "cycle_strategy"
CONTROL_VARIANT_OPTIONS = [
    CONTROL_VARIANT_AUTO,
    CONTROL_VARIANT_CHARGE_CONFIG,
    CONTROL_VARIANT_CYCLE_STRATEGY,
]
DEFAULT_CONTROL_VARIANT = CONTROL_VARIANT_AUTO
DEFAULT_CONTROL_TARGET_SYSTEM_ID = ""

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
SERVICE_UPDATE_CYCLE_STRATEGY = "update_cycle_strategy"
SERVICE_SET_CYCLE_DAY_SCHEDULE = "set_cycle_day_schedule"
SERVICE_FORCE_CHARGE = "force_charge"
SERVICE_STOP_FORCE_CHARGE = "stop_force_charge"

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

# Additional read-only telemetry discovered in live cloud API
SENSOR_PV_POWER_L1 = "pv_power_l1"
SENSOR_PV_POWER_L2 = "pv_power_l2"
SENSOR_PV_POWER_L3 = "pv_power_l3"
SENSOR_PV_POWER_L4 = "pv_power_l4"
SENSOR_REAL_POWER_L1 = "real_power_l1"
SENSOR_REAL_POWER_L2 = "real_power_l2"
SENSOR_REAL_POWER_L3 = "real_power_l3"
SENSOR_METER_DC_POWER = "meter_dc_power"
SENSOR_EV_POWER = "ev_power"
SENSOR_UPS_MODEL = "ups_model"
SENSOR_HAS_SECONDARY_DATA = "has_secondary_data"
SENSOR_DATA_TYPE = "data_type"
SENSOR_FORCE_CHARGE_MODE = "force_charge_mode"
SENSOR_INVERTER_MODE = "inverter_mode"
SENSOR_HAS_GENERATOR = "has_generator"
SENSOR_HAS_CHARGING_PILE = "has_charging_pile"
SENSOR_GRID_DISCHARGE_TOTAL = "grid_discharge_total"
SENSOR_BATTERY_TO_LOAD_TOTAL = "battery_to_load_total"
SENSOR_EV_CHARGING_TOTAL = "ev_charging_total"
SENSOR_GRID_TO_LOAD_TOTAL = "grid_to_load_total"
SENSOR_DIESEL_ENERGY_TOTAL = "diesel_energy_total"
SENSOR_CONTROL_VARIANT = "control_variant"
SENSOR_DETECTED_CONTROL_VARIANT = "detected_control_variant"
SENSOR_CONTROL_VARIANT_SOURCE = "control_variant_source"
SENSOR_CONTROL_SYSTEM_ID = "control_system_id"
SENSOR_CONTROL_SUMMARY = "control_summary"
SENSOR_FORCE_CHARGE_LIMIT = "force_charge_limit"
SENSOR_FORCE_CHARGE_STATUS = "force_charge_status"
SENSOR_CYCLE_CHARGE_ACTIVE = "cycle_charge_active"
SENSOR_CYCLE_DISCHARGE_ACTIVE = "cycle_discharge_active"
SENSOR_CYCLE_CHARGE_COUNT = "cycle_charge_count"
SENSOR_CYCLE_DISCHARGE_COUNT = "cycle_discharge_count"
SENSOR_CYCLE_CHARGE_START = "cycle_charge_start"
SENSOR_CYCLE_CHARGE_END = "cycle_charge_end"
SENSOR_CYCLE_DISCHARGE_START = "cycle_discharge_start"
SENSOR_CYCLE_DISCHARGE_END = "cycle_discharge_end"
SENSOR_CYCLE_CHARGE_WINDOWS_JSON = "cycle_charge_windows_json"
SENSOR_CYCLE_DISCHARGE_WINDOWS_JSON = "cycle_discharge_windows_json"

# Circuit breaker and connection constants
MAX_DIAGNOSTIC_LOGS = 100
RECENT_DATA_THRESHOLD = 300  # 5 minutes in seconds
STALE_DATA_THRESHOLD = 3600  # 1 hour in seconds
AUTO_RECONNECT_INTERVAL_HOURS = 24  # 24 hours
HTTPS_PORT = 443

# Per-inverter sensor types
SENSOR_INVERTER_252_PV_POWER = "inverter_252_pv_power"
SENSOR_INVERTER_252_BATTERY_POWER = "inverter_252_battery_power"
SENSOR_INVERTER_252_GRID_POWER = "inverter_252_grid_power"
SENSOR_INVERTER_252_LOAD_POWER = "inverter_252_load_power"
SENSOR_INVERTER_252_SOC = "inverter_252_soc"

SENSOR_INVERTER_253_PV_POWER = "inverter_253_pv_power"
SENSOR_INVERTER_253_BATTERY_POWER = "inverter_253_battery_power"
SENSOR_INVERTER_253_GRID_POWER = "inverter_253_grid_power"
SENSOR_INVERTER_253_LOAD_POWER = "inverter_253_load_power"
SENSOR_INVERTER_253_SOC = "inverter_253_soc"

# Known inverter serial numbers
KNOWN_INVERTER_SNS = [
    "25000SP2B5W00252",
    "25000SP2B5W00253"
]
