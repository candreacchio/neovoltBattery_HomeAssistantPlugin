"""Per-stack (per-inverter) battery helpers for parallel Neovolt systems.

On a parallel install, each inverter can only charge/discharge the battery
stack physically wired to it — the Host's stack and the Follower's stack
are independent, even though the portal (and the bank SOC sensor) reports
them blended together. These helpers turn the raw API responses into
per-stack SOC and capacity so automations can see each stack's own state.

Role is reported per-inverter by ``getCustomMenuEssList`` as
``parallelGridMode``: 1 = Host, 2 = Follower. Capacity (``cobat``) is
correct for a Follower but double-counts the whole bank for the Host, so
the Host's own stack capacity has to be backed out: Host stack kWh =
Host cobat - sum(Follower cobat).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PARALLEL_GRID_MODE_HOST = 1
PARALLEL_GRID_MODE_FOLLOWER = 2

ROLE_HOST = "host"
ROLE_FOLLOWER = "follower"


def _truthy_flag(value: Any) -> bool:
    """Treat 1 / "1" / True as a valid-data flag; everything else is not."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip() == "1"
    return False


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def detect_roles(inverters: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map sysSn -> "host"/"follower" using each inverter's parallelGridMode.

    Inverters with an unrecognised or missing parallelGridMode are omitted
    — callers should treat a sysSn absent from the result as unknown
    rather than guessing a role.
    """
    roles: Dict[str, str] = {}
    for inv in inverters:
        sys_sn = inv.get("sysSn")
        if not sys_sn:
            continue
        mode = inv.get("parallelGridMode")
        if mode == PARALLEL_GRID_MODE_HOST:
            roles[sys_sn] = ROLE_HOST
        elif mode == PARALLEL_GRID_MODE_FOLLOWER:
            roles[sys_sn] = ROLE_FOLLOWER
    return roles


def derive_stack_capacities(
    inverters: List[Dict[str, Any]], host_sys_sn: str
) -> Dict[str, float]:
    """Return sysSn -> this inverter's own stack capacity in kWh.

    A Follower's ``cobat`` is already its own stack capacity. The Host's
    ``cobat`` double-counts the whole parallel bank, so its real stack
    capacity is backed out as (Host cobat - sum of Follower cobat).
    Returns an empty dict if the Host's cobat can't be read — a caller
    should treat that as "capacities unknown" rather than deriving a
    negative or zero value.
    """
    host_cobat: Optional[float] = None
    follower_cobats: Dict[str, float] = {}

    for inv in inverters:
        sys_sn = inv.get("sysSn")
        if not sys_sn:
            continue
        cobat = _as_float(inv.get("cobat"))
        if cobat is None:
            continue
        if sys_sn == host_sys_sn:
            host_cobat = cobat
        elif inv.get("parallelGridMode") == PARALLEL_GRID_MODE_FOLLOWER:
            follower_cobats[sys_sn] = cobat

    if host_cobat is None:
        return {}

    host_stack_kwh = host_cobat - sum(follower_cobats.values())
    if host_stack_kwh <= 0:
        return {}

    capacities = {host_sys_sn: host_stack_kwh}
    capacities.update(follower_cobats)
    return capacities


def follower_sys_sns(inverters: List[Dict[str, Any]], host_sys_sn: str) -> List[str]:
    """List every Follower sysSn (any count), excluding the Host."""
    return [
        inv.get("sysSn")
        for inv in inverters
        if inv.get("sysSn")
        and inv.get("sysSn") != host_sys_sn
        and inv.get("parallelGridMode") == PARALLEL_GRID_MODE_FOLLOWER
    ]


@dataclass
class StackSocSample:
    """One picked SOC reading for a single stack."""

    soc: float
    time: str


def pick_latest_stack_soc(data: Dict[str, Any]) -> Optional[StackSocSample]:
    """Pick the latest valid per-stack SOC out of one staticsByDay response.

    ``data`` is the raw ``data`` object of a staticsByDay response: parallel
    arrays ``time``/``cbat``/``hasSoc`` plus ``lasIdx`` (index of the newest
    slot). The newest slot can read 0 before the server has filled it in
    (hasSoc may still say 1), so this walks backward from lasIdx and skips
    any slot that is flagged invalid OR reads exactly 0 — a real SOC of
    0% doesn't happen in practice, so an exact 0 is always "not filled yet"
    rather than a genuine reading.

    Returns None if no valid point exists in this response at all — e.g.
    just after midnight, before today's array has any filled slots. The
    caller is expected to retry against the previous day's data.
    """
    cbat = data.get("cbat") or []
    has_soc = data.get("hasSoc") or []
    times = data.get("time") or []
    if not cbat:
        return None

    las_idx = data.get("lasIdx")
    if not isinstance(las_idx, int) or not (0 <= las_idx < len(cbat)):
        las_idx = len(cbat) - 1

    for idx in range(las_idx, -1, -1):
        value = _as_float(cbat[idx])
        if value is None or value <= 0:
            continue
        flag = has_soc[idx] if idx < len(has_soc) else 1
        if not _truthy_flag(flag):
            continue
        sample_time = times[idx] if idx < len(times) else ""
        return StackSocSample(soc=value, time=sample_time)

    return None


STATE_FULL = "full"
STATE_CHARGING = "charging"
STATE_DISCHARGING = "discharging"
STATE_EMPTY = "empty"

# How close to 100%/min-SOC counts as "full"/"empty" rather than merely
# charging/discharging near the limit — matches the ≤ min_soc + 0.5 rule
# used to detect the single stack running out before the bank average does.
EMPTY_SOC_MARGIN = 0.5
FULL_SOC_THRESHOLD = 99.5
POWER_HYSTERESIS_W = 50


def derive_stack_state(
    soc: Optional[float],
    power_w: Optional[float],
    min_soc: float = 0.0,
) -> Optional[str]:
    """Derive a simple full/charging/discharging/empty state for one stack.

    Negative power = charging (matches prealL1's sign convention). SOC
    extremes take priority over power so a stack sitting at the limit
    with near-zero power still reads full/empty rather than idle.
    """
    if soc is None:
        return None
    if soc <= min_soc + EMPTY_SOC_MARGIN:
        return STATE_EMPTY
    if soc >= FULL_SOC_THRESHOLD:
        return STATE_FULL
    if power_w is None:
        return None
    if power_w <= -POWER_HYSTERESIS_W:
        return STATE_CHARGING
    if power_w >= POWER_HYSTERESIS_W:
        return STATE_DISCHARGING
    return None
