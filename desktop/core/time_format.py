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

from datetime import date, datetime, timezone
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


def to_ist(value: datetime | None) -> datetime | None:
    """Convert an aware (or UTC-assumed naive) timestamp to IST for display."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST)
