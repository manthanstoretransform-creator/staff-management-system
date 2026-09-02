"""
The desktop's single authoritative duration formatter and IST day helper.

This mirrors ``backend/app/core/time_format.py`` deliberately: the whole point
of the time model is that the desktop, the API and the frontend cannot disagree
about what a duration of N seconds looks like, or about which calendar day a
piece of tracked time belongs to.

Two rules this module encodes:

  * A **duration** is exact integer seconds rendered as ``HH:MM:SS``. It is
    never passed through a timezone conversion, and it never wraps at 24 hours
    — 90061 seconds is ``25:01:01``, not ``01:01:01``. That rules out
    ``strftime`` and ``timedelta`` formatting.
  * A **day** is an IST calendar day, because that is the day the backend
    reports against. Deriving "today" from the machine's local date would put
    the desktop's cache bucket in a different day from the server's report the
    moment the machine is not on IST.

Widgets must not keep private copies of either of these; there were once
several competing counters, and one formatter per widget is the same defect in
a smaller form.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

#: Display/reporting timezone. A real zone definition, never a fixed offset.
IST = ZoneInfo("Asia/Kolkata")


def format_hms(total_seconds: int | float | None) -> str:
    """
    Format an exact duration in seconds as ``HH:MM:SS``.

    Integer arithmetic only. ``None`` and negatives render as ``00:00:00``:
    tracked time is never negative, and a clock that has moved backwards must
    not be allowed to display a nonsense duration.
    """
    if total_seconds is None:
        return "00:00:00"
    seconds = int(total_seconds)
    if seconds < 0:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def ist_today() -> date:
    """Today's date in IST — the same day the backend reports against."""
    return datetime.now(IST).date()


def ist_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """
    The half-open UTC bounds of an IST calendar day: ``[start, end)``.

    Mirrors ``backend/app/core/time_format.py``'s ``ist_day_start_utc`` /
    ``ist_day_end_utc``, so the desktop asks for exactly the interval the
    backend reports against.

    This exists because the dashboard used to build its day filter as a
    *naive* ``YYYY-MM-DDT00:00:00`` .. ``23:59:59`` pair. The backend compares
    those against ``timestamptz`` columns in a UTC session, so the desktop was
    really asking for a UTC calendar day while calling it the IST day -- a
    5½-hour shift. Anything tracked between 00:00 and 05:30 IST was attributed
    to the previous day, and anything after 23:30 IST to the next one.

    Half-open on purpose: an inclusive ``23:59:59`` bound silently drops
    whatever happened in the final second of the day.
    """
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=IST).astimezone(timezone.utc)
    return start, end


def to_ist(value: datetime | None) -> datetime | None:
    """Convert an aware (or UTC-assumed naive) timestamp to IST for display."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST)
