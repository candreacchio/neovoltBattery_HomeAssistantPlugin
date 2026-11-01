"""Sensor platform for Byte-Watt integration."""
import logging
from typing import Callable, Dict, Optional, Any
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
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
    SENSOR_BATTERY_STATE,
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
from .stacks import ROLE_HOST, derive_stack_state

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
            SensorDeviceClass.POWER,
            "pgrid",
            "W", 
            "mdi:transmission-tower"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_HOUSE_CONSUMPTION,
            "House Consumption",
            SensorDeviceClass.POWER,
            "pload",
            "W", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_POWER,
            "Battery Power",
            SensorDeviceClass.POWER,
            "pbat",
            "W", 
            "mdi:battery-charging"
        ),
        ByteWattBatteryStateSensor(
            coordinator, entry,
            SENSOR_BATTERY_STATE, "Battery State",
            "pbat", "mdi:battery-sync",
        ),
        ByteWattSensor(
            coordinator,
            entry,
            SENSOR_PV,
            "PV Power",
            SensorDeviceClass.POWER,
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
            SensorDeviceClass.ENERGY,
            "Total_Solar_Generation",
            "kWh",
            "mdi:solar-power",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_FEED_IN, 
            "Total Feed In", 
            SensorDeviceClass.ENERGY,
            "Total_Feed_In",
            "kWh",
            "mdi:transmission-tower-export",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_BATTERY_CHARGE, 
            "Total Battery Charge", 
            SensorDeviceClass.ENERGY,
            "Total_Battery_Charge",
            "kWh",
            "mdi:battery-charging",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator,
            entry,
            SENSOR_TOTAL_BATTERY_DISCHARGE,
            "Total Battery Discharge",
            SensorDeviceClass.ENERGY,
            "Total_Battery_Discharge",
            "kWh",
            "mdi:battery-minus",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_POWER_HOUSE, 
            "PV Power to House", 
            SensorDeviceClass.ENERGY,
            "PV_Power_House",
            "kWh",
            "mdi:solar-power-variant",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_CHARGING_BATTERY, 
            "PV Charging Battery", 
            SensorDeviceClass.ENERGY,
            "PV_Charging_Battery",
            "kWh",
            "mdi:solar-power-variant-outline",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_HOUSE_CONSUMPTION, 
            "Total House Consumption", 
            SensorDeviceClass.ENERGY,
            "Total_House_Consumption",
            "kWh",
            "mdi:home-lightning-bolt",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_BATTERY_CHARGE, 
            "Grid Based Battery Charge", 
            SensorDeviceClass.ENERGY,
            "Grid_Based_Battery_Charge",
            "kWh",
            "mdi:transmission-tower-import",
            cumulative=True,
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_POWER_CONSUMPTION, 
            "Grid Power Consumption", 
            SensorDeviceClass.ENERGY,
            "Grid_Power_Consumption",
            "kWh",
            "mdi:transmission-tower",
            cumulative=True,
        ),
    ]
    
    
    # Define daily stats sensors
    daily_stats_sensors = [
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_GENERATED_TODAY, 
            "PV Generated Today", 
            SensorDeviceClass.ENERGY,
            "PV_Generated_Today", 
            "kWh", 
            "mdi:solar-power"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_CONSUMED_TODAY, 
            "Consumed Today", 
            SensorDeviceClass.ENERGY,
            "Consumed_Today", 
            "kWh", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_FEED_IN_TODAY, 
            "Feed In Today", 
            SensorDeviceClass.ENERGY,
            "Feed_In_Today", 
            "kWh", 
            "mdi:transmission-tower-export"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_IMPORT_TODAY, 
            "Grid Import Today", 
            SensorDeviceClass.ENERGY,
            "Grid_Import_Today", 
            "kWh", 
            "mdi:transmission-tower-import"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_CHARGED_TODAY, 
            "Battery Charged Today", 
            SensorDeviceClass.ENERGY,
            "Battery_Charged_Today", 
            "kWh", 
            "mdi:battery-plus"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_DISCHARGED_TODAY, 
            "Battery Discharged Today", 
            SensorDeviceClass.ENERGY,
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
    
    stacks = (coordinator.data or {}).get("battery", {}).get("stacks", {})
    stack_sensors: list[SensorEntity] = []
    for sys_sn, stack in stacks.items():
        label = "Host" if stack.get("role") == ROLE_HOST else f"Follower {sys_sn}"
        stack_sensors.append(ByteWattStackSocSensor(coordinator, entry, sys_sn, label))
        stack_sensors.append(ByteWattStackPowerSensor(coordinator, entry, sys_sn, label))
        stack_sensors.append(ByteWattStackStateSensor(coordinator, entry, sys_sn, label))

    async_add_entities(soc_sensors + grid_sensors + daily_stats_sensors + stack_sensors)


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
        if device_class == SensorDeviceClass.POWER:
            self._attr_state_class = SensorStateClass.MEASUREMENT

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
            if self._attr_device_class == SensorDeviceClass.POWER and isinstance(value, (str, int, float)):
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
        cumulative=False,
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
        self._cumulative = cumulative
        self._last_valid_value = None
        # Use TOTAL for cumulative sensors to avoid HA interpreting minor API
        # value fluctuations as counter resets. Daily sensors keep
        # TOTAL_INCREASING since they legitimately reset to zero each day.
        if unit == "kWh":
            if cumulative:
                self._attr_state_class = SensorStateClass.TOTAL
            else:
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "battery" not in self.coordinator.data:
                return None

            battery_data = self.coordinator.data["battery"]

            if self._attribute not in battery_data:
                _LOGGER.debug(f"Grid sensor {self._attribute} data not found in battery response")
                return None

            value = battery_data.get(self._attribute)

            # For cumulative sensors, enforce monotonic values to prevent
            # dips caused by API returning temporarily lower readings.
            if self._cumulative and value is not None:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return value
                if (
                    self._last_valid_value is not None
                    and value < self._last_valid_value
                ):
                    _LOGGER.debug(
                        "Cumulative sensor %s decreased from %s to %s, returning cached value",
                        self._attribute, self._last_valid_value, value,
                    )
                    return self._last_valid_value
                self._last_valid_value = value

            return value
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


BATTERY_STATE_CHARGING = "Charging"
BATTERY_STATE_DISCHARGING = "Discharging"
BATTERY_STATE_IDLE = "Idle"
BATTERY_STATE_HYSTERESIS_W = 50


class ByteWattBatteryStateSensor(CoordinatorEntity, SensorEntity):
    """Sensor that derives battery state (Charging/Discharging/Idle) from pbat."""

    def __init__(self, coordinator, config_entry, sensor_type, name, attribute, icon):
        """Initialize the battery state sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [
            BATTERY_STATE_CHARGING,
            BATTERY_STATE_DISCHARGING,
            BATTERY_STATE_IDLE,
        ]
        self._attr_icon = icon
        self._current_state = BATTERY_STATE_IDLE

    @property
    def device_info(self):
        """Return device info."""
        username = self._config_entry.data.get("username", "Unknown") if self._config_entry.data else "Unknown"
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": f"Byte-Watt Battery ({username})",
            "manufacturer": "Byte-Watt",
            "model": "Battery Monitor",
        }

    @property
    def native_value(self):
        """Return Charging, Discharging, or Idle based on pbat with hysteresis."""
        try:
            if not self.coordinator.data or "battery" not in self.coordinator.data:
                return None

            pbat = self.coordinator.data["battery"].get(self._attribute)
            if pbat is None:
                return None
            pbat = float(pbat)

            # Hysteresis prevents rapid toggling when pbat fluctuates near zero
            # Positive pbat = discharging, negative pbat = charging
            if self._current_state == BATTERY_STATE_CHARGING:
                if pbat > BATTERY_STATE_HYSTERESIS_W:
                    self._current_state = BATTERY_STATE_DISCHARGING
                elif abs(pbat) <= BATTERY_STATE_HYSTERESIS_W:
                    self._current_state = BATTERY_STATE_IDLE
            elif self._current_state == BATTERY_STATE_DISCHARGING:
                if pbat < -BATTERY_STATE_HYSTERESIS_W:
                    self._current_state = BATTERY_STATE_CHARGING
                elif abs(pbat) <= BATTERY_STATE_HYSTERESIS_W:
                    self._current_state = BATTERY_STATE_IDLE
            else:  # Idle
                if pbat < -BATTERY_STATE_HYSTERESIS_W:
                    self._current_state = BATTERY_STATE_CHARGING
                elif pbat > BATTERY_STATE_HYSTERESIS_W:
                    self._current_state = BATTERY_STATE_DISCHARGING

            return self._current_state
        except (ValueError, TypeError):
            return None
        except Exception as ex:
            _LOGGER.error("Error getting battery state: %s", ex)
            return None


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


class _ByteWattStackSensorBase(CoordinatorEntity, SensorEntity):
    """Shared lookup for one inverter's own battery stack.

    Each physical stack (Host or a Follower) can only be charged/discharged
    by its own inverter, so automations need per-stack state rather than
    the blended bank SOC. ``coordinator.data["battery"]["stacks"][sys_sn]``
    is absent whenever this cycle's data couldn't be derived (not merely
    zero) — entities go unavailable rather than reporting 0 in that case.
    """

    def __init__(self, coordinator, config_entry: ConfigEntry, sys_sn: str, key: str):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sys_sn = sys_sn
        self._attr_unique_id = f"{config_entry.entry_id}_stack_{key}_{sys_sn}"

    @property
    def device_info(self):
        username = self._config_entry.data.get("username", "Unknown") if self._config_entry.data else "Unknown"
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": f"Byte-Watt Battery ({username})",
            "manufacturer": "Byte-Watt",
            "model": "Battery Monitor",
        }

    def _stack_data(self) -> Optional[Dict[str, Any]]:
        if not self.coordinator.data or "battery" not in self.coordinator.data:
            return None
        stacks = self.coordinator.data["battery"].get("stacks")
        if not stacks:
            return None
        return stacks.get(self._sys_sn)


class ByteWattStackSocSensor(_ByteWattStackSensorBase):
    """Per-stack SOC (%) — the SOC of just the battery this inverter can act on."""

    def __init__(self, coordinator, config_entry: ConfigEntry, sys_sn: str, label: str):
        super().__init__(coordinator, config_entry, sys_sn, "soc")
        self._attr_name = f"{label} Stack Battery"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:battery-high"

    @property
    def native_value(self):
        stack = self._stack_data()
        return stack.get("soc") if stack else None

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        stack = self._stack_data() or {}
        return {
            "sysSn": self._sys_sn,
            "capacity_kwh": stack.get("capacity_kwh"),
            "energy_kwh": stack.get("energy_kwh"),
            "sample_time": stack.get("sample_time"),
        }


class ByteWattStackPowerSensor(_ByteWattStackSensorBase):
    """Per-stack inverter AC power (W) — negative means that inverter is charging."""

    def __init__(self, coordinator, config_entry: ConfigEntry, sys_sn: str, label: str):
        super().__init__(coordinator, config_entry, sys_sn, "power")
        self._attr_name = f"{label} Stack Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "W"
        self._attr_icon = "mdi:transmission-tower"

    @property
    def native_value(self):
        stack = self._stack_data()
        return stack.get("power_w") if stack else None

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {"sysSn": self._sys_sn}


STACK_STATE_OPTIONS = ["full", "charging", "discharging", "empty"]


class ByteWattStackStateSensor(_ByteWattStackSensorBase):
    """Derived full/charging/discharging/empty state for one stack.

    Useful because a stack reading full or empty caps its inverter's
    charge/discharge power well before the blended bank SOC would suggest.
    """

    def __init__(self, coordinator, config_entry: ConfigEntry, sys_sn: str, label: str):
        super().__init__(coordinator, config_entry, sys_sn, "state")
        self._attr_name = f"{label} Stack State"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = STACK_STATE_OPTIONS
        self._attr_icon = "mdi:battery-sync"

    @property
    def native_value(self):
        stack = self._stack_data()
        if stack is None:
            return None
        return derive_stack_state(stack.get("soc"), stack.get("power_w"))

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {"sysSn": self._sys_sn}
