"""Data models for the Byte-Watt integration."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Safe field-coercion helpers used by every from_api_response().
#
# dict.get(key, default) returns `default` only when the KEY is missing —
# if the API sends `"foo": null` or `"foo": ""`, dict.get returns the
# null/empty string and the subsequent int()/float() call raises TypeError
# or ValueError. The whole settings refresh then fails and entities go
# unavailable. These helpers coerce missing / null / empty / non-numeric
# values to the supplied default.
# ---------------------------------------------------------------------------

def _safe_int(data: Dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(data: Dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(data: Dict[str, Any], key: str, default: bool) -> bool:
    """Boolean-coerce an API field, with string-aware semantics.

    bool("false") is True in Python because any non-empty string is
    truthy — that would silently flip the wrong way for an API that ever
    returns string booleans. Handle the common string forms explicitly
    so this helper does the right thing regardless of whether the
    server sends true/1/"true"/"1"/"yes"/"on".
    """
    value = data.get(key, default)
    if value is None:
        return default
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "1", "yes", "on", "y", "t"):
            return True
        if lower in ("false", "0", "no", "off", "n", "f", ""):
            return False
        # Unknown string — log + fall back to default rather than guess.
        return default
    return bool(value)


def _safe_str(data: Dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if value is None:
        return default
    return str(value)


@dataclass
class SoCData:
    """Represents battery State of Charge data."""
    soc: float = 0
    grid_consumption: float = 0
    battery: float = 0
    house_consumption: float = 0
    create_time: str = ""
    pv: float = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "SoCData":
        return cls(
            soc=data.get("soc", 0),
            grid_consumption=data.get("gridConsumption", 0),
            battery=data.get("battery", 0),
            house_consumption=data.get("houseConsumption", 0),
            create_time=data.get("createTime", ""),
            pv=data.get("pv", 0),
        )


@dataclass
class GridData:
    """Represents grid energy data."""
    total_solar_generation: float = 0
    total_feed_in: float = 0
    total_battery_charge: float = 0
    total_battery_discharge: float = 0
    pv_power_house: float = 0
    pv_charging_battery: float = 0
    total_house_consumption: float = 0
    grid_based_battery_charge: float = 0
    grid_power_consumption: float = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "GridData":
        return cls(
            total_solar_generation=data.get("Total_Solar_Generation", 0),
            total_feed_in=data.get("Total_Feed_In", 0),
            total_battery_charge=data.get("Total_Battery_Charge", 0),
            total_battery_discharge=data.get("Total_Battery_Discharge", 0),
            pv_power_house=data.get("PV_Power_House", 0),
            pv_charging_battery=data.get("PV_Charging_Battery", 0),
            total_house_consumption=data.get("Total_House_Consumption", 0),
            grid_based_battery_charge=data.get("Grid_Based_Battery_Charge", 0),
            grid_power_consumption=data.get("Grid_Power_Consumption", 0),
        )


# ---------------------------------------------------------------------------
# New Cycle Strategy models — matches getCycleStrategy / setCycleStrategy
# ---------------------------------------------------------------------------

@dataclass
class ChargeSlot:
    """One charge time slot."""
    begin_time: str = "00:00"
    end_time: str = "00:00"
    charge_limit: float = 100.0    # Charging cutoff SOC %
    charge_power: int = 8000       # W
    sort: int = 1
    weeks: List[int] = field(default_factory=lambda: [7, 1, 2, 3, 4, 5, 6])
    feed_mode: int = 0
    equip_group_id: int = 0
    feed_power: int = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "ChargeSlot":
        return cls(
            begin_time=_safe_str(data, "beginTime", "00:00"),
            end_time=_safe_str(data, "endTime", "00:00"),
            charge_limit=_safe_float(data, "chargeLimit", 100.0),
            charge_power=_safe_int(data, "chargePower", 8000),
            sort=_safe_int(data, "sort", 1),
            weeks=data.get("weeks") or [7, 1, 2, 3, 4, 5, 6],
            feed_mode=_safe_int(data, "feedMode", 0),
            equip_group_id=_safe_int(data, "equipGroupId", 0),
            feed_power=_safe_int(data, "feedPower", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beginTime": self.begin_time,
            "endTime": self.end_time,
            "chargeLimit": self.charge_limit,
            "chargePower": self.charge_power,
            "sort": self.sort,
            "weeks": self.weeks,
            "feedMode": self.feed_mode,
            "equipGroupId": self.equip_group_id,
            "feedPower": self.feed_power,
        }


@dataclass
class DischargeSlot:
    """One discharge time slot."""
    begin_time: str = "00:00"
    end_time: str = "00:00"
    charge_limit: float = 10.0     # Discharging cutoff SOC %
    charge_power: int = 10000      # Battery discharge power W
    sort: int = 1
    weeks: List[int] = field(default_factory=lambda: [7, 1, 2, 3, 4, 5, 6])
    feed_mode: int = 0
    equip_group_id: int = 0
    feed_power: int = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DischargeSlot":
        return cls(
            begin_time=_safe_str(data, "beginTime", "00:00"),
            end_time=_safe_str(data, "endTime", "00:00"),
            charge_limit=_safe_float(data, "chargeLimit", 10.0),
            charge_power=_safe_int(data, "chargePower", 10000),
            sort=_safe_int(data, "sort", 1),
            weeks=data.get("weeks") or [7, 1, 2, 3, 4, 5, 6],
            feed_mode=_safe_int(data, "feedMode", 0),
            equip_group_id=_safe_int(data, "equipGroupId", 0),
            feed_power=_safe_int(data, "feedPower", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beginTime": self.begin_time,
            "endTime": self.end_time,
            "chargeLimit": self.charge_limit,
            "chargePower": self.charge_power,
            "sort": self.sort,
            "weeks": self.weeks,
            "feedMode": self.feed_mode,
            "equipGroupId": self.equip_group_id,
            "feedPower": self.feed_power,
        }


@dataclass
class CycleStrategy:
    """Battery cycle strategy — maps to getCycleStrategy / setCycleStrategy.

    Field names mirror the server-side JSON keys verbatim (snake_case).
    Entity code does NOT access these fields directly — it goes through
    SettingsManager, which translates logical names like ``minimum_soc``
    to the underlying slot/field. That keeps the model layer free of
    presentation concerns.
    """
    # Top-level flags
    grid_charge_cycle: int = 1      # gridChargeCycle  (grid charging enabled)
    ctr_dis_cycle: int = 1          # ctrDisCycle      (discharge time control)
    bat_use_cap: float = 10.0       # batUseCap        (global discharging cutoff SOC)
    execute_cycle_type: int = 0     # 0=every day, 1=every week
    ups_reserve: int = 0
    loadcutout_en: int = 0
    cutoff_soc: int = 0
    wakeup_soc: int = 0
    is_support_discharge_soc: bool = True
    is_support_charger_power: bool = True
    poinv: int = 10000

    # Time slot lists
    charge_slots: List[ChargeSlot] = field(default_factory=list)
    discharge_slots: List[DischargeSlot] = field(default_factory=list)

    # Echo of unknown GET fields so they round-trip through PUT
    raw_data: Dict[str, Any] = field(default_factory=dict)
    # Set by BatterySettingsAPI after fetch; used in to_dict() for the "id" field
    host_system_id: str = ""

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "CycleStrategy":
        charge_slots = [
            ChargeSlot.from_api_response(s)
            for s in (data.get("dayChargeTimeList") or [])
        ]
        discharge_slots = [
            DischargeSlot.from_api_response(s)
            for s in (data.get("dayDischargeTimeList") or [])
        ]
        return cls(
            grid_charge_cycle=_safe_int(data, "gridChargeCycle", 1),
            ctr_dis_cycle=_safe_int(data, "ctrDisCycle", 1),
            bat_use_cap=_safe_float(data, "batUseCap", 10.0),
            execute_cycle_type=_safe_int(data, "executeCycleType", 0),
            ups_reserve=_safe_int(data, "upsReserve", 0),
            loadcutout_en=_safe_int(data, "loadcutoutEn", 0),
            cutoff_soc=_safe_int(data, "cutoffSoc", 0),
            wakeup_soc=_safe_int(data, "wakeupSoc", 0),
            is_support_discharge_soc=_safe_bool(data, "isSupportDischargeSoc", True),
            is_support_charger_power=_safe_bool(data, "isSupportChargerPower", True),
            poinv=_safe_int(data, "poinv", 10000),
            charge_slots=charge_slots,
            discharge_slots=discharge_slots,
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Build the PUT payload for setCycleStrategy.

        The server's GET returns ``dayChargeTimeList``/``dayDischargeTimeList``
        but the PUT expects ``chargeTimeList``/``dischargeTimeList``
        (verified against a live HAR capture of the Byte-Watt portal).
        Pop the GET-side keys when echoing raw_data so they don't leak
        stale slot data into the PUT alongside our edits.
        """
        result = dict(self.raw_data)
        result.pop("dayChargeTimeList", None)
        result.pop("dayDischargeTimeList", None)
        result.update({
            "id": self.host_system_id,
            "batUseCap": self.bat_use_cap,
            "upsReserve": self.ups_reserve,
            "executeCycleType": self.execute_cycle_type,
            "loadcutoutEn": self.loadcutout_en,
            "wakeupSoc": self.wakeup_soc,
            "cutoffSoc": self.cutoff_soc,
            "gridChargeCycle": self.grid_charge_cycle,
            "ctrDisCycle": self.ctr_dis_cycle,
            "chargeTimeList": [s.to_dict() for s in self.charge_slots],
            "dischargeTimeList": [s.to_dict() for s in self.discharge_slots],
            "isSupportDischargeSoc": self.is_support_discharge_soc,
            "isSupportChargerPower": self.is_support_charger_power,
            "poinv": self.poinv,
        })
        return result


