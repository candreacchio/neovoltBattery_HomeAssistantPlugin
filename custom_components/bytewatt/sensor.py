"""Sensor platform for Byte-Watt integration."""
import logging
from typing import Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_SOC,
    SENSOR_GRID_CONSUMPTION,
    SENSOR_HOUSE_CONSUMPTION,
    SENSOR_BATTERY_POWER,
    SENSOR_PV,
    SENSOR_LAST_UPDATE,
    SENSOR_TOTAL_SOLAR,
    SENSOR_TOTAL_FEED_IN,
    SENSOR_TOTAL_BATTERY_CHARGE,
    SENSOR_PV_POWER_HOUSE,
    SENSOR_PV_CHARGING_BATTERY,
    SENSOR_TOTAL_HOUSE_CONSUMPTION,
    SENSOR_GRID_BATTERY_CHARGE,
    SENSOR_GRID_POWER_CONSUMPTION,
    SENSOR_PV_GENERATED_TODAY,
    SENSOR_CONSUMED_TODAY,
    SENSOR_FEED_IN_TODAY,
    SENSOR_GRID_IMPORT_TODAY,
    SENSOR_BATTERY_CHARGED_TODAY,
    SENSOR_BATTERY_DISCHARGED_TODAY,
    SENSOR_SELF_CONSUMPTION,
    SENSOR_SELF_SUFFICIENCY,
    SENSOR_TREES_PLANTED,
    SENSOR_CO2_REDUCTION,
    SENSOR_TOTAL_BATTERY_DISCHARGE,
    SENSOR_PV_POWER_L1,
    SENSOR_PV_POWER_L2,
    SENSOR_PV_POWER_L3,
    SENSOR_PV_POWER_L4,
    SENSOR_REAL_POWER_L1,
    SENSOR_REAL_POWER_L2,
    SENSOR_REAL_POWER_L3,
    SENSOR_METER_DC_POWER,
    SENSOR_EV_POWER,
    SENSOR_UPS_MODEL,
    SENSOR_HAS_SECONDARY_DATA,
    SENSOR_DATA_TYPE,
    SENSOR_FORCE_CHARGE_MODE,
    SENSOR_INVERTER_MODE,
    SENSOR_HAS_GENERATOR,
    SENSOR_HAS_CHARGING_PILE,
    SENSOR_GRID_DISCHARGE_TOTAL,
    SENSOR_BATTERY_TO_LOAD_TOTAL,
    SENSOR_EV_CHARGING_TOTAL,
    SENSOR_GRID_TO_LOAD_TOTAL,
    SENSOR_DIESEL_ENERGY_TOTAL,
    SENSOR_CONTROL_VARIANT,
    SENSOR_DETECTED_CONTROL_VARIANT,
    SENSOR_CONTROL_VARIANT_SOURCE,
    SENSOR_CONTROL_SYSTEM_ID,
    SENSOR_CONTROL_SUMMARY,
    SENSOR_FORCE_CHARGE_LIMIT,
    SENSOR_FORCE_CHARGE_STATUS,
    SENSOR_CYCLE_CHARGE_ACTIVE,
    SENSOR_CYCLE_DISCHARGE_ACTIVE,
    SENSOR_CYCLE_CHARGE_COUNT,
    SENSOR_CYCLE_DISCHARGE_COUNT,
    SENSOR_CYCLE_CHARGE_START,
    SENSOR_CYCLE_CHARGE_END,
    SENSOR_CYCLE_DISCHARGE_START,
    SENSOR_CYCLE_DISCHARGE_END,
    SENSOR_CYCLE_CHARGE_WINDOWS_JSON,
    SENSOR_CYCLE_DISCHARGE_WINDOWS_JSON,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Byte-Watt sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    # Define SOC sensors
    soc_sensors = [
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_SOC, 
            "Battery Percentage", 
            "battery", 
            "soc", 
            "%", 
            "mdi:battery"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_CONSUMPTION, 
            "Grid Consumption", 
            "power", 
            "pgrid", 
            "W", 
            "mdi:transmission-tower"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_HOUSE_CONSUMPTION, 
            "House Consumption", 
            "power", 
            "pload", 
            "W", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_POWER, 
            "Battery Power", 
            "power", 
            "pbat", 
            "W", 
            "mdi:battery-charging"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_PV, 
            "PV Power", 
            "power", 
            "ppv", 
            "W", 
            "mdi:solar-power"
        ),
        ByteWattLastUpdateSensor(
            coordinator, 
            entry, 
            SENSOR_LAST_UPDATE, 
            "Last Update", 
            "timestamp", 
            "", 
            "mdi:clock-outline",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_PV_POWER_L1,
            "PV Power L1",
            "power",
            "ppv1",
            "W",
            "mdi:solar-power-variant"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_PV_POWER_L2,
            "PV Power L2",
            "power",
            "ppv2",
            "W",
            "mdi:solar-power-variant"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_PV_POWER_L3,
            "PV Power L3",
            "power",
            "ppv3",
            "W",
            "mdi:solar-power-variant"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_PV_POWER_L4,
            "PV Power L4",
            "power",
            "ppv4",
            "W",
            "mdi:solar-power-variant"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_REAL_POWER_L1,
            "Real Power L1",
            "power",
            "prealL1",
            "W",
            "mdi:sine-wave"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_REAL_POWER_L2,
            "Real Power L2",
            "power",
            "prealL2",
            "W",
            "mdi:sine-wave"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_REAL_POWER_L3,
            "Real Power L3",
            "power",
            "prealL3",
            "W",
            "mdi:sine-wave"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_METER_DC_POWER,
            "Meter DC Power",
            "power",
            "pmeterDc",
            "W",
            "mdi:meter-electric-outline"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_EV_POWER,
            "EV Power",
            "power",
            "pev",
            "W",
            "mdi:car-electric"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_UPS_MODEL,
            "UPS Model",
            None,
            "upsModel",
            "",
            "mdi:battery-lock"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_HAS_SECONDARY_DATA,
            "Has Secondary Data",
            None,
            "hasSecData",
            "",
            "mdi:database-check-outline",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_DATA_TYPE,
            "Data Type",
            None,
            "dataType",
            "",
            "mdi:identifier",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_FORCE_CHARGE_MODE,
            "Force Charge Mode",
            None,
            "forceChargeMode",
            "",
            "mdi:battery-plus-variant",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_INVERTER_MODE,
            "Inverter Mode",
            None,
            "inverterMode",
            "",
            "mdi:power-settings",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CONTROL_VARIANT,
            "Control Variant",
            "effective_variant",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_DETECTED_CONTROL_VARIANT,
            "Detected Control Variant",
            "detected_variant",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CONTROL_VARIANT_SOURCE,
            "Control Variant Source",
            "variant_source",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CONTROL_SYSTEM_ID,
            "Control System ID",
            "system_id",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CONTROL_SUMMARY,
            "Control Summary",
            "summary",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_FORCE_CHARGE_LIMIT,
            "Force Charge Limit",
            "force_charge_limit",
            unit="%",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_FORCE_CHARGE_STATUS,
            "Force Charge Status",
            "force_charge_status",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_CHARGE_ACTIVE,
            "Cycle Charge Active",
            "cycle_charge_active",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_DISCHARGE_ACTIVE,
            "Cycle Discharge Active",
            "cycle_discharge_active",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_CHARGE_COUNT,
            "Cycle Charge Count",
            "cycle_charge_count",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_DISCHARGE_COUNT,
            "Cycle Discharge Count",
            "cycle_discharge_count",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_CHARGE_START,
            "Cycle Charge Start",
            "cycle_charge_start",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_CHARGE_END,
            "Cycle Charge End",
            "cycle_charge_end",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_DISCHARGE_START,
            "Cycle Discharge Start",
            "cycle_discharge_start",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_DISCHARGE_END,
            "Cycle Discharge End",
            "cycle_discharge_end",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_CHARGE_WINDOWS_JSON,
            "Cycle Charge Windows JSON",
            "cycle_charge_windows_json",
        ),
        ByteWattControlVariantSensor(
            coordinator,
            entry,
            SENSOR_CYCLE_DISCHARGE_WINDOWS_JSON,
            "Cycle Discharge Windows JSON",
            "cycle_discharge_windows_json",
        ),
    ]
    
    # Define grid stats sensors - modified to use "energy" device_class for kWh sensors
    grid_sensors = [
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_SOLAR, 
            "Total Solar Generation", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_Solar_Generation", 
            "kWh", 
            "mdi:solar-power"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_FEED_IN, 
            "Total Feed In", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_Feed_In", 
            "kWh", 
            "mdi:transmission-tower-export"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_BATTERY_CHARGE, 
            "Total Battery Charge", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_Battery_Charge", 
            "kWh", 
            "mdi:battery-charging"
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_TOTAL_BATTERY_DISCHARGE,
            "Total Battery Discharge",
            "energy",
            "Total_Battery_Discharge",
            "kWh",
            "mdi:battery-minus"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_POWER_HOUSE, 
            "PV Power to House", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "PV_Power_House", 
            "kWh", 
            "mdi:solar-power-variant"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_CHARGING_BATTERY, 
            "PV Charging Battery", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "PV_Charging_Battery", 
            "kWh", 
            "mdi:solar-power-variant-outline"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_HOUSE_CONSUMPTION, 
            "Total House Consumption", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_House_Consumption", 
            "kWh", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_BATTERY_CHARGE, 
            "Grid Based Battery Charge", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Grid_Based_Battery_Charge", 
            "kWh", 
            "mdi:transmission-tower-import"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_POWER_CONSUMPTION, 
            "Grid Power Consumption", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Grid_Power_Consumption", 
            "kWh", 
            "mdi:transmission-tower"
        ),
    ]
    
    
    # Define daily stats sensors
    daily_stats_sensors = [
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_GENERATED_TODAY, 
            "PV Generated Today", 
            "energy",
            "PV_Generated_Today", 
            "kWh", 
            "mdi:solar-power"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_CONSUMED_TODAY, 
            "Consumed Today", 
            "energy",
            "Consumed_Today", 
            "kWh", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_FEED_IN_TODAY, 
            "Feed In Today", 
            "energy",
            "Feed_In_Today", 
            "kWh", 
            "mdi:transmission-tower-export"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_IMPORT_TODAY, 
            "Grid Import Today", 
            "energy",
            "Grid_Import_Today", 
            "kWh", 
            "mdi:transmission-tower-import"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_CHARGED_TODAY, 
            "Battery Charged Today", 
            "energy",
            "Battery_Charged_Today", 
            "kWh", 
            "mdi:battery-plus"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_DISCHARGED_TODAY, 
            "Battery Discharged Today", 
            "energy",
            "Battery_Discharged_Today", 
            "kWh", 
            "mdi:battery-minus"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_SELF_CONSUMPTION, 
            "Self Consumption", 
            None,  # No device class for percentage
            "Self_Consumption", 
            "%", 
            "mdi:home-battery"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_SELF_SUFFICIENCY, 
            "Self Sufficiency", 
            None,  # No device class for percentage
            "Self_Sufficiency", 
            "%", 
            "mdi:home-battery-outline"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_TREES_PLANTED, 
            "Trees Planted", 
            None,
            "Trees_Planted", 
            "trees", 
            "mdi:tree"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_CO2_REDUCTION, 
            "CO2 Reduction", 
            None,
            "CO2_Reduction_Tons", 
            "tons", 
            "mdi:molecule-co2"
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_HAS_GENERATOR,
            "Has Generator",
            "",
            "hasGenerator",
            "",
            "mdi:generator-portable",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_HAS_CHARGING_PILE,
            "Has Charging Pile",
            "",
            "hasChargingPile",
            "",
            "mdi:ev-station",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_GRID_DISCHARGE_TOTAL,
            "Grid Discharge Total",
            "energy",
            "egriddischarge",
            "kWh",
            "mdi:transmission-tower-export"
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_BATTERY_TO_LOAD_TOTAL,
            "Battery To Load Total",
            "energy",
            "batLoad",
            "kWh",
            "mdi:battery-arrow-down-outline"
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_EV_CHARGING_TOTAL,
            "EV Charging Total",
            "energy",
            "echargingPile",
            "kWh",
            "mdi:car-electric"
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_GRID_TO_LOAD_TOTAL,
            "Grid To Load Total",
            "energy",
            "egrid2Load",
            "kWh",
            "mdi:home-import-outline"
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_DIESEL_ENERGY_TOTAL,
            "Diesel Energy Total",
            "energy",
            "ediesel",
            "kWh",
            "mdi:fuel"
        ),
    ]
    
    # Add dynamic inverter sensors based on discovered inverters
    # These will be created based on whatever inverters the API returns
    inverter_sensors = []
    
    # Power/status sensors for each inverter (from getLastPowerData API)
    inverter_power_attrs = [
        ("pv_power", "PV Power", "power", "ppv", "W", "mdi:solar-power"),
        ("battery_power", "Battery Power", "power", "pbat", "W", "mdi:battery-charging"),
        ("grid_power", "Grid Power", "power", "pgrid", "W", "mdi:transmission-tower"),
        ("house_power", "House Power", "power", "pload", "W", "mdi:home-lightning-bolt"),
        ("soc", "Battery SOC", "battery", "soc", "%", "mdi:battery"),
        ("pv_power_l1", "PV Power L1", "power", "ppv1", "W", "mdi:solar-power-variant"),
        ("pv_power_l2", "PV Power L2", "power", "ppv2", "W", "mdi:solar-power-variant"),
        ("pv_power_l3", "PV Power L3", "power", "ppv3", "W", "mdi:solar-power-variant"),
        ("pv_power_l4", "PV Power L4", "power", "ppv4", "W", "mdi:solar-power-variant"),
        ("real_power_l1", "Real Power L1", "power", "prealL1", "W", "mdi:transmission-tower-export"),
        ("real_power_l2", "Real Power L2", "power", "prealL2", "W", "mdi:transmission-tower-export"),
        ("real_power_l3", "Real Power L3", "power", "prealL3", "W", "mdi:transmission-tower-export"),
        ("force_charge_mode", "Force Charge Mode", None, "forceChargeMode", None, "mdi:battery-plus"),
        ("inverter_mode", "Inverter Mode", None, "inverterMode", None, "mdi:state-machine"),
    ]
    
    # Info sensors for each inverter (from getCustomMenuEssList API)
    inverter_info_attrs = [
        ("pv_capacity", "PV Capacity", None, "popv", "kWp", "mdi:solar-panel"),
        ("battery_capacity", "Battery Capacity", None, "cobat", "kWh", "mdi:battery"),
        ("on_grid_cap", "On-Grid Cap", None, "onGridCap", "kW", "mdi:transmission-tower"),
    ]
    
    # Try to get the inverter list from coordinator data if available
    # Otherwise, we'll create sensors that will be available once data is fetched
    inverter_list = []
    if coordinator.data and "inverter_list" in coordinator.data:
        inverter_list = coordinator.data.get("inverter_list", [])
    
    # If we don't have inverter data yet, create sensors with default inverter SNs
    # that will become available once the coordinator fetches the data
    if not inverter_list:
        # Default fallback - sensors will show as unavailable until first data fetch
        # The coordinator will populate inverter_list on its first successful update
        inverter_list = [
            {"sysSn": "25000SP2B5W00253"},
            {"sysSn": "25000SP2B5W00252"},
        ]
        _LOGGER.info("No inverter data yet, creating placeholder sensors that will update when data is available")
    
    # Create sensors for each discovered inverter
    for inverter in inverter_list:
        inverter_sn = inverter.get("sysSn")
        if not inverter_sn:
            continue
            
        # Create power sensors for this inverter
        for sensor_key, name, device_class, attr, unit, icon in inverter_power_attrs:
            inverter_sensors.append(
                ByteWattInverterSensor(
                    coordinator,
                    entry,
                    inverter_sn,
                    sensor_key,
                    name,
                    device_class,
                    attr,
                    unit,
                    icon,
                    None
                )
            )
        
        # Create info sensors for this inverter
        for sensor_key, name, device_class, attr, unit, icon in inverter_info_attrs:
            inverter_sensors.append(
                ByteWattInverterInfoSensor(
                    coordinator,
                    entry,
                    inverter_sn,
                    sensor_key,
                    name,
                    device_class,
                    attr,
                    unit,
                    icon,
                    EntityCategory.DIAGNOSTIC
                )
            )
    
    _LOGGER.info(f"Created {len(inverter_sensors)} dynamic inverter sensors for {len(inverter_list)} inverters")
    
    async_add_entities(soc_sensors + grid_sensors + daily_stats_sensors + inverter_sensors)


class ByteWattSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Byte-Watt Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
        name: str,
        device_class: str,
        attribute: str,
        unit: str,
        icon: str,
        entity_category: Optional[EntityCategory] = None,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = entity_category

    @property
    def device_info(self):
        """Return device info."""
        # Safely get username from config entry data
        username = "Unknown"
        if self._config_entry.data:
            username = self._config_entry.data.get('username', 'Unknown')
        
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": f"Byte-Watt Battery ({username})",
            "manufacturer": "Byte-Watt",
            "model": "Battery Monitor",
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "battery" not in self.coordinator.data:
                return None
            
            battery_data = self.coordinator.data["battery"]
            value = battery_data.get(self._attribute)
            
            if value is None:
                # First time encountering a missing attribute, log it at info level 
                # to help with troubleshooting new API responses
                _LOGGER.debug(
                    f"Attribute '{self._attribute}' not found in battery data for {self._attr_name}. "
                    f"Available attributes: {list(battery_data.keys())}"
                )
                return None
                
            # Return the value, converting string values to float if needed for numerical sensors
            if self._attr_device_class == "power" and isinstance(value, (str, int, float)):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return value
            return value
        except Exception as ex:
            _LOGGER.error(f"Error getting sensor state for {self._attr_name}: {ex}")
            return None


