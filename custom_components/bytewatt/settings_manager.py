"""Single source of truth for battery + grid feed-in settings.

Owns the server cache, the pending diff, and serializes refresh/submit
behind a lock. Entities call ``effective_*()`` to read, ``stage_*()`` to
write (with validation). The Submit button calls ``submit()`` to push
everything to the API in one shot; on per-batch failure the failed
batch's pending changes are preserved so the UI does not lie to the user.

Concurrency model
-----------------
- ``stage_*`` / ``discard`` are sync and lock-free. They mutate the
  pending dicts directly. Safe in asyncio's single-threaded model so
  long as no awaits sit between read and write inside any one of them.
- ``refresh`` / ``submit`` take an ``asyncio.Lock`` to serialize against
  each other across await points.
- ``submit`` uses a snapshot-clear-restore pattern: it atomically
  (no awaits in between) moves pending into a local snapshot and
  resets pending to empty BEFORE the API call. Any ``stage_*`` that
  fires while the submit is in flight lands in the fresh pending and
  survives the submit. On per-batch failure, the snapshot is merged
  back into pending (without overwriting any newer values the user
  staged during submit).
- ``_battery_submitted_at`` / ``_feedin_submitted_at`` carry a short
  "trust local cache" window after a successful submit. Subsequent
  refreshes skip the corresponding batch for that window, since the
  Byte-Watt API is not strictly read-after-write consistent — without
  this guard the UI can flick back to stale values for one poll cycle.
"""
from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .api.settings import BatterySettingsAPI, GridFeedInSettingsAPI
from .const import signal_pending_changed
from .models import CycleStrategy, GridFeedInSettings, GridFeedInSlot
from .utilities.time_utils import sanitize_time_format

_LOGGER = logging.getLogger(__name__)


class SettingsValidationError(ValueError):
    """Raised when a staged value fails validation."""


@dataclass
class SubmitResult:
    """Per-batch outcome of a submit() call."""
    battery_attempted: bool = False
    battery_ok: bool = False
    battery_error: Optional[str] = None
    feedin_attempted: bool = False
    feedin_ok: bool = False
    feedin_error: Optional[str] = None

    @property
    def all_ok(self) -> bool:
        if not (self.battery_attempted or self.feedin_attempted):
            return True
        if self.battery_attempted and not self.battery_ok:
            return False
        if self.feedin_attempted and not self.feedin_ok:
            return False
        return True

    @property
    def any_attempted(self) -> bool:
        return self.battery_attempted or self.feedin_attempted


# -- Validators ------------------------------------------------------------

def _v_soc(name: str, value: Any) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError) as ex:
        raise SettingsValidationError(f"{name} must be an integer, got {value!r}") from ex
    if not 1 <= iv <= 100:
        raise SettingsValidationError(f"{name} must be 1..100, got {iv}")
    return iv


def _v_time(name: str, value: Any) -> str:
    sanitized = sanitize_time_format(value)
    if sanitized is None:
        raise SettingsValidationError(f"{name} must be HH:MM, got {value!r}")
    return sanitized


def _v_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "1", "on", "yes"):
            return True
        if lower in ("false", "0", "off", "no"):
            return False
    raise SettingsValidationError(f"{name} must be boolean-like, got {value!r}")


def _v_battery_power(name: str, value: Any) -> int:
    """Charge/discharge power: realistic inverter range."""
    try:
        iv = int(value)
    except (TypeError, ValueError) as ex:
        raise SettingsValidationError(f"{name} must be an integer, got {value!r}") from ex
    if not 0 <= iv <= 50000:
        raise SettingsValidationError(f"{name} must be 0..50000 W, got {iv}")
    return iv


def _v_feedin_power(name: str, value: Any) -> int:
    """Grid feed-in power: hardware top end ~20 kW."""
    try:
        iv = int(value)
    except (TypeError, ValueError) as ex:
        raise SettingsValidationError(f"{name} must be an integer, got {value!r}") from ex
    if not 0 <= iv <= 20000:
        raise SettingsValidationError(f"{name} must be 0..20000 W, got {iv}")
    return iv


