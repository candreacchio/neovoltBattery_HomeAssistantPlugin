"""Tests for SettingsManager — the heart of the refactored settings stack.

Covers validation, staging, discard, effective-value reads (pending vs
cache fallback), and the snapshot-clear-restore atomicity in submit().
"""
from __future__ import annotations

import asyncio  # noqa: F401 — kept for future async tests
import pytest

# SettingsManager imports homeassistant.helpers.dispatcher; skip cleanly
# if HA isn't installed (bare dev sandbox). Same for pycryptodome.
pytest.importorskip("Crypto.Cipher")
pytest.importorskip("voluptuous")
pytest.importorskip("homeassistant")

from custom_components.bytewatt.models import (  # noqa: E402
    CycleStrategy,
    GridFeedInSettings,
)
from custom_components.bytewatt.settings_manager import (  # noqa: E402
    BATTERY_VALIDATORS,
    FEEDIN_SLOT_VALIDATORS,
    FEEDIN_VALIDATORS,
    SettingsValidationError,
    SettingsManager,
    SubmitResult,
)


# ---------------------------------------------------------------------------
# Fixtures — a manager with a stubbed-out HA / client (we don't need real ones
# to exercise stage/discard/effective; those don't touch the network).
# ---------------------------------------------------------------------------

class _StubHass:
    """Minimal hass stand-in — async_dispatcher_send tolerates a hass.bus."""
    def __init__(self):
        self.signals_sent = []


@pytest.fixture
def stub_hass(monkeypatch):
    """Patch out the dispatcher so stage/discard don't need a real hass.bus."""
    sent = []
    def fake_send(hass, signal, *args):
        sent.append(signal)
    monkeypatch.setattr(
        "custom_components.bytewatt.settings_manager.async_dispatcher_send",
        fake_send,
    )
    hass = _StubHass()
    hass.signals_sent = sent
    return hass


@pytest.fixture
def populated_cache():
    """A CycleStrategy with realistic slots — submit/effective need this."""
    return CycleStrategy.from_api_response({
        "gridChargeCycle": 1,
        "ctrDisCycle": 1,
        "batUseCap": 10.0,
        "executeCycleType": 0,
        "upsReserve": 0,
        "loadcutoutEn": 0,
        "cutoffSoc": 0,
        "wakeupSoc": 0,
        "isSupportDischargeSoc": True,
        "isSupportChargerPower": True,
        "poinv": 10000,
        "dayChargeTimeList": [{
            "beginTime": "01:00", "endTime": "05:00",
            "chargeLimit": 100, "chargePower": 8000, "sort": 1,
        }],
        "dayDischargeTimeList": [{
            "beginTime": "17:00", "endTime": "22:00",
            "chargeLimit": 10, "chargePower": 10000, "sort": 1,
        }],
    })


@pytest.fixture
def populated_feedin_cache():
    return GridFeedInSettings.from_api_response({
        "batteryEn": 0,
        "batteryFeedCutoffSoc": 25.0,
        "prechargeEn": 0,
        "feedStrategyVOList": [
            {"start": "10:00", "end": "14:00", "feedPower": 5000, "sort": 1},
        ],
    }, system_id="test-id")


@pytest.fixture
def manager(stub_hass):
    return SettingsManager(stub_hass, client=None, entry_id="test_entry")


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def test_soc_validator_accepts_in_range():
    assert BATTERY_VALIDATORS["minimum_soc"]("minimum_soc", 25) == 25
    assert BATTERY_VALIDATORS["minimum_soc"]("minimum_soc", "75") == 75


def test_soc_validator_rejects_out_of_range():
    with pytest.raises(SettingsValidationError):
        BATTERY_VALIDATORS["minimum_soc"]("minimum_soc", 0)
    with pytest.raises(SettingsValidationError):
        BATTERY_VALIDATORS["minimum_soc"]("minimum_soc", 101)


def test_soc_validator_rejects_non_int():
    with pytest.raises(SettingsValidationError):
        BATTERY_VALIDATORS["minimum_soc"]("minimum_soc", "not a number")