class ByteWattGridSensor(ByteWattSensor):
    """Representation of a Byte-Watt Grid Sensor."""

    def __init__(
        self,
        coordinator,
        config_entry,
        sensor_type,
        name,
        device_class,
        attribute,
        unit,
        icon,
        entity_category=None,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator, 
            config_entry, 
            sensor_type, 
            name, 
            device_class, 
            attribute, 
            unit, 
            icon,
            entity_category
        )
        # Daily counters can reset at midnight, so they should not advertise
        # total_increasing. Keep that only for true lifetime totals.
        lifetime_total_attributes = {
            "Total_Solar_Generation",
            "Total_Feed_In",
            "Total_Battery_Charge",
            "Total_Battery_Discharge",
            "PV_Power_House",
            "PV_Charging_Battery",
            "Total_House_Consumption",
            "Grid_Based_Battery_Charge",
            "Grid_Power_Consumption",
        }
        if unit == "kWh" and attribute in lifetime_total_attributes:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "battery" not in self.coordinator.data:
                return None
            
            # In the new API, all data is in the battery object
            # Try to find matching attributes in the battery data
            battery_data = self.coordinator.data["battery"]
            
            # Handle special case for energy metrics which may be in a different format
            if self._attribute in battery_data:
                value = battery_data.get(self._attribute)
                if value is None:
                    return None
                if self._attr_native_unit_of_measurement == "kWh":
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return None
                return value
            
            # If data isn't available, we'll log it at debug level
            _LOGGER.debug(f"Grid sensor {self._attribute} data not found in battery response")
            return None
        except Exception as ex:
            _LOGGER.error(f"Error getting grid sensor state: {ex}")
            return None
            
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Many grid sensors may not be available in the new API
        if not self.coordinator.data or "battery" not in self.coordinator.data:
            return False
            
        # Check if this attribute exists in the data
        return self._attribute in self.coordinator.data["battery"]