# ---------------------------------------------------------------------------
# Grid feed-in models (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class GridFeedInSlot:
    """One grid feed-in time slot."""
    id: Optional[int] = None
    sys_sn: str = ""
    start: str = "00:00"
    end: str = "00:00"
    feed_power: int = 0
    sort: int = 1

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "GridFeedInSlot":
        return cls(
            id=data.get("id"),  # may legitimately be None for new slots
            sys_sn=_safe_str(data, "sysSn", ""),
            start=_safe_str(data, "start", "00:00"),
            end=_safe_str(data, "end", "00:00"),
            feed_power=_safe_int(data, "feedPower", 0),
            sort=_safe_int(data, "sort", 1),
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "start": self.start,
            "end": self.end,
            "feedPower": self.feed_power,
            "sort": self.sort,
        }
        if self.id is not None:
            d["id"] = self.id
        if self.sys_sn:
            d["sysSn"] = self.sys_sn
        return d


@dataclass
class GridFeedInSettings:
    """Grid feed-in control settings."""
    system_id: str = ""
    battery_en: int = 1
    battery_feed_cutoff_soc: float = 20.0
    precharge_en: int = 0
    slots: List[GridFeedInSlot] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return bool(self.battery_en)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.battery_en = 1 if value else 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any], system_id: str = "") -> "GridFeedInSettings":
        slots = [GridFeedInSlot.from_api_response(s) for s in (data.get("feedStrategyVOList") or [])]
        return cls(
            system_id=system_id,
            battery_en=_safe_int(data, "batteryEn", 1),
            battery_feed_cutoff_soc=_safe_float(data, "batteryFeedCutoffSoc", 20.0),
            precharge_en=_safe_int(data, "prechargeEn", 0),
            slots=slots,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.system_id,
            "batteryEn": self.battery_en,
            "batteryFeedCutoffSoc": self.battery_feed_cutoff_soc,
            "prechargeEn": self.precharge_en,
            "feedStrategyDTOList": [s.to_dict() for s in self.slots],
        }