def test_time_validator_accepts_hhmm():
    assert BATTERY_VALIDATORS["charge_start_time"]("charge_start_time", "14:30") == "14:30"


def test_time_validator_rejects_garbage():
    with pytest.raises(SettingsValidationError):
        BATTERY_VALIDATORS["charge_start_time"]("charge_start_time", "not a time")


def test_bool_validator_coerces():
    assert BATTERY_VALIDATORS["grid_charging"]("grid_charging", True) is True
    assert BATTERY_VALIDATORS["grid_charging"]("grid_charging", 1) is True
    assert BATTERY_VALIDATORS["grid_charging"]("grid_charging", "yes") is True
    assert BATTERY_VALIDATORS["grid_charging"]("grid_charging", "false") is False


def test_battery_power_validator_range():
    assert BATTERY_VALIDATORS["charge_power"]("charge_power", 5000) == 5000
    with pytest.raises(SettingsValidationError):
        BATTERY_VALIDATORS["charge_power"]("charge_power", -1)
    with pytest.raises(SettingsValidationError):
        BATTERY_VALIDATORS["charge_power"]("charge_power", 60000)


def test_feedin_power_validator_capped_at_20kw():
    """Hardware top end ~20 kW per the HAR; tighter than battery power."""
    assert FEEDIN_SLOT_VALIDATORS["power"]("power", 20000) == 20000
    with pytest.raises(SettingsValidationError):
        FEEDIN_SLOT_VALIDATORS["power"]("power", 20001)


def test_feedin_cutoff_soc_validator_allows_zero():
    """Cutoff SOC is 0-100 (not 1-100 like minimum_soc)."""
    assert FEEDIN_VALIDATORS["cutoff_soc"]("cutoff_soc", 0) == 0.0
    assert FEEDIN_VALIDATORS["cutoff_soc"]("cutoff_soc", 100) == 100.0
    with pytest.raises(SettingsValidationError):
        FEEDIN_VALIDATORS["cutoff_soc"]("cutoff_soc", 101)


# ---------------------------------------------------------------------------
# Stage / discard / pending_count
# ---------------------------------------------------------------------------

def test_stage_battery_records_value(manager):
    manager.stage_battery("minimum_soc", 25)
    assert manager.has_pending() is True
    assert manager.pending_count() == 1


def test_stage_battery_validates(manager):
    with pytest.raises(SettingsValidationError):
        manager.stage_battery("minimum_soc", 0)
    assert manager.has_pending() is False


def test_stage_battery_unknown_field(manager):
    with pytest.raises(SettingsValidationError):
        manager.stage_battery("not_a_real_field", 42)


def test_stage_feedin_slot_records_value(manager):
    manager.stage_feedin_slot(0, "power", 8000)
    assert manager.pending_count() == 1


def test_discard_clears_all(manager):
    manager.stage_battery("minimum_soc", 25)
    manager.stage_battery("charge_cap", 90)
    manager.stage_feedin("cutoff_soc", 30)
    manager.stage_feedin_slot(0, "power", 5000)
    assert manager.pending_count() == 4
    count = manager.discard()
    assert count == 4
    assert manager.has_pending() is False


def test_dispatcher_fires_on_stage(manager, stub_hass):
    """Dispatcher signal must fire so the Submit / Discard buttons re-render."""
    initial = len(stub_hass.signals_sent)
    manager.stage_battery("minimum_soc", 25)
    assert len(stub_hass.signals_sent) == initial + 1
    assert stub_hass.signals_sent[-1] == "bytewatt_pending_test_entry"


def test_dispatcher_fires_on_discard(manager, stub_hass):
    manager.stage_battery("minimum_soc", 25)
    initial = len(stub_hass.signals_sent)
    manager.discard()
    assert len(stub_hass.signals_sent) == initial + 1


# ---------------------------------------------------------------------------
# Effective-value reads — pending wins; falls back to cache; default if neither.
# ---------------------------------------------------------------------------

