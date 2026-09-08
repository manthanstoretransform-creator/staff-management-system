"""
day_split — splitting a tracked segment at the IST midnight it crosses.

An app-usage or URL-usage segment is stored as one row: the instant it started
plus how many seconds it lasted. Every reader — the desktop's date filter, the
backend's `start_date`/`end_date`, the web client's reports — attributes that
row to the calendar day of its *start*. That is correct for every segment that
begins and ends on the same day, and wrong for the one segment a session that
runs past midnight produces:

    23:59:40  segment begins in VS Code
    00:00:40  segment flushed, 60 seconds

Stored whole, all 60 seconds land on the earlier day, including the 40 that
were worked on the new one. Yesterday's total is 40 seconds too high and
today's is 40 seconds too low — every night, for every tracker, on the one
boundary the user is most likely to look at ("why does today already show
time?").

Filtering in the UI cannot repair this: by then the row is a single opaque
duration with one timestamp, and the information about where the boundary fell
is gone. So the split happens where the fact is still known — at flush time,
before the row is written. A crossing segment becomes two rows, one per day,
each carrying its own start instant.

The function is pure and returns whole seconds that always re-add to the input
duration, so splitting can never invent or lose tracked time. A timestamp that
cannot be parsed is passed through unchanged rather than dropped: an
unattributable segment is still real work, and losing it would be a worse
error than mis-dating it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from core.time_format import ist_day_bounds_utc, to_ist


def _parse_utc(value: str) -> datetime | None:
    """Read a stored ISO-8601 instant, treating a naive one as UTC.

    Naive means UTC everywhere in the local cache — `datetime.now(timezone.utc)`
    is what writes these — so assuming local time here is how a timestamp ends
    up five and a half hours out.
    """
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def split_by_ist_day(
    start_iso: str, duration_seconds: int
) -> List[Tuple[str, int]]:
    """
    Split `[start, start + duration)` at every IST midnight it crosses.

    Returns `(start_iso, seconds)` pairs in chronological order, each wholly
    inside one IST calendar day. The seconds always sum to `duration_seconds`
    exactly: the boundary offset is taken in whole seconds and whatever is left
    goes to the final chunk, so no rounding can shave a second off a total.

    A segment that does not cross a boundary — the overwhelmingly common case —
    comes back as the single pair it went in as, with its original timestamp
    string untouched, so nothing is rewritten needlessly.
    """
    if duration_seconds <= 0:
        return []

    start = _parse_utc(start_iso)
    if start is None:
        # Unreadable timestamp: keep the segment whole rather than discard a
        # real measurement over a formatting problem.
        return [(start_iso, duration_seconds)]

    _, first_day_end = ist_day_bounds_utc(to_ist(start).date())
    if start + timedelta(seconds=duration_seconds) <= first_day_end:
        return [(start_iso, duration_seconds)]

    chunks: List[Tuple[str, int]] = []
    cursor = start
    remaining = duration_seconds
    while remaining > 0:
        _, day_end = ist_day_bounds_utc(to_ist(cursor).date())
        to_boundary = int((day_end - cursor).total_seconds())
        # A cursor sitting less than a second before midnight would otherwise
        # take zero seconds and loop forever. One second is the smallest unit
        # this data has, so advancing by it always terminates.
        if to_boundary < 1:
            to_boundary = 1
        take = min(remaining, to_boundary)
        chunks.append((cursor.isoformat(), take))
        cursor = cursor + timedelta(seconds=take)
        remaining -= take
    return chunks
