"""
The single authoritative time/duration helper for the time module.

Two concepts live here and must not be confused:

  * a **timestamp** is a point in time. It is stored and calculated in UTC
    (``timestamptz`` in Postgres) and converted to Asia/Kolkata only for
    user-facing display.
  * a **duration** is elapsed time. It is exact integer seconds, formatted as
    ``HH:MM:SS``, and is timezone-independent — a duration is never passed
    through a timezone conversion.

``format_hms`` is deliberately not built on ``strftime``/``timedelta``
formatting: those wrap or reformat past 24 hours, and a tracked duration of
25:10:30 must stay 25:10:30, not become 01:10:30.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

#: The organisation's display timezone. A real zone definition, never a
#: hard-coded +05:30 offset.
IST = ZoneInfo("Asia/Kolkata")


def format_hms(total_seconds: int | float | None) -> str:
    """
    Format an exact duration in seconds as ``HH:MM:SS``.

    Integer arithmetic only, so no floating-point drift. Hours are not capped:
    90061 seconds is ``25:01:01``. ``None`` and negative values render as
    ``00:00:00`` — a tracked duration is never negative, and clamping is safer
    than surfacing a nonsense value derived from a clock that moved backwards.
    """
    if total_seconds is None:
        return "00:00:00"
    seconds = int(total_seconds)
    if seconds < 0:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def to_ist(value: datetime | None) -> datetime | None:
    """
    Convert an aware UTC timestamp to Asia/Kolkata for display.

    A naive datetime is treated as UTC, because every timestamp this system
    persists is written as UTC; reading one as local time is how displayed
    times end up hours out.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST)


def ist_today() -> date:
    """The current calendar date in IST — the user's idea of 'today'."""
    return datetime.now(IST).date()


def ist_day_start_utc(value: date) -> datetime:
    """UTC instant at which the given IST calendar day begins (00:00 IST)."""
    return datetime.combine(value, time.min, tzinfo=IST).astimezone(timezone.utc)


def ist_day_end_utc(value: date) -> datetime:
    """
    UTC instant at which the given IST calendar day ends — i.e. 00:00 IST of
    the following day. Exclusive upper bound, matching the existing queries.
    """
    return datetime.combine(value + timedelta(days=1), time.min, tzinfo=IST).astimezone(timezone.utc)


def elapsed_seconds(start_time: datetime | None, end_time: datetime | None = None) -> int:
    """
    Exact elapsed seconds between two timestamps.

    With no ``end_time`` the duration is measured against the current UTC
    instant, which is what a *running* timer needs: elapsed time is available
    immediately, not only once the timer is stopped.

    The result is **rounded** to the nearest second, not truncated. ``int()``
    always loses the fractional part, so every stop under-reported by up to a
    second and never over-reported -- a systematic, one-directional loss. It
    was measured on real data: 90 of 2449 completed entries stored a value one
    second below ``round(end_time - start_time)``, and none stored one above.
    Rounding also makes this agree with Postgres's own
    ``round(extract(epoch from (end_time - start_time)))``, so the invariant
    ``total_seconds == end_time - start_time`` can be checked in SQL.
    """
    if start_time is None:
        return 0
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time is None:
        end_time = datetime.now(timezone.utc)
    elif end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    return max(0, round((end_time - start_time).total_seconds()))
