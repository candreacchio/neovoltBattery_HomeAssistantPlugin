from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .inverters import ByteWattInverterEntity, async_add_inverter_entities


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_inverter_entities(
        coordinator, entry, async_add_entities,
        lambda sn: [ByteWattInverterProblemSensor(coordinator, entry, sn, "problem")],
    )


class ByteWattInverterProblemSensor(ByteWattInverterEntity, BinarySensorEntity):
    _attr_name = "Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def available(self) -> bool:
        return self._fresh_status()

    @property
    def is_on(self):
        status = self.inverter.get("status")
        return None if status in (None, "unknown") else status != "normal"
