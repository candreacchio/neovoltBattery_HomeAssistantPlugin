"""Tests for the dataclass models — especially the HAR-verified round-trip
between getCycleStrategy / setCycleStrategy field names.

These tests only need ``models.py`` itself (stdlib-only at the module
level), so they load it directly via importlib instead of going through
``custom_components.bytewatt`` — the package's ``__init__.py`` would
otherwise pull in homeassistant/voluptuous, which we don't want for
pure-model tests.
"""
from __future__ import annotations

import importlib.util
import os

import pytest


def _load_models_module():
    """Load models.py directly without triggering the package's __init__."""
    here = os.path.dirname(__file__)
    path = os.path.abspath(os.path.join(
        here, "..", "custom_components", "bytewatt", "models.py",
    ))
    spec = importlib.util.spec_from_file_location("bytewatt_models", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


models = _load_models_module()
ChargeSlot = models.ChargeSlot
DischargeSlot = models.DischargeSlot
CycleStrategy = models.CycleStrategy
GridFeedInSettings = models.GridFeedInSettings
GridFeedInSlot = models.GridFeedInSlot


# ---------------------------------------------------------------------------
# CycleStrategy: GET → model → PUT round-trip
# ---------------------------------------------------------------------------

GET_RESPONSE_SAMPLE = {
    "gridChargeCycle": 0,
    "ctrDisCycle": 0,
    "batUseCap": 5,
    "executeCycleType": 0,
    "upsReserve": 1,
    "loadcutoutEn": 0,
    "cutoffSoc": 0,
    "wakeupSoc": 0,
    "isSupportDischargeSoc": True,
    "isSupportChargerPower": True,
    "poinv": 10000,
    "dayChargeTimeList": [
        {"beginTime": "01:00", "endTime": "05:00", "chargeLimit": 100,
         "chargePower": 8000, "sort": 1},
    ],
    "dayDischargeTimeList": [
        {"beginTime": "17:00", "endTime": "23:00", "chargeLimit": 10,
         "chargePower": 10000, "sort": 1},
    ],
    # Server returns extra keys we don't model — they should round-trip via raw_data.
    "extraServerField": "preserve_me",
}


def test_from_api_response_parses_top_level_fields():
    s = CycleStrategy.from_api_response(GET_RESPONSE_SAMPLE)
    assert s.bat_use_cap == 5
    assert s.grid_charge_cycle == 0
    assert s.ctr_dis_cycle == 0
    assert s.ups_reserve == 1
    assert s.is_support_discharge_soc is True


def test_from_api_response_parses_slot_lists():
    s = CycleStrategy.from_api_response(GET_RESPONSE_SAMPLE)
    assert len(s.charge_slots) == 1
    assert s.charge_slots[0].begin_time == "01:00"
    assert s.charge_slots[0].end_time == "05:00"
    assert len(s.discharge_slots) == 1
    assert s.discharge_slots[0].end_time == "23:00"


def test_to_dict_renames_slot_keys_for_put():
    """GET uses dayChargeTimeList/dayDischargeTimeList; PUT uses chargeTimeList/dischargeTimeList.

    Confirmed against a live HAR capture from the Byte-Watt portal — this
    asymmetry is intentional and must NOT regress.
    """
    s = CycleStrategy.from_api_response(GET_RESPONSE_SAMPLE)
    s.host_system_id = "test-host-id"
    payload = s.to_dict()
    assert "chargeTimeList" in payload
    assert "dischargeTimeList" in payload
    # GET-side names must NOT appear in the PUT payload — they'd carry the
    # original (stale, unmodified) slots alongside our edits.
    assert "dayChargeTimeList" not in payload
    assert "dayDischargeTimeList" not in payload


def test_to_dict_includes_host_system_id_under_id_key():
    s = CycleStrategy.from_api_response(GET_RESPONSE_SAMPLE)
    s.host_system_id = "host-xyz"
    payload = s.to_dict()
    assert payload["id"] == "host-xyz"


def test_to_dict_preserves_unknown_server_fields():
    s = CycleStrategy.from_api_response(GET_RESPONSE_SAMPLE)
    payload = s.to_dict()
    # raw_data echo lets the server's new fields round-trip without us
    # needing to model them — except for the GET-side slot keys we deliberately strip.
    assert payload.get("extraServerField") == "preserve_me"


def test_to_dict_field_set_matches_har_capture():
    """Every field the Byte-Watt portal sends in its setCycleStrategy PUT.

    Captured from a live save on the portal — these are the keys the
    server requires (or at least always sends).
    """
    s = CycleStrategy.from_api_response(GET_RESPONSE_SAMPLE)
    s.host_system_id = "test"
    payload = s.to_dict()
    required_keys = {
        "id", "batUseCap", "upsReserve", "executeCycleType",
        "loadcutoutEn", "wakeupSoc", "cutoffSoc",
        "gridChargeCycle", "ctrDisCycle",
        "chargeTimeList", "dischargeTimeList",
        "isSupportDischargeSoc", "isSupportChargerPower", "poinv",
    }
    missing = required_keys - payload.keys()
    assert not missing, f"to_dict() missing required PUT fields: {missing}"


# ---------------------------------------------------------------------------
# GridFeedInSettings: round-trip
# ---------------------------------------------------------------------------

FEEDIN_GET_SAMPLE = {
    "batteryEn": 0,
    "batteryFeedCutoffSoc": 30.0,
    "poinv": 5000.0,
    "timePeriodLimit": 6,
    "batUseCap": 5.0,
    "feedStrategyVOList": [
        {"start": "00:00", "end": "00:15", "feedPower": "0",
         "sysSn": "TEST-SN", "sort": 1},
    ],
    "prechargeEn": 0,
    "prechargeSoc": None,
}


def test_feedin_from_api_response():
    s = GridFeedInSettings.from_api_response(FEEDIN_GET_SAMPLE, "test-system-id")
    assert s.system_id == "test-system-id"
    assert s.battery_en == 0
    assert s.battery_feed_cutoff_soc == 30.0
    assert len(s.slots) == 1
    assert s.slots[0].start == "00:00"
    assert s.slots[0].feed_power == 0


def test_feedin_to_dict_matches_har_post():
    """The saveFeedStrategy POST captured from the portal sent exactly these keys."""
    s = GridFeedInSettings.from_api_response(FEEDIN_GET_SAMPLE, "test-id")
    payload = s.to_dict()
    assert set(payload.keys()) == {
        "id", "batteryEn", "batteryFeedCutoffSoc",
        "prechargeEn", "feedStrategyDTOList",
    }
    assert payload["id"] == "test-id"


# ---------------------------------------------------------------------------
# ChargeSlot / DischargeSlot
# ---------------------------------------------------------------------------

def test_chargeslot_roundtrip():
    raw = {"beginTime": "02:00", "endTime": "06:00", "chargeLimit": 90,
           "chargePower": 5000, "sort": 1}
    slot = ChargeSlot.from_api_response(raw)
    out = slot.to_dict()
    for key in ("beginTime", "endTime", "chargeLimit", "chargePower", "sort"):
        assert out[key] == raw[key]


def test_dischargeslot_roundtrip():
    raw = {"beginTime": "17:00", "endTime": "22:00", "chargeLimit": 20,
           "chargePower": 8000, "sort": 1}
    slot = DischargeSlot.from_api_response(raw)
    out = slot.to_dict()
    for key in ("beginTime", "endTime", "chargeLimit", "chargePower", "sort"):
        assert out[key] == raw[key]


def test_gridfeedinslot_omits_optional_keys_when_unset():
    """sysSn and id are optional — the slot.to_dict should omit them when blank."""
    slot = GridFeedInSlot(start="00:00", end="01:00", feed_power=100, sort=1)
    out = slot.to_dict()
    assert "id" not in out
    assert "sysSn" not in out
    assert out["start"] == "00:00"
    assert out["feedPower"] == 100


# ---------------------------------------------------------------------------
# Safe coercion helpers — defensive parsing for API fields that might be
# missing, null, empty, or wrong-typed.
# ---------------------------------------------------------------------------

_safe_int = models._safe_int
_safe_float = models._safe_float
_safe_bool = models._safe_bool
_safe_str = models._safe_str


def test_safe_int_handles_missing_key():
    assert _safe_int({}, "x", 42) == 42


def test_safe_int_handles_explicit_none():
    """API sending `{"x": null}` used to crash `int(None)`."""
    assert _safe_int({"x": None}, "x", 42) == 42


def test_safe_int_handles_empty_string():
    assert _safe_int({"x": ""}, "x", 42) == 42


def test_safe_int_handles_non_numeric_string():
    assert _safe_int({"x": "not a number"}, "x", 42) == 42


def test_safe_int_passes_through_valid():
    assert _safe_int({"x": 100}, "x", 0) == 100
    assert _safe_int({"x": "100"}, "x", 0) == 100  # numeric string is fine


def test_safe_float_handles_none_and_strings():
    assert _safe_float({"x": None}, "x", 1.0) == 1.0
    assert _safe_float({"x": ""}, "x", 1.0) == 1.0
    assert _safe_float({"x": "abc"}, "x", 1.0) == 1.0
    assert _safe_float({"x": "2.5"}, "x", 0.0) == 2.5
    assert _safe_float({"x": 3}, "x", 0.0) == 3.0


def test_safe_bool_handles_string_false_correctly():
    """bool('false') is True in Python — must not regress."""
    assert _safe_bool({"x": "false"}, "x", True) is False
    assert _safe_bool({"x": "FALSE"}, "x", True) is False
    assert _safe_bool({"x": "0"}, "x", True) is False
    assert _safe_bool({"x": "no"}, "x", True) is False


def test_safe_bool_handles_string_true():
    assert _safe_bool({"x": "true"}, "x", False) is True
    assert _safe_bool({"x": "TRUE"}, "x", False) is True
    assert _safe_bool({"x": "1"}, "x", False) is True
    assert _safe_bool({"x": "yes"}, "x", False) is True


def test_safe_bool_handles_native_bool():
    assert _safe_bool({"x": True}, "x", False) is True
    assert _safe_bool({"x": False}, "x", True) is False


def test_safe_bool_handles_int():
    assert _safe_bool({"x": 1}, "x", False) is True
    assert _safe_bool({"x": 0}, "x", True) is False


def test_safe_bool_unknown_string_falls_back_to_default():
    """Unknown string shouldn't silently coerce — fall back to default."""
    assert _safe_bool({"x": "maybe"}, "x", True) is True
    assert _safe_bool({"x": "maybe"}, "x", False) is False


def test_safe_bool_handles_none():
    assert _safe_bool({"x": None}, "x", True) is True
    assert _safe_bool({"x": None}, "x", False) is False


def test_safe_str_handles_none():
    assert _safe_str({"x": None}, "x", "default") == "default"
    assert _safe_str({}, "x", "default") == "default"
    assert _safe_str({"x": "hello"}, "x", "") == "hello"
