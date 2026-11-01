"""Tests for the per-stack orchestration added to NeovoltClient:

- async_get_stack_soc's 5-minute poll throttle and yesterday-fallback
- reusing the Host's cached getLastPowerData for its own stack power

neovolt_client imports Home Assistant at module load — skipped cleanly
when HA isn't installed, matching test_neovolt_client.py.
"""
from __future__ import annotations

import datetime

import pytest

pytest.importorskip("Crypto.Cipher")
pytest.importorskip("aiohttp")

try:
    from custom_components.bytewatt.api import neovolt_client
except ModuleNotFoundError as exc:
    pytest.skip(f"Module not installed in this environment: {exc.name}", allow_module_level=True)

from custom_components.bytewatt.stacks import StackSocSample

STATICS_URL_FRAGMENT = "staticsByDay"


class _FakeResponse:
    def __init__(self, json_value):
        self._json_value = json_value
        self.status = 200

    async def json(self):
        return self._json_value

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _QueueSession:
    """Fake aiohttp session returning queued responses, keyed by call order.

    Each ``.get()`` call pops the next response for the matching URL from
    its queue, so a test can script "today empty -> yesterday has data"
    without the two staticsByDay dates being distinguishable any other way.
    """

    def __init__(self):
        self.responses_by_date: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params or {}))
        date = (params or {}).get("date")
        payload = self.responses_by_date.get(date, {"code": 200, "data": {}})
        return _FakeResponse(payload)


def _client(session, host_sys_sn="HOST"):
    client = object.__new__(neovolt_client.NeovoltClient)
    client.base_url = "https://example.invalid"
    client.session = session
    client.host_sys_sn = host_sys_sn
    client.user_id = "U1"
    client._stack_soc_cache = {}
    client._inverter_list_cache = None
    client._last_host_inverter_data = None
    return client


def _soc_payload(time, cbat, has_soc, las_idx):
    return {"code": 200, "data": {"time": time, "cbat": cbat, "hasSoc": has_soc, "lasIdx": las_idx}}


# ---------------------------------------------------------------------------
# 5-minute cadence for staticsByDay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stack_soc_fetches_on_first_call(monkeypatch):
    session = _QueueSession()
    session.responses_by_date["2026-11-01"] = _soc_payload(
        ["13:45"], [84], [1], 0
    )
    client = _client(session)
    monkeypatch.setattr(
        neovolt_client.dt_util, "now",
        lambda: datetime.datetime(2026, 11, 1, 13, 45),
    )

    sample = await client.async_get_stack_soc("HOST", {})

    assert sample == StackSocSample(soc=84, time="13:45")
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_stack_soc_within_5_minutes_uses_cache_not_a_new_call(monkeypatch):
    session = _QueueSession()
    session.responses_by_date["2026-11-01"] = _soc_payload(["13:45"], [84], [1], 0)
    client = _client(session)

    clock = {"now": datetime.datetime(2026, 11, 1, 13, 45)}
    monkeypatch.setattr(neovolt_client.dt_util, "now", lambda: clock["now"])

    first = await client.async_get_stack_soc("HOST", {})
    assert len(session.calls) == 1

    clock["now"] = clock["now"] + datetime.timedelta(minutes=4)
    second = await client.async_get_stack_soc("HOST", {})

    assert second == first
    assert len(session.calls) == 1, "a call inside the 5-minute window must not re-poll"


@pytest.mark.asyncio
async def test_stack_soc_after_5_minutes_polls_again(monkeypatch):
    session = _QueueSession()
    session.responses_by_date["2026-11-01"] = _soc_payload(["13:45"], [84], [1], 0)
    client = _client(session)

    clock = {"now": datetime.datetime(2026, 11, 1, 13, 45)}
    monkeypatch.setattr(neovolt_client.dt_util, "now", lambda: clock["now"])

    await client.async_get_stack_soc("HOST", {})
    assert len(session.calls) == 1

    clock["now"] = clock["now"] + datetime.timedelta(minutes=6)
    session.responses_by_date["2026-11-01"] = _soc_payload(["13:51"], [85], [1], 0)
    second = await client.async_get_stack_soc("HOST", {})

    assert second == StackSocSample(soc=85, time="13:51")
    assert len(session.calls) == 2, "past the 5-minute window, staticsByDay must be re-polled"


@pytest.mark.asyncio
async def test_stack_soc_caches_independently_per_sys_sn(monkeypatch):
    session = _QueueSession()
    session.responses_by_date["2026-11-01"] = _soc_payload(["13:45"], [84], [1], 0)
    client = _client(session)
    monkeypatch.setattr(
        neovolt_client.dt_util, "now",
        lambda: datetime.datetime(2026, 11, 1, 13, 45),
    )

    await client.async_get_stack_soc("HOST", {})
    await client.async_get_stack_soc("FOLLOWER", {})

    assert len(session.calls) == 2
    assert {call[1]["sysSn"] for call in session.calls} == {"HOST", "FOLLOWER"}


# ---------------------------------------------------------------------------
# Midnight fallback: today empty -> retry against yesterday
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stack_soc_falls_back_to_yesterday_when_today_has_no_valid_points(monkeypatch):
    session = _QueueSession()
    # Today (just after midnight): no filled slots yet.
    session.responses_by_date["2026-11-01"] = _soc_payload(["0:00", "0:05"], [0, 0], [0, 0], 1)
    # Yesterday's last valid point.
    session.responses_by_date["2026-10-31"] = _soc_payload(["23:55"], [96], [1], 0)
    client = _client(session)

    monkeypatch.setattr(
        neovolt_client.dt_util, "now",
        lambda: datetime.datetime(2026, 11, 1, 0, 6),
    )

    sample = await client.async_get_stack_soc("HOST", {})

    assert sample == StackSocSample(soc=96, time="23:55")
    assert [call[1]["date"] for call in session.calls] == ["2026-11-01", "2026-10-31"]


@pytest.mark.asyncio
async def test_stack_soc_returns_none_and_is_not_cached_when_both_days_empty(monkeypatch):
    session = _QueueSession()
    session.responses_by_date["2026-11-01"] = _soc_payload(["0:00"], [0], [0], 0)
    session.responses_by_date["2026-10-31"] = _soc_payload(["23:55"], [0], [0], 0)
    client = _client(session)
    monkeypatch.setattr(
        neovolt_client.dt_util, "now",
        lambda: datetime.datetime(2026, 11, 1, 0, 6),
    )

    sample = await client.async_get_stack_soc("HOST", {})

    assert sample is None
    assert client._stack_soc_cache == {}


@pytest.mark.asyncio
async def test_stack_soc_http_failure_returns_none_without_raising(monkeypatch):
    class _FailingSession:
        def get(self, url, params=None, headers=None):
            class _Resp:
                status = 500

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *exc):
                    return False

            return _Resp()

    client = _client(_FailingSession())
    monkeypatch.setattr(
        neovolt_client.dt_util, "now",
        lambda: datetime.datetime(2026, 11, 1, 13, 45),
    )

    assert await client.async_get_stack_soc("HOST", {}) is None
