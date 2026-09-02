"""
today_summary — the one place today's activity percentage is computed.

The dashboard's TODAY'S ACTIVITY card is a single duration-weighted number:

    percent = SUM(window_percent x window_seconds) / SUM(window_seconds)

and it has to survive the fact that today's measurements live in three
different places at once:

  1. **Uploaded** windows, which only the backend has
     (``GET /time-entry-activities/today`` returns them already aggregated).
  2. **Queued** windows, captured locally but not yet uploaded — the offline
     case, and the ordinary case for the last minute or two of a session.
  3. The **window still being sampled**, which exists only in
     ``ActivityService``'s counters and has not been written anywhere.

Those three sets are disjoint by construction: a queued sample row is deleted
from the local cache only after its upload succeeded, and the in-flight window
is not written until it is flushed. So they can be summed — which is why this
module adds weighted totals rather than averaging percentages. Averaging three
percentages would let a 12-second tail window outweigh a 60-second one, which
is precisely the error the card must not make.

A plain dataclass and a couple of pure functions, deliberately: this is
arithmetic, so it belongs neither in a widget nor in a service loop, and it is
testable without a Qt application or a network.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from core.time_format import IST


@dataclass(frozen=True)
class ActivityTotals:
    """One weighted sum and its denominator, in seconds.

    ``weighted`` is ``SUM(percent x seconds)``; ``measured`` is
    ``SUM(seconds)``. Keeping the pair unreduced is what makes totals from
    different sources addable.
    """

    weighted: float = 0.0
    measured: int = 0

    def __add__(self, other: "ActivityTotals") -> "ActivityTotals":
        return ActivityTotals(
            weighted=self.weighted + other.weighted,
            measured=self.measured + other.measured,
        )

    @property
    def percent_exact(self) -> float:
        """The weighted percentage, clamped to 0-100.

        Nothing measured is 0%, not a division by zero and not a NaN: an
        honest zero is the only defensible reading of "no measurement".
        """
        if self.measured <= 0:
            return 0.0
        value = self.weighted / self.measured
        if value != value:  # NaN
            return 0.0
        return max(0.0, min(100.0, value))

    @property
    def percent(self) -> int:
        """The value the card shows: 72.4 -> 72, 72.6 -> 73."""
        return int(round(self.percent_exact))

    @property
    def has_measurement(self) -> bool:
        return self.measured > 0


def totals_from_percent(percent: float, seconds: int) -> ActivityTotals:
    """Build totals from a percentage that covers `seconds` of measurement."""
    if seconds <= 0:
        return ActivityTotals()
    clamped = max(0.0, min(100.0, float(percent)))
    return ActivityTotals(weighted=clamped * seconds, measured=int(seconds))


def ist_day_bounds_utc(day: date) -> tuple[str, str]:
    """
    The half-open UTC bounds of an IST calendar day, as ISO-8601 strings.

    "Today" is the IST day the backend reports against — the same definition
    ``core.time_format.ist_today`` uses — so the card and the server can never
    disagree about which side of midnight a window fell on. Deriving the
    bounds from UTC midnight instead would shift the day by five and a half
    hours and quietly mix two days' measurements.
    """
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=IST).astimezone(
        timezone.utc
    )
    return start.isoformat(), end.isoformat()


@dataclass(frozen=True)
class TodaySnapshot:
    """Everything already persisted for today, from both stores.

    `tracked_seconds` and `is_tracking` come from the backend and are carried
    only so the card can distinguish "nothing tracked yet" from "tracked, but
    activity capture measured nothing".
    """

    totals: ActivityTotals = ActivityTotals()
    tracked_seconds: int = 0
    is_tracking: bool = False
    remote_ok: bool = False


def build_today_snapshot(api_client, cache, day: date) -> TodaySnapshot:
    """
    Read today's persisted activity: the backend's aggregate plus the windows
    still queued locally.

    Blocking (one HTTP request and one SQLite read) — callers must run it
    through ``BackgroundApi.run_in_background``, never on the GUI thread.

    The remote read is issued **before** the local one on purpose. A window is
    deleted locally only after its upload has been acknowledged, so reading
    the server first means a window that uploads between the two reads is
    still counted exactly once (locally) rather than twice.

    A failed request is not an empty day: `remote_ok` is False and the caller
    keeps whatever it was already showing rather than dropping the card to 0%.
    """
    remote = ActivityTotals()
    tracked_seconds = 0
    is_tracking = False
    remote_ok = False
    try:
        response = api_client.get(
            "/time-entry-activities/today", params={"date": day.isoformat()}
        )
        payload = response.json() or {}
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            measured = int(data.get("measured_seconds") or 0)
            percent = float(
                data.get("activity_percentage_exact")
                if data.get("activity_percentage_exact") is not None
                else data.get("activity_percentage") or 0
            )
            remote = totals_from_percent(percent, measured)
            tracked_seconds = max(0, int(data.get("tracked_seconds") or 0))
            is_tracking = bool(data.get("is_tracking"))
            remote_ok = True
    except Exception:  # noqa: BLE001 — offline is an expected state here
        remote_ok = False

    start_iso, end_iso = ist_day_bounds_utc(day)
    local = ActivityTotals()
    try:
        row = cache.get_day_activity_totals(start_iso, end_iso)
        local = ActivityTotals(
            weighted=float(row.get("weighted", 0)), measured=int(row.get("measured", 0))
        )
    except Exception:  # noqa: BLE001
        local = ActivityTotals()

    return TodaySnapshot(
        totals=remote + local,
        tracked_seconds=tracked_seconds,
        is_tracking=is_tracking,
        remote_ok=remote_ok,
    )
