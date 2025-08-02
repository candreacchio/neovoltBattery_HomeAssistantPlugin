"""Sensor platform for Byte-Watt integration."""
import logging
from typing import Callable, Dict, Optional, Any
from datetime import datetime

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
    ]
    
    async_add_entities(soc_sensors + grid_sensors + daily_stats_sensors)


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
        # Add state_class for energy sensors (kWh)
        if unit == "kWh":
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
                return battery_data.get(self._attribute)
            
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