def _v_cutoff_soc(name: str, value: Any) -> float:
    try:
        fv = float(value)
    except (TypeError, ValueError) as ex:
        raise SettingsValidationError(f"{name} must be a number, got {value!r}") from ex
    if not 0 <= fv <= 100:
        raise SettingsValidationError(f"{name} must be 0..100, got {fv}")
    return fv


BATTERY_VALIDATORS = {
    "minimum_soc":            _v_soc,
    "charge_cap":             _v_soc,
    "charge_start_time":      _v_time,
    "charge_end_time":        _v_time,
    "discharge_start_time":   _v_time,
    "discharge_end_time":     _v_time,
    "grid_charging":          _v_bool,
    "discharge_time_control": _v_bool,
    "charge_power":           _v_battery_power,
    "discharge_power":        _v_battery_power,
}

FEEDIN_VALIDATORS = {
    "enabled":    _v_bool,
    "cutoff_soc": _v_cutoff_soc,
}

FEEDIN_SLOT_VALIDATORS = {
    "start": _v_time,
    "end":   _v_time,
    "power": _v_feedin_power,
}


class SettingsManager:
    """Owns cache + pending diff + submit lifecycle for one config entry."""

    # Submit operation timeout — protects against an unresponsive API
    # holding the lock and blocking future refreshes/submits indefinitely.
    SUBMIT_TIMEOUT_SECONDS = 60

    # After a successful submit, skip fetching that batch on the next
    # refresh(es) for this long. The Byte-Watt API isn't read-after-write
    # consistent — without this window the UI can flick back to the
    # pre-submit value for one poll cycle.
    POST_SUBMIT_TRUST_SECONDS = 30

    def __init__(self, hass: HomeAssistant, client, entry_id: str) -> None:
        self._hass = hass
        self._client = client  # NeovoltClient
        self._entry_id = entry_id
        self._lock = asyncio.Lock()

        # Server cache
        self._battery_cache: Optional[CycleStrategy] = None
        self._feedin_cache: Optional[GridFeedInSettings] = None

        # Pending diff (cleared per-batch on successful submit)
        self._pending_battery: Dict[str, Any] = {}
        self._pending_feedin: Dict[str, Any] = {}
        self._pending_feedin_slots: Dict[int, Dict[str, Any]] = {}

        # Per-batch post-submit "trust local cache" timestamps
        self._battery_submitted_at: Optional[datetime] = None
        self._feedin_submitted_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Pending-change dispatcher signal
    # ------------------------------------------------------------------

    def _notify_pending_changed(self) -> None:
        """Tell Submit/Discard buttons (and anyone else listening)
        that the pending dict shape just changed."""
        async_dispatcher_send(self._hass, signal_pending_changed(self._entry_id))

    # ------------------------------------------------------------------
    # Read — sync, lock-free
    # ------------------------------------------------------------------

    @property
    def battery_cache(self) -> Optional[CycleStrategy]:
        return self._battery_cache

    @property
    def feedin_cache(self) -> Optional[GridFeedInSettings]:
        return self._feedin_cache

    def has_pending(self) -> bool:
        return bool(
            self._pending_battery or self._pending_feedin or self._pending_feedin_slots
        )

    def pending_count(self) -> int:
        return (
            len(self._pending_battery)
            + len(self._pending_feedin)
            + sum(len(s) for s in self._pending_feedin_slots.values())
        )

    def effective_battery(self, field: str, default: Any = None) -> Any:
        if field in self._pending_battery:
            return self._pending_battery[field]
        return self._read_battery_from_cache(field, default)

    def effective_feedin(self, field: str, default: Any = None) -> Any:
        if field in self._pending_feedin:
            return self._pending_feedin[field]
        if self._feedin_cache is None:
            return default
        if field == "enabled":
            return bool(self._feedin_cache.battery_en)
        if field == "cutoff_soc":
            return float(self._feedin_cache.battery_feed_cutoff_soc)
        return default

    def effective_feedin_slot(
        self, slot_index: int, field: str, default: Any = None
    ) -> Any:
        slot_pending = self._pending_feedin_slots.get(slot_index, {})
        if field in slot_pending:
            return slot_pending[field]
        if self._feedin_cache is None or slot_index >= len(self._feedin_cache.slots):
            return default
        slot = self._feedin_cache.slots[slot_index]
        if field == "start":
            return slot.start
        if field == "end":
            return slot.end
        if field == "power":
            return slot.feed_power
        return default

    def feedin_slot_available(self, slot_index: int) -> bool:
        if slot_index in self._pending_feedin_slots:
            return True
        return (
            self._feedin_cache is not None
            and slot_index < len(self._feedin_cache.slots)
        )

    def _read_battery_from_cache(self, field: str, default: Any) -> Any:
        c = self._battery_cache
        if c is None:
            return default
        if field == "minimum_soc":
            return c.bat_use_cap
        if field == "charge_cap":
            return c.charge_slots[0].charge_limit if c.charge_slots else default
        if field == "charge_start_time":
            return c.charge_slots[0].begin_time if c.charge_slots else default
        if field == "charge_end_time":
            return c.charge_slots[0].end_time if c.charge_slots else default
        if field == "discharge_start_time":
            return c.discharge_slots[0].begin_time if c.discharge_slots else default
        if field == "discharge_end_time":
            return c.discharge_slots[0].end_time if c.discharge_slots else default
        if field == "grid_charging":
            return bool(c.grid_charge_cycle)
        if field == "discharge_time_control":
            return bool(c.ctr_dis_cycle)
        if field == "charge_power":
            return c.charge_slots[0].charge_power if c.charge_slots else default
        if field == "discharge_power":
            return c.discharge_slots[0].charge_power if c.discharge_slots else default
        return default

    # ------------------------------------------------------------------
    # Stage — validates and stores; no API call; lock-free; safe to call
    # any time including during a submit-in-flight (see class docstring)
    # ------------------------------------------------------------------

    def stage_battery(self, field: str, value: Any) -> None:
        if field not in BATTERY_VALIDATORS:
            raise SettingsValidationError(f"Unknown battery field: {field}")
        validated = BATTERY_VALIDATORS[field](field, value)
        self._pending_battery[field] = validated
        _LOGGER.debug("Staged battery.%s = %r", field, validated)
        self._notify_pending_changed()

    def stage_feedin(self, field: str, value: Any) -> None:
        if field not in FEEDIN_VALIDATORS:
            raise SettingsValidationError(f"Unknown feed-in field: {field}")
        validated = FEEDIN_VALIDATORS[field](field, value)
        self._pending_feedin[field] = validated
        _LOGGER.debug("Staged feedin.%s = %r", field, validated)
        self._notify_pending_changed()

    def stage_feedin_slot(self, slot_index: int, field: str, value: Any) -> None:
        if field not in FEEDIN_SLOT_VALIDATORS:
            raise SettingsValidationError(f"Unknown feed-in slot field: {field}")
        validated = FEEDIN_SLOT_VALIDATORS[field](field, value)
        self._pending_feedin_slots.setdefault(slot_index, {})[field] = validated
        _LOGGER.debug("Staged feedin.slots[%d].%s = %r", slot_index, field, validated)
        self._notify_pending_changed()

    def discard(self) -> int:
        """Drop all pending changes. Returns the count discarded.

        If a submit is in flight, only changes NOT already snapshotted
        for that submit are dropped — the in-flight API call cannot be
        recalled. New changes staged after a discard land normally.
        """
        count = self.pending_count()
        self._pending_battery.clear()
        self._pending_feedin.clear()
        self._pending_feedin_slots.clear()
        self._notify_pending_changed()
        return count

    # ------------------------------------------------------------------
    # Refresh — pulls latest server state into cache, never touches pending
    # ------------------------------------------------------------------

    async def refresh(self) -> None:
        async with self._lock:
            await self._refresh_locked()

    async def _refresh_locked(self) -> None:
        now = dt_util.utcnow()

        if self._battery_submitted_at and (
            now - self._battery_submitted_at < timedelta(seconds=self.POST_SUBMIT_TRUST_SECONDS)
        ):
            _LOGGER.debug(
                "Skipping battery refresh — trusting local cache for %.0fs after submit",
                self.POST_SUBMIT_TRUST_SECONDS,
            )
        else:
            try:
                battery = await BatterySettingsAPI(self._client).fetch_current_settings()
                if battery is not None:
                    self._battery_cache = battery
            except Exception as ex:  # noqa: BLE001 — surface in logs, never crash poll
                _LOGGER.warning("Battery settings refresh failed: %s", ex)

        if self._feedin_submitted_at and (
            now - self._feedin_submitted_at < timedelta(seconds=self.POST_SUBMIT_TRUST_SECONDS)
        ):
            _LOGGER.debug(
                "Skipping feed-in refresh — trusting local cache for %.0fs after submit",
                self.POST_SUBMIT_TRUST_SECONDS,
            )
        else:
            try:
                feedin = await GridFeedInSettingsAPI(self._client).fetch_current_settings()
                if feedin is not None:
                    self._feedin_cache = feedin
            except Exception as ex:  # noqa: BLE001
                _LOGGER.warning("Grid feed-in settings refresh failed: %s", ex)

    # ------------------------------------------------------------------
    # Submit — single transactional push; per-batch atomicity
    # ------------------------------------------------------------------

    async def submit_battery_one_shot(self, fields: Dict[str, Any]) -> SubmitResult:
        """Validate, build a payload, and PUT — without touching pending.

        Service handlers use this so a service call doesn't accidentally
        commit the user's UI-staged drafts. fields is a dict of logical
        battery field names to values (same keys as stage_battery).
        """
        result = SubmitResult()
        snapshot: Dict[str, Any] = {}
        try:
            for field, value in fields.items():
                if value is None:
                    continue
                if field not in BATTERY_VALIDATORS:
                    raise SettingsValidationError(f"Unknown battery field: {field}")
                snapshot[field] = BATTERY_VALIDATORS[field](field, value)
        except SettingsValidationError as ex:
            result.battery_attempted = True
            result.battery_error = str(ex)
            return result

        if not snapshot:
            return result

        async with self._lock:
            await self._submit_battery(snapshot, result)
            # _submit_battery updates _battery_cache on success — UI entities
            # will read the new value via effective_battery.
            self._notify_pending_changed()
        return result

    async def submit_feedin_one_shot(
        self,
        top: Dict[str, Any] | None = None,
        slots: Dict[int, Dict[str, Any]] | None = None,
    ) -> SubmitResult:
        """Validate + POST grid feed-in without touching pending."""
        result = SubmitResult()
        top_snapshot: Dict[str, Any] = {}
        slots_snapshot: Dict[int, Dict[str, Any]] = {}
        try:
            for field, value in (top or {}).items():
                if value is None:
                    continue
                if field not in FEEDIN_VALIDATORS:
                    raise SettingsValidationError(f"Unknown feed-in field: {field}")
                top_snapshot[field] = FEEDIN_VALIDATORS[field](field, value)
            for slot_idx, slot_fields in (slots or {}).items():
                slot_clean: Dict[str, Any] = {}
                for field, value in slot_fields.items():
                    if value is None:
                        continue
                    if field not in FEEDIN_SLOT_VALIDATORS:
                        raise SettingsValidationError(f"Unknown feed-in slot field: {field}")
                    slot_clean[field] = FEEDIN_SLOT_VALIDATORS[field](field, value)
                if slot_clean:
                    slots_snapshot[slot_idx] = slot_clean
        except SettingsValidationError as ex:
            result.feedin_attempted = True
            result.feedin_error = str(ex)
            return result

        if not (top_snapshot or slots_snapshot):
            return result

        async with self._lock:
            await self._submit_feedin(top_snapshot, slots_snapshot, result)
            self._notify_pending_changed()
        return result

    async def submit(self) -> SubmitResult:
        """Push pending changes to the API.

        Snapshots pending into locals, hands them to `_submit_locked`,
        and unconditionally restores any unsubmitted ones on the way out
        (timeout, cancellation, unexpected exception) so the user never
        loses staged values.
        """
        result = SubmitResult()
        # Snapshot OUTSIDE the lock so the timeout/exception handler can
        # see them and restore on its way out.
        snapshot_battery = self._pending_battery
        snapshot_feedin = self._pending_feedin
        snapshot_feedin_slots = self._pending_feedin_slots
        self._pending_battery = {}
        self._pending_feedin = {}
        self._pending_feedin_slots = {}
        self._notify_pending_changed()

        try:
            async with asyncio.timeout(self.SUBMIT_TIMEOUT_SECONDS):
                async with self._lock:
                    await self._submit_battery(snapshot_battery, result)
                    await self._submit_feedin(
                        snapshot_feedin, snapshot_feedin_slots, result
                    )
        except asyncio.TimeoutError:
            _LOGGER.error("Submit timed out after %ds", self.SUBMIT_TIMEOUT_SECONDS)
            if snapshot_battery and not result.battery_ok:
                result.battery_attempted = True
                result.battery_error = result.battery_error or "submit timed out"
            if (snapshot_feedin or snapshot_feedin_slots) and not result.feedin_ok:
                result.feedin_attempted = True
                result.feedin_error = result.feedin_error or "submit timed out"
        except asyncio.CancelledError:
            # HA is shutting down, or the task was cancelled — preserve pending
            # and re-raise so the cancellation propagates correctly.
            self._restore_battery_pending(snapshot_battery)
            self._restore_feedin_pending(snapshot_feedin, snapshot_feedin_slots)
            self._notify_pending_changed()
            raise
        except Exception as ex:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during submit: %s", ex)
            if snapshot_battery and not result.battery_ok:
                result.battery_attempted = True
                result.battery_error = result.battery_error or f"unexpected: {ex}"
            if (snapshot_feedin or snapshot_feedin_slots) and not result.feedin_ok:
                result.feedin_attempted = True
                result.feedin_error = result.feedin_error or f"unexpected: {ex}"

        # Restore anything that didn't make it to the inverter. On full
        # success this is a no-op (the per-batch _submit_* paths cleared
        # their locals via the "ok" branch). On partial / total failure,
        # the snapshot is merged back via setdefault so any newer stage_*
        # made during submit wins on conflict.
        if not result.battery_ok and snapshot_battery:
            self._restore_battery_pending(snapshot_battery)
        if not result.feedin_ok and (snapshot_feedin or snapshot_feedin_slots):
            self._restore_feedin_pending(snapshot_feedin, snapshot_feedin_slots)
        self._notify_pending_changed()
        return result

    # Submit retry policy.
    #
    # The manager owns the retry loop and does a full re-fetch + rebuild +
    # single write on EACH attempt. This is deliberate: the failure mode we
    # care about (a stale raw_data field such as poinv getting the PUT
    # rejected) is deterministic — re-sending identical bytes, as a
    # transport-level retry does, gets the identical rejection. Rebuilding
    # against freshly-fetched server state on each attempt is what actually
    # lets the submit self-heal. Transient failures (9007, rate-limit, a
    # blip) are also covered by the same loop + backoff.
    #
    # The transport calls are therefore made single-attempt (max_retries=1,
    # which still performs the 6069 re-login) so retries don't stack into
    # this loop and compound the time spent under the submit lock + timeout.
    SUBMIT_RETRIES = 3
    SUBMIT_RETRY_DELAY = 4.0  # seconds between attempts
    _SINGLE_ATTEMPT = 1

    async def _submit_battery(
        self, snapshot: Dict[str, Any], result: SubmitResult
    ) -> None:
        if not snapshot:
            return
        result.battery_attempted = True
        api = BatterySettingsAPI(self._client)

        for attempt in range(1, self.SUBMIT_RETRIES + 1):
            # Re-fetch + rebuild on every attempt so a stale-data rejection
            # can self-heal rather than re-sending the same rejected payload.
            fresh = await api.fetch_current_settings(max_retries=self._SINGLE_ATTEMPT)
            if fresh is not None:
                self._battery_cache = fresh
            elif self._battery_cache is None:
                result.battery_error = "could not fetch current battery settings"
                _LOGGER.warning(
                    "Battery submit attempt %d/%d: no settings to build against (entry=%s)",
                    attempt, self.SUBMIT_RETRIES, self._entry_id,
                )
                if attempt < self.SUBMIT_RETRIES:
                    await asyncio.sleep(self.SUBMIT_RETRY_DELAY)
                continue

            try:
                merged = self._build_battery_payload(snapshot)
            except SettingsValidationError as ex:
                # Deterministic build error (e.g. no slot defined) — retrying
                # can't help, so bail immediately.
                _LOGGER.error("Cannot build battery payload: %s", ex)
                result.battery_error = str(ex)
                return

            if await api.put(merged, max_retries=self._SINGLE_ATTEMPT):
                self._battery_cache = merged
                self._battery_submitted_at = dt_util.utcnow()
                result.battery_ok = True
                _LOGGER.info(
                    "Battery settings submitted (entry=%s, host=%s, attempt=%d/%d)",
                    self._entry_id,
                    getattr(self._client, "host_system_id", "") or "default",
                    attempt, self.SUBMIT_RETRIES,
                )
                return

            result.battery_error = f"API call failed on attempt {attempt}/{self.SUBMIT_RETRIES}"
            _LOGGER.warning(
                "Battery submit attempt %d/%d failed (entry=%s)%s",
                attempt, self.SUBMIT_RETRIES, self._entry_id,
                f"; retrying in {self.SUBMIT_RETRY_DELAY:.0f}s"
                if attempt < self.SUBMIT_RETRIES else "; no more retries",
            )
            if attempt < self.SUBMIT_RETRIES:
                await asyncio.sleep(self.SUBMIT_RETRY_DELAY)

        _LOGGER.error(
            "Battery submit failed after %d attempt(s); pending changes preserved",
            self.SUBMIT_RETRIES,
        )

    async def _submit_feedin(
        self,
        snapshot_top: Dict[str, Any],
        snapshot_slots: Dict[int, Dict[str, Any]],
        result: SubmitResult,
    ) -> None:
        if not (snapshot_top or snapshot_slots):
            return
        result.feedin_attempted = True
        api = GridFeedInSettingsAPI(self._client)

        for attempt in range(1, self.SUBMIT_RETRIES + 1):
            # Re-fetch + rebuild on every attempt (see _submit_battery).
            fresh = await api.fetch_current_settings(max_retries=self._SINGLE_ATTEMPT)
            if fresh is not None:
                self._feedin_cache = fresh
            elif self._feedin_cache is None:
                result.feedin_error = "could not fetch current feed-in settings"
                _LOGGER.warning(
                    "Feed-in submit attempt %d/%d: no settings to build against (entry=%s)",
                    attempt, self.SUBMIT_RETRIES, self._entry_id,
                )
                if attempt < self.SUBMIT_RETRIES:
                    await asyncio.sleep(self.SUBMIT_RETRY_DELAY)
                continue

            try:
                merged = self._build_feedin_payload(snapshot_top, snapshot_slots)
            except SettingsValidationError as ex:
                _LOGGER.error("Cannot build feed-in payload: %s", ex)
                result.feedin_error = str(ex)
                return

            if await api.post(merged, max_retries=self._SINGLE_ATTEMPT):
                self._feedin_cache = merged
                self._feedin_submitted_at = dt_util.utcnow()
                result.feedin_ok = True
                _LOGGER.info(
                    "Grid feed-in settings submitted (entry=%s, host=%s, attempt=%d/%d)",
                    self._entry_id,
                    getattr(self._client, "host_system_id", "") or "default",
                    attempt, self.SUBMIT_RETRIES,
                )
                return

            result.feedin_error = f"API call failed on attempt {attempt}/{self.SUBMIT_RETRIES}"
            _LOGGER.warning(
                "Feed-in submit attempt %d/%d failed (entry=%s)%s",
                attempt, self.SUBMIT_RETRIES, self._entry_id,
                f"; retrying in {self.SUBMIT_RETRY_DELAY:.0f}s"
                if attempt < self.SUBMIT_RETRIES else "; no more retries",
            )
            if attempt < self.SUBMIT_RETRIES:
                await asyncio.sleep(self.SUBMIT_RETRY_DELAY)

        _LOGGER.error(
            "Feed-in submit failed after %d attempt(s); pending changes preserved",
            self.SUBMIT_RETRIES,
        )

    # Restore helpers — `setdefault` ensures fresh stage_* calls made during
    # the submit win over the restored snapshot value on conflict (later
    # edit always beats earlier).
    def _restore_battery_pending(self, snapshot: Dict[str, Any]) -> None:
        for k, v in snapshot.items():
            self._pending_battery.setdefault(k, v)

    def _restore_feedin_pending(
        self,
        snapshot_top: Dict[str, Any],
        snapshot_slots: Dict[int, Dict[str, Any]],
    ) -> None:
        for k, v in snapshot_top.items():
            self._pending_feedin.setdefault(k, v)
        for slot_index, slot_kwargs in snapshot_slots.items():
            target = self._pending_feedin_slots.setdefault(slot_index, {})
            for k, v in slot_kwargs.items():
                target.setdefault(k, v)

    # ------------------------------------------------------------------
    # Payload builders — clone cache and overlay the snapshot
    # ------------------------------------------------------------------

    def _build_battery_payload(self, pending: Dict[str, Any]) -> CycleStrategy:
        if self._battery_cache is None:
            raise SettingsValidationError(
                "No battery settings cache yet — wait for the first successful poll "
                "before submitting"
            )
        merged = copy.deepcopy(self._battery_cache)

        if "minimum_soc" in pending:
            merged.bat_use_cap = float(pending["minimum_soc"])
        if "charge_cap" in pending:
            if not merged.charge_slots:
                raise SettingsValidationError(
                    "Cannot set charge_cap: no charge slot defined on the inverter"
                )
            merged.charge_slots[0].charge_limit = float(pending["charge_cap"])
        if "grid_charging" in pending:
            merged.grid_charge_cycle = 1 if pending["grid_charging"] else 0
        if "discharge_time_control" in pending:
            merged.ctr_dis_cycle = 1 if pending["discharge_time_control"] else 0

        for field_name, slot_attr, slot_list_attr in (
            ("charge_start_time",    "begin_time", "charge_slots"),
            ("charge_end_time",      "end_time",   "charge_slots"),
            ("discharge_start_time", "begin_time", "discharge_slots"),
            ("discharge_end_time",   "end_time",   "discharge_slots"),
        ):
            if field_name in pending:
                slots = getattr(merged, slot_list_attr)
                if not slots:
                    raise SettingsValidationError(
                        f"Cannot set {field_name}: no slot defined on the inverter"
                    )
                setattr(slots[0], slot_attr, pending[field_name])

        if "charge_power" in pending:
            if not merged.charge_slots:
                raise SettingsValidationError("Cannot set charge_power: no charge slot")
            merged.charge_slots[0].charge_power = int(pending["charge_power"])
        if "discharge_power" in pending:
            if not merged.discharge_slots:
                raise SettingsValidationError("Cannot set discharge_power: no discharge slot")
            merged.discharge_slots[0].charge_power = int(pending["discharge_power"])

        return merged

    def _build_feedin_payload(
        self,
        pending_top: Dict[str, Any],
        pending_slots: Dict[int, Dict[str, Any]],
    ) -> GridFeedInSettings:
        if self._feedin_cache is None:
            raise SettingsValidationError(
                "No grid feed-in cache yet — wait for the first successful poll "
                "before submitting"
            )
        merged = copy.deepcopy(self._feedin_cache)

        if "enabled" in pending_top:
            merged.battery_en = 1 if pending_top["enabled"] else 0
        if "cutoff_soc" in pending_top:
            merged.battery_feed_cutoff_soc = float(pending_top["cutoff_soc"])

        for slot_index, slot_pending in pending_slots.items():
            while len(merged.slots) <= slot_index:
                merged.slots.append(GridFeedInSlot(sort=len(merged.slots) + 1))
            slot = merged.slots[slot_index]
            if "start" in slot_pending:
                slot.start = slot_pending["start"]
            if "end" in slot_pending:
                slot.end = slot_pending["end"]
            if "power" in slot_pending:
                slot.feed_power = int(slot_pending["power"])

        return merged
