"""Data models for the Byte-Watt integration."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


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
            begin_time=data.get("beginTime", "00:00"),
            end_time=data.get("endTime", "00:00"),
            charge_limit=float(data.get("chargeLimit", 100.0)),
            charge_power=int(data.get("chargePower", 8000)),
            sort=int(data.get("sort", 1)),
            weeks=data.get("weeks", [7, 1, 2, 3, 4, 5, 6]),
            feed_mode=int(data.get("feedMode", 0)),
            equip_group_id=int(data.get("equipGroupId", 0)),
            feed_power=int(data.get("feedPower", 0)),
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
            begin_time=data.get("beginTime", "00:00"),
            end_time=data.get("endTime", "00:00"),
            charge_limit=float(data.get("chargeLimit", 10.0)),
            charge_power=int(data.get("chargePower", 10000)),
            sort=int(data.get("sort", 1)),
            weeks=data.get("weeks", [7, 1, 2, 3, 4, 5, 6]),
            feed_mode=int(data.get("feedMode", 0)),
            equip_group_id=int(data.get("equipGroupId", 0)),
            feed_power=int(data.get("feedPower", 0)),
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
    """
    Battery cycle strategy — maps to getCycleStrategy / setCycleStrategy.

    Replaces the old BatterySettings model.
    Property aliases are provided so existing code that reads
    bat_use_cap, grid_charge, ctr_dis, time_chaf1a etc. keeps working.
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

    # Time slot lists (Time1 only exposed in HA)
    charge_slots: List[ChargeSlot] = field(default_factory=list)
    discharge_slots: List[DischargeSlot] = field(default_factory=list)

    # Raw data preserved for round-tripping unknown fields
    raw_data: Dict[str, Any] = field(default_factory=dict)
    last_updated: Optional[str] = None

    # ------------------------------------------------------------------
    # Compatibility aliases so switch.py / number.py / time.py keep working
    # ------------------------------------------------------------------

    @property
    def grid_charge(self) -> int:
        return self.grid_charge_cycle

    @grid_charge.setter
    def grid_charge(self, v: int) -> None:
        self.grid_charge_cycle = v

    @property
    def ctr_dis(self) -> int:
        return self.ctr_dis_cycle

    @ctr_dis.setter
    def ctr_dis(self, v: int) -> None:
        self.ctr_dis_cycle = v

    # Charge slot 0 time aliases
    @property
    def time_chaf1a(self) -> str:
        return self.charge_slots[0].begin_time if self.charge_slots else "00:00"

    @time_chaf1a.setter
    def time_chaf1a(self, v: str) -> None:
        if self.charge_slots:
            self.charge_slots[0].begin_time = v

    @property
    def time_chae1a(self) -> str:
        return self.charge_slots[0].end_time if self.charge_slots else "00:00"

    @time_chae1a.setter
    def time_chae1a(self, v: str) -> None:
        if self.charge_slots:
            self.charge_slots[0].end_time = v

    # bat_high_cap alias → charge_slots[0].charge_limit
    @property
    def bat_high_cap(self) -> str:
        if self.charge_slots:
            return str(int(self.charge_slots[0].charge_limit))
        return "100"

    @bat_high_cap.setter
    def bat_high_cap(self, v) -> None:
        if self.charge_slots:
            self.charge_slots[0].charge_limit = float(v)

    # Discharge slot 0 time aliases
    @property
    def time_disf1a(self) -> str:
        return self.discharge_slots[0].begin_time if self.discharge_slots else "00:00"

    @time_disf1a.setter
    def time_disf1a(self, v: str) -> None:
        if self.discharge_slots:
            self.discharge_slots[0].begin_time = v

    @property
    def time_dise1a(self) -> str:
        return self.discharge_slots[0].end_time if self.discharge_slots else "00:00"

    @time_dise1a.setter
    def time_dise1a(self, v: str) -> None:
        if self.discharge_slots:
            self.discharge_slots[0].end_time = v

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
            grid_charge_cycle=int(data.get("gridChargeCycle", 1)),
            ctr_dis_cycle=int(data.get("ctrDisCycle", 1)),
            bat_use_cap=float(data.get("batUseCap", 10.0)),
            execute_cycle_type=int(data.get("executeCycleType", 0)),
            ups_reserve=int(data.get("upsReserve", 0)),
            loadcutout_en=int(data.get("loadcutoutEn", 0)),
            cutoff_soc=int(data.get("cutoffSoc", 0)),
            wakeup_soc=int(data.get("wakeupSoc", 0)),
            is_support_discharge_soc=bool(data.get("isSupportDischargeSoc", True)),
            is_support_charger_power=bool(data.get("isSupportChargerPower", True)),
            poinv=int(data.get("poinv", 10000)),
            charge_slots=charge_slots,
            discharge_slots=discharge_slots,
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Build the PUT payload for setCycleStrategy."""
        result = dict(self.raw_data)  # preserve unknown fields
        result.update({
            "id": "",
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


# Alias so any code that still imports BatterySettings keeps working
BatterySettings = CycleStrategy


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
            id=data.get("id"),
            sys_sn=data.get("sysSn", ""),
            start=data.get("start", "00:00"),
            end=data.get("end", "00:00"),
            feed_power=int(data.get("feedPower", 0)),
            sort=int(data.get("sort", 1)),
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
            battery_en=int(data.get("batteryEn", 1)),
            battery_feed_cutoff_soc=float(data.get("batteryFeedCutoffSoc", 20.0)),
            precharge_en=int(data.get("prechargeEn", 0)),
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