from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

INVERTER_STATUS_OPTIONS = ["normal", "fault", "offline", "protection", "unknown"]
POWER_KEYS = ("soc", "pbat", "ppv", "pload", "pgrid")


def device_prefix(entry_id: str) -> str:
    return f"{entry_id}_inverter_"


def normalize_status(raw: Any) -> str:
    value = raw.strip().lower() if isinstance(raw, str) else ""
    return value if value in INVERTER_STATUS_OPTIONS else "unknown"


def _float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def inverter_label(system: Dict[str, Any]) -> str:
    for key in ("sysName", "remark"):
        if isinstance(system.get(key), str) and system[key].strip():
            return system[key].strip()
    sys_sn = str(system.get("sysSn") or "")
    return f"Inverter {sys_sn[-4:]}" if sys_sn else "Inverter"


def apply_system_list(
    inverters: Dict[str, Dict[str, Any]], systems: Iterable[Any], host_id: str, now: datetime
) -> List[str]:
    seen: List[str] = []
    for system in systems or []:
        if not isinstance(system, dict) or not system.get("sysSn"):
            continue
        sys_sn = str(system["sysSn"])
        seen.append(sys_sn)
        system_id = str(system.get("systemId") or "")
        inverters.setdefault(sys_sn, {"power": None, "power_updated": None}).update({
            "name": inverter_label(system),
            "is_host": bool(host_id) and system_id == host_id,
            "status": normalize_status(system.get("emsStatus")),
            "status_raw": system.get("emsStatus"),
            "status_updated": now,
            "inverter_model": system.get("minv"),
            "battery_model": system.get("mbat"),
            "ems_version": system.get("emsVersion"),
            "inverter_power_kw": _float(system.get("poinv")),
            "pv_capacity_kw": _float(system.get("popv")),
            "battery_capacity_kwh": _float(system.get("cobat")),
            "usable_capacity_kwh": _float(system.get("surpluscobat")),
        })
    return seen


def apply_power_data(
    inverters: Dict[str, Dict[str, Any]], sys_sn: str, data: Any, now: datetime
) -> bool:
    entry = inverters.get(sys_sn)
    if entry is None or not isinstance(data, dict) or _float(data.get("soc")) is None:
        return False
    entry["power"] = {key: _float(data.get(key)) for key in POWER_KEYS}
    entry["power_updated"] = now
    return True


def apply_versions(
    inverters: Dict[str, Dict[str, Any]], versions: Dict[str, Dict[str, str]], now: datetime
) -> None:
    for sys_sn, entry in inverters.items():
        entry.update(versions.get(sys_sn) or {})
        entry["versions_checked"] = now


def firmware(inv: Dict[str, Any]) -> Optional[str]:
    parts = [
        f"{label} {inv[key]}"
        for label, key in (("EMS", "ems_version"), ("BMS", "bms_version"),
                           ("Inverter", "inverter_version"))
        if inv.get(key)
    ]
    return " · ".join(parts) or None


def is_fresh(updated: Optional[datetime], now: datetime, max_age_s: float) -> bool:
    return updated is not None and (now - updated).total_seconds() <= max_age_s


class ByteWattInverterEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, sys_sn: str, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sys_sn = sys_sn
        self._attr_unique_id = f"{entry.entry_id}_inverter_{sys_sn}_{key}"

    @property
    def inverter(self) -> Dict[str, Any]:
        return self.coordinator.inverters.get(self._sys_sn) or {}

    def _fresh_power(self) -> bool:
        return is_fresh(self.inverter.get("power_updated"), dt_util.utcnow(),
                        self.coordinator.inverter_stale_after)

    def _fresh_status(self) -> bool:
        return is_fresh(self.inverter.get("status_updated"), dt_util.utcnow(),
                        self.coordinator.inverter_status_stale_after)

    @property
    def device_info(self) -> DeviceInfo:
        inv = self.inverter
        return DeviceInfo(
            identifiers={(DOMAIN, device_prefix(self._entry.entry_id) + self._sys_sn)},
            name=f"ByteWatt Inverter {inv.get('name') or self._sys_sn[-4:]}",
            manufacturer="Byte-Watt",
            model=inv.get("inverter_model") or "Inverter",
            sw_version=firmware(inv),
            serial_number=self._sys_sn,
            via_device=(DOMAIN, self._entry.entry_id),
        )


def async_add_inverter_entities(
    coordinator, entry, async_add_entities, factory: Callable[[str], Iterable[Any]]
) -> None:
    known: set = set()

    @callback
    def _add_new() -> None:
        known.intersection_update(coordinator.inverters)
        new = [sn for sn in coordinator.inverters if sn not in known]
        known.update(new)
        if new:
            async_add_entities([entity for sn in new for entity in factory(sn)])

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