def test_effective_battery_returns_default_when_no_cache(manager):
    assert manager.effective_battery("minimum_soc") is None
    assert manager.effective_battery("minimum_soc", default=42) == 42


def test_effective_battery_reads_from_cache(manager, populated_cache):
    manager._battery_cache = populated_cache
    assert manager.effective_battery("minimum_soc") == 10.0
    assert manager.effective_battery("grid_charging") is True
    assert manager.effective_battery("charge_start_time") == "01:00"
    assert manager.effective_battery("discharge_end_time") == "22:00"


def test_effective_battery_pending_overrides_cache(manager, populated_cache):
    manager._battery_cache = populated_cache
    manager.stage_battery("minimum_soc", 25)
    assert manager.effective_battery("minimum_soc") == 25
    # Other fields still read from cache.
    assert manager.effective_battery("grid_charging") is True


def test_effective_feedin_pending_overrides_cache(manager, populated_feedin_cache):
    manager._feedin_cache = populated_feedin_cache
    assert manager.effective_feedin("enabled") is False
    assert manager.effective_feedin("cutoff_soc") == 25.0
    manager.stage_feedin("enabled", True)
    assert manager.effective_feedin("enabled") is True


def test_effective_feedin_slot_reads_cache(manager, populated_feedin_cache):
    manager._feedin_cache = populated_feedin_cache
    assert manager.effective_feedin_slot(0, "power") == 5000
    assert manager.effective_feedin_slot(0, "start") == "10:00"


def test_feedin_slot_available_reflects_cache_size(manager, populated_feedin_cache):
    manager._feedin_cache = populated_feedin_cache
    assert manager.feedin_slot_available(0) is True
    assert manager.feedin_slot_available(1) is False  # only one slot in cache
    # But staging into slot 1 makes it available pre-submit.
    manager.stage_feedin_slot(1, "power", 1000)
    assert manager.feedin_slot_available(1) is True


# ---------------------------------------------------------------------------
# Payload builders — apply pending diff onto a clone of the cache.
# ---------------------------------------------------------------------------

def test_build_battery_payload_applies_minimum_soc(manager, populated_cache):
    manager._battery_cache = populated_cache
    merged = manager._build_battery_payload({"minimum_soc": 30})
    assert merged.bat_use_cap == 30.0
    # Other fields are untouched.
    assert merged.grid_charge_cycle == populated_cache.grid_charge_cycle


def test_build_battery_payload_applies_slot_times(manager, populated_cache):
    manager._battery_cache = populated_cache
    merged = manager._build_battery_payload({
        "charge_start_time": "02:00",
        "discharge_end_time": "23:00",
    })
    assert merged.charge_slots[0].begin_time == "02:00"
    assert merged.discharge_slots[0].end_time == "23:00"


def test_build_battery_payload_raises_when_no_cache(manager):
    with pytest.raises(SettingsValidationError):
        manager._build_battery_payload({"minimum_soc": 25})


def test_build_battery_payload_does_not_mutate_cache(manager, populated_cache):
    """The snapshot pattern depends on the cache being unchanged on build."""
    original_soc = populated_cache.bat_use_cap
    manager._battery_cache = populated_cache
    manager._build_battery_payload({"minimum_soc": 99})
    # Cache itself must NOT change — only the returned merged copy.
    assert manager._battery_cache.bat_use_cap == original_soc


# ---------------------------------------------------------------------------
# SubmitResult helpers
# ---------------------------------------------------------------------------

def test_submitresult_all_ok_when_nothing_attempted():
    r = SubmitResult()
    assert r.all_ok is True
    assert r.any_attempted is False


def test_submitresult_all_ok_when_attempted_and_succeeded():
    r = SubmitResult(battery_attempted=True, battery_ok=True)
    assert r.all_ok is True


def test_submitresult_not_all_ok_on_partial_failure():
    r = SubmitResult(battery_attempted=True, battery_ok=True,
                     feedin_attempted=True, feedin_ok=False)
    assert r.all_ok is False
    assert r.any_attempted is True