class ByteWattLastUpdateSensor(ByteWattSensor):
    """Representation of a Byte-Watt Last Update Sensor that doesn't rely on createTime."""
    
    def __init__(
        self,
        coordinator,
        config_entry,
        sensor_type,
        name,
        device_class,
        unit,
        icon,
        entity_category=None,
    ):
        """Initialize the Last Update sensor."""
        super().__init__(
            coordinator, 
            config_entry, 
            sensor_type, 
            name, 
            device_class, 
            "last_update",  # Use a custom attribute name
            unit, 
            icon,
            entity_category
        )

    @property
    def native_value(self):
        """Return the last update time based on coordinator's last successful update."""
        try:
            if hasattr(self.coordinator, '_last_successful_update') and self.coordinator._last_successful_update:
                return self.coordinator._last_successful_update
            return None
        except Exception as ex:
            _LOGGER.error(f"Error getting last update time: {ex}")
            return None
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return hasattr(self.coordinator, '_last_successful_update') and self.coordinator._last_successful_update is not None


class ByteWattControlVariantSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for Byte-Watt control variant metadata."""

    def __init__(self, coordinator, config_entry, sensor_type, name, key, unit: str | None = None):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if unit is not None:
            self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:tune-variant"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }

    @property
    def native_value(self):
        control_data = (self.coordinator.data or {}).get("control_variant", {})
        value = control_data.get(self._key)
        if value is None:
            cycle_strategy = control_data.get("cycle_strategy") or {}
            if self._key == "cycle_charge_active":
                value = bool((cycle_strategy.get("gridChargeCycle") or 0) == 1 and len(cycle_strategy.get("dayChargeTimeList") or []) > 0)
            elif self._key == "cycle_discharge_active":
                value = bool((cycle_strategy.get("ctrDisCycle") or 0) == 1 and len(cycle_strategy.get("dayDischargeTimeList") or []) > 0)
            elif self._key == "cycle_charge_count":
                value = len(cycle_strategy.get("dayChargeTimeList") or [])
            elif self._key == "cycle_discharge_count":
                value = len(cycle_strategy.get("dayDischargeTimeList") or [])
            elif self._key == "cycle_charge_start":
                first = (cycle_strategy.get("dayChargeTimeList") or [None])[0]
                value = first.get("beginTime") if first else None
            elif self._key == "cycle_charge_end":
                first = (cycle_strategy.get("dayChargeTimeList") or [None])[0]
                value = first.get("endTime") if first else None
            elif self._key == "cycle_discharge_start":
                first = (cycle_strategy.get("dayDischargeTimeList") or [None])[0]
                value = first.get("beginTime") if first else None
            elif self._key == "cycle_discharge_end":
                first = (cycle_strategy.get("dayDischargeTimeList") or [None])[0]
                value = first.get("endTime") if first else None
            elif self._key == "cycle_charge_windows_json":
                value = f"{len(cycle_strategy.get('dayChargeTimeList') or [])} windows"
            elif self._key == "cycle_discharge_windows_json":
                value = f"{len(cycle_strategy.get('dayDischargeTimeList') or [])} windows"
        if value is None:
            return None
        return value

    @property
    def available(self) -> bool:
        # Keep diagnostics available even if the latest refresh had partial data,
        # so restored state can be replaced as soon as attributes arrive.
        return self.coordinator.last_update_success or bool((self.coordinator.data or {}).get("control_variant"))

    @property
    def extra_state_attributes(self):
        control_data = (self.coordinator.data or {}).get("control_variant", {})
        attrs = {
            "configured_variant": control_data.get("configured_variant"),
            "detected_variant": control_data.get("detected_variant"),
            "effective_variant": control_data.get("effective_variant"),
            "variant_source": control_data.get("variant_source"),
            "host_sys_sn": control_data.get("host_sys_sn"),
            "target_system_id": control_data.get("target_system_id"),
            "target_sys_sn": control_data.get("target_sys_sn"),
            "target_selection_source": control_data.get("target_selection_source"),
            "cycle_charge_active": control_data.get("cycle_charge_active"),
            "cycle_discharge_active": control_data.get("cycle_discharge_active"),
        }
        cycle_strategy = control_data.get("cycle_strategy") or {}
        if cycle_strategy:
            attrs["executeCycleType"] = cycle_strategy.get("executeCycleType")
            attrs["gridChargeCycle"] = cycle_strategy.get("gridChargeCycle")
            attrs["ctrDisCycle"] = cycle_strategy.get("ctrDisCycle")
            attrs["dayChargeTimeList_count"] = len(cycle_strategy.get("dayChargeTimeList") or [])
            attrs["dayDischargeTimeList_count"] = len(cycle_strategy.get("dayDischargeTimeList") or [])
            if self._key == "cycle_charge_windows_json":
                attrs["windows"] = cycle_strategy.get("dayChargeTimeList") or []
            if self._key == "cycle_discharge_windows_json":
                attrs["windows"] = cycle_strategy.get("dayDischargeTimeList") or []
        candidates = control_data.get("system_candidates") or []
        if candidates:
            attrs["system_candidates"] = candidates
        if control_data.get("last_force_charge_action"):
            attrs["last_force_charge_action"] = control_data.get("last_force_charge_action")
            attrs["last_force_charge_requested_limit"] = control_data.get("last_force_charge_requested_limit")
            attrs["last_force_charge_updated_at"] = control_data.get("last_force_charge_updated_at")
            attrs["last_force_charge_results"] = control_data.get("last_force_charge_results")
        return attrs


class ByteWattInverterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Byte-Watt Per-Inverter Sensor (dynamic)."""
    
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        inverter_sn: str,
        sensor_key: str,
        name: str,
        device_class: str,
        attribute: str,
        unit: str,
        icon: str,
        entity_category: str = None,
    ):
        """Initialize the inverter sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._inverter_sn = inverter_sn
        self._sensor_key = sensor_key
        self._attr_name = f"{name} ({inverter_sn})"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attribute = attribute
        self._attr_entity_category = entity_category
        
        # Set unique_id - use the inverter SN directly
        self._attr_unique_id = f"bytewatt_{sensor_key}_{inverter_sn}"
        
        # Set entity registry enabled
        self._attr_entity_registry_enabled_default = True
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "inverters" not in self.coordinator.data:
                return None
            
            inverters_data = self.coordinator.data.get("inverters", {})
            inverter_data = inverters_data.get(self._inverter_sn, {})
            
            if not inverter_data:
                return None
            
            value = inverter_data.get(self._attribute)
            if value is None:
                return None
            
            # Convert to float if needed
            if self._attr_native_unit_of_measurement in ["W", "kWh", "%"]:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            
            return value
        except Exception as ex:
            _LOGGER.error(f"Error getting inverter sensor state: {ex}")
            return None
            
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data or "inverters" not in self.coordinator.data:
            return False
        return self._inverter_sn in self.coordinator.data.get("inverters", {})


class ByteWattInverterInfoSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Byte-Watt Per-Inverter Info Sensor (dynamic)."""
    
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        inverter_sn: str,
        sensor_key: str,
        name: str,
        device_class: str,
        attribute: str,
        unit: str,
        icon: str,
        entity_category: str = None,
    ):
        """Initialize the inverter info sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._inverter_sn = inverter_sn
        self._sensor_key = sensor_key
        self._attr_name = f"{name} ({inverter_sn})"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attribute = attribute
        self._attr_entity_category = entity_category
        
        # Set unique_id - use the inverter SN directly
        self._attr_unique_id = f"bytewatt_{sensor_key}_{inverter_sn}_info"
        
        # Set entity registry enabled
        self._attr_entity_registry_enabled_default = True
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "inverter_list" not in self.coordinator.data:
                return None
            
            inverter_list = self.coordinator.data.get("inverter_list", [])
            
            # Find the inverter in the list
            for inv in inverter_list:
                if inv.get("sysSn") == self._inverter_sn:
                    value = inv.get(self._attribute)
                    if value is None:
                        return None
                    
                    # Convert to appropriate type
                    if self._attr_native_unit_of_measurement in ["W", "kWh", "kWp", "%"]:
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return None
                    return value
            
            return None
        except Exception as ex:
            _LOGGER.error(f"Error getting inverter info sensor state: {ex}")
            return None
            
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data or "inverter_list" not in self.coordinator.data:
            return False
        inverter_list = self.coordinator.data.get("inverter_list", [])
        return any(inv.get("sysSn") == self._inverter_sn for inv in inverter_list)
