"""Tests for low-level neovolt_client helpers and the encryption fail-loud contract.

Load the relevant modules directly via importlib so the test suite doesn't
need the full integration package to be importable (which would pull in
voluptuous + homeassistant).
"""
from __future__ import annotations

import importlib.util
import os

import pytest

# neovolt_auth needs pycryptodome at module load; neovolt_client also imports it.
pytest.importorskip("Crypto.Cipher")
pytest.importorskip("aiohttp")


def _load_module(rel_path: str, name: str):
    here = os.path.dirname(__file__)
    path = os.path.abspath(os.path.join(here, "..", "custom_components", "bytewatt", rel_path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# neovolt_client imports homeassistant.helpers.aiohttp_client at module load —
# skip cleanly when HA isn't installed (bare sandbox).
try:
    neovolt_auth = _load_module("api/neovolt_auth.py", "bytewatt_neovolt_auth")
    neovolt_client = _load_module("api/neovolt_client.py", "bytewatt_neovolt_client")
except ModuleNotFoundError as exc:
    pytest.skip(f"Module not installed in this environment: {exc.name}", allow_module_level=True)

EncryptionError = neovolt_auth.EncryptionError
encrypt_password = neovolt_auth.encrypt_password
ByteWattAPIError = neovolt_client.ByteWattAPIError
_stat_value = neovolt_client._stat_value
_decode_json_object = neovolt_client._decode_json_object


def test_stat_value_returns_value_when_present():
    assert _stat_value({"epvtoday": 12.5}, "epvtoday") == 12.5
    assert _stat_value({"epvtoday": 0}, "epvtoday") == 0


def test_stat_value_coalesces_missing_key_to_zero():
    assert _stat_value({}, "epvtoday") == 0


def test_stat_value_coalesces_explicit_none_to_zero():
    """The fragile arithmetic path used to crash on None — never again."""
    assert _stat_value({"epvtoday": None}, "epvtoday") == 0


def test_battery_discharged_today_calculation_survives_partial_data():
    """The discharge calc used to raise TypeError when any input was None.
    With _stat_value, the calc must complete with sensible zeros."""
    stats_data = {
        "epvtoday": 10,
        "ehomeload": None,   # Missing field
        # efeedIn missing entirely
        "einput": 5,
        "echarge": 2,
    }
    pv_today    = _stat_value(stats_data, "epvtoday")
    consumed    = _stat_value(stats_data, "ehomeload")
    feed_in     = _stat_value(stats_data, "efeedIn")
    grid_import = _stat_value(stats_data, "einput")
    charged     = _stat_value(stats_data, "echarge")
    # Should not raise.
    total_gained = pv_today + grid_import
    total_used   = consumed + feed_in + charged
    discharged = total_used - total_gained
    assert discharged == 2 - 15  # 0+0+2 - (10+5)


def test_encryption_known_vector():
    """Anchor a known cipher output so we'd catch any regression in the
    encryption algorithm (key derivation, IV, padding, base64)."""
    assert encrypt_password("1", "caraa") == "CH1iL1FqYK9bhTd9izZyMA=="
    assert encrypt_password("1", "carraa") == "oFzzKemj3O4WP92FBSjZzw=="


def test_encryption_error_is_runtime_error_subclass():
    """Callers can catch RuntimeError generically and still get EncryptionError."""
    assert issubclass(EncryptionError, RuntimeError)


def test_bytewatt_api_error_is_exception_subclass():
    """The coordinator catches Exception broadly — ByteWattAPIError must match."""
    assert issubclass(ByteWattAPIError, Exception)


# ---------------------------------------------------------------------------
# _decode_json_object — must reject non-object JSON before .get() crashes
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal stand-in for aiohttp.ClientResponse."""

    def __init__(self, json_value=None, raise_exc=None):
        self._json_value = json_value
        self._raise_exc = raise_exc

    async def json(self):
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._json_value


@pytest.mark.asyncio
async def test_decode_returns_dict_for_object():
    result = await _decode_json_object(_FakeResponse({"code": 200}), "ctx")
    assert result == {"code": 200}


@pytest.mark.asyncio
async def test_decode_returns_none_for_array():
    """Body is valid JSON but a list — `.get('code')` would crash later."""
    result = await _decode_json_object(_FakeResponse(["error", "details"]), "ctx")
    assert result is None


@pytest.mark.asyncio
async def test_decode_returns_none_for_string():
    """Body is valid JSON but a bare string."""
    result = await _decode_json_object(_FakeResponse("just an error message"), "ctx")
    assert result is None


@pytest.mark.asyncio
async def test_decode_returns_none_for_null():
    result = await _decode_json_object(_FakeResponse(None), "ctx")
    assert result is None


@pytest.mark.asyncio
async def test_decode_returns_none_on_value_error():
    """ValueError covers json.JSONDecodeError for malformed bodies."""
    result = await _decode_json_object(_FakeResponse(raise_exc=ValueError("bad json")), "ctx")
    assert result is None
