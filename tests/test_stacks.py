"""Tests for the per-stack role/capacity/SOC pure helpers in stacks.py.

These have no Home Assistant runtime dependency — plain dict/dataclass
fixtures modelling the getCustomMenuEssList / staticsByDay API shapes.
"""
from __future__ import annotations

import pytest

from custom_components.bytewatt.stacks import (
    ROLE_FOLLOWER,
    ROLE_HOST,
    StackSocSample,
    derive_stack_capacities,
    derive_stack_state,
    detect_roles,
    follower_sys_sns,
    pick_latest_stack_soc,
)

HOST_SN = "25000SP295W00658"
FOLLOWER_SN = "25000SP285W00998"


def _inverters(host_cobat=28.8, follower_cobat=9.6):
    return [
        {
            "sysSn": HOST_SN,
            "parallelGridMode": 1,
            "cobat": host_cobat,
            "remark": "Host",
        },
        {
            "sysSn": FOLLOWER_SN,
            "parallelGridMode": 2,
            "cobat": follower_cobat,
            "remark": "Follower",
        },
    ]


# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------

def test_detect_roles_maps_parallel_grid_mode():
    roles = detect_roles(_inverters())
    assert roles == {HOST_SN: ROLE_HOST, FOLLOWER_SN: ROLE_FOLLOWER}


def test_detect_roles_ignores_entries_without_sys_sn():
    inverters = [{"parallelGridMode": 1, "cobat": 10.0}]
    assert detect_roles(inverters) == {}


def test_detect_roles_ignores_unknown_parallel_grid_mode():
    inverters = [{"sysSn": "X", "parallelGridMode": 99, "cobat": 10.0}]
    assert detect_roles(inverters) == {}


def test_follower_sys_sns_excludes_host_and_unrelated_roles():
    inverters = _inverters() + [{"sysSn": "OTHER", "parallelGridMode": 1, "cobat": 5.0}]
    assert follower_sys_sns(inverters, HOST_SN) == [FOLLOWER_SN]


# ---------------------------------------------------------------------------
# Capacity derivation — Host cobat double-counts the whole bank
# ---------------------------------------------------------------------------

def test_derive_stack_capacities_backs_out_host_from_bank_total():
    """28.8 (bank, double-counted) - 9.6 (follower) = 19.2 (host's own stack)."""
    capacities = derive_stack_capacities(_inverters(), HOST_SN)
    assert capacities[HOST_SN] == pytest.approx(19.2)
    assert capacities[FOLLOWER_SN] == 9.6


def test_derive_stack_capacities_sums_multiple_followers():
    inverters = _inverters(host_cobat=38.4) + [
        {"sysSn": "FOLLOWER2", "parallelGridMode": 2, "cobat": 9.6},
    ]
    capacities = derive_stack_capacities(inverters, HOST_SN)
    assert capacities == {HOST_SN: 19.2, FOLLOWER_SN: 9.6, "FOLLOWER2": 9.6}


def test_derive_stack_capacities_empty_when_host_cobat_missing():
    inverters = [{"sysSn": FOLLOWER_SN, "parallelGridMode": 2, "cobat": 9.6}]
    assert derive_stack_capacities(inverters, HOST_SN) == {}


def test_derive_stack_capacities_empty_when_result_would_be_non_positive():
    """Host cobat no bigger than the sum of followers — the derivation can't be trusted."""
    inverters = _inverters(host_cobat=9.6, follower_cobat=9.6)
    assert derive_stack_capacities(inverters, HOST_SN) == {}


def test_derive_stack_capacities_single_inverter_no_followers():
    inverters = [{"sysSn": HOST_SN, "parallelGridMode": 1, "cobat": 9.6}]
    assert derive_stack_capacities(inverters, HOST_SN) == {HOST_SN: 9.6}


# ---------------------------------------------------------------------------
# pick_latest_stack_soc — picking the latest valid cbat point
# ---------------------------------------------------------------------------

def test_pick_latest_stack_soc_returns_value_at_las_idx():
    data = {
        "time": ["13:40", "13:45"],
        "cbat": [83, 84],
        "hasSoc": [1, 1],
        "lasIdx": 1,
    }
    sample = pick_latest_stack_soc(data)
    assert sample == StackSocSample(soc=84, time="13:45")


def test_pick_latest_stack_soc_skips_trailing_zero_not_yet_filled():
    """lasIdx points at the newest slot, which reads 0 before the server fills it in."""
    data = {
        "time": ["13:50", "13:55", "14:00"],
        "cbat": [83, 84, 0],
        "hasSoc": [1, 1, 1],
        "lasIdx": 2,
    }
    sample = pick_latest_stack_soc(data)
    assert sample == StackSocSample(soc=84, time="13:55")


def test_pick_latest_stack_soc_skips_has_soc_zero_even_if_nonzero_value():
    data = {
        "time": ["13:55", "14:00"],
        "cbat": [84, 50],
        "hasSoc": [1, 0],
        "lasIdx": 1,
    }
    sample = pick_latest_stack_soc(data)
    assert sample == StackSocSample(soc=84, time="13:55")


def test_pick_latest_stack_soc_midnight_case_no_valid_points():
    """Just after midnight, today's array may have no filled slots at all."""
    data = {
        "time": ["0:00", "0:05"],
        "cbat": [0, 0],
        "hasSoc": [0, 0],
        "lasIdx": 1,
    }
    assert pick_latest_stack_soc(data) is None


def test_pick_latest_stack_soc_empty_cbat_array():
    assert pick_latest_stack_soc({"cbat": [], "hasSoc": [], "lasIdx": 0}) is None


def test_pick_latest_stack_soc_out_of_range_las_idx_falls_back_to_last_slot():
    data = {
        "time": ["13:55", "14:00"],
        "cbat": [84, 90],
        "hasSoc": [1, 1],
        "lasIdx": 999,
    }
    sample = pick_latest_stack_soc(data)
    assert sample == StackSocSample(soc=90, time="14:00")


def test_pick_latest_stack_soc_accepts_string_has_soc_flag():
    data = {
        "time": ["13:55"],
        "cbat": ["84"],
        "hasSoc": ["1"],
        "lasIdx": 0,
    }
    assert pick_latest_stack_soc(data) == StackSocSample(soc=84.0, time="13:55")


# ---------------------------------------------------------------------------
# derive_stack_state
# ---------------------------------------------------------------------------

def test_derive_stack_state_full_when_soc_near_max():
    assert derive_stack_state(soc=100, power_w=-10) == "full"


def test_derive_stack_state_empty_when_at_min_soc():
    assert derive_stack_state(soc=10.3, power_w=50, min_soc=10) == "empty"


def test_derive_stack_state_charging_when_power_negative():
    assert derive_stack_state(soc=50, power_w=-4178) == "charging"


def test_derive_stack_state_discharging_when_power_positive():
    assert derive_stack_state(soc=50, power_w=2000) == "discharging"


def test_derive_stack_state_none_when_soc_missing():
    assert derive_stack_state(soc=None, power_w=100) is None


def test_derive_stack_state_none_when_power_missing_and_soc_mid_range():
    assert derive_stack_state(soc=50, power_w=None) is None
