"""
retention — how far back the desktop itself will show activity.

The desktop is not an archive. Before this module the Activity panel asked the
backend for everything it had and summed it, so the Apps and URLs tabs showed
an all-time cumulative total and the client's memory and cache grew with the
account's whole history. Durable history still belongs on the server; the
desktop shows a recent window of it and sends the user to the web client for
anything older.

Two windows, because screenshots are far more expensive to hold than a row of
counted seconds:

  * **Screenshots** — today plus the previous 3 calendar days.
  * **Apps and URLs** — today plus the previous 7 calendar days.

A date outside its window is not an error and not an empty day: it is a date
whose data exists, on the server, reachable through the web client. The UI says
exactly that and offers the link, rather than fetching data it has decided not
to keep.

**This is a display policy, not a retention policy.** Nothing here deletes a
tracked record or a pending sync row. A segment captured nine days ago that has
still not uploaded stays in the local queue and still syncs; it simply is not
drawn. The two concerns were deliberately kept separate — dropping queued rows
because they aged out of a *display* window would lose real tracked time.

Days are IST calendar days throughout, the same day the backend reports
against and the same one `core.time_format` defines.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core.time_format import ist_today

#: Screenshots the desktop will load: today and this many days before it.
SCREENSHOT_DESKTOP_DAYS = 3
#: App and URL usage the desktop will load: today and this many days before it.
ACTIVITY_DESKTOP_DAYS = 7


class DateAvailability:
    """What the desktop can show for a selected date.

    Plain string constants rather than an Enum so they can be compared against
    a widget's mode string without conversion at every call site.
    """

    #: The date has not happened yet — nothing can have been tracked.
    FUTURE = "future"
    #: Inside the desktop's window: fetch and display it.
    AVAILABLE = "available"
    #: Real data, but older than the desktop keeps — link to the web client.
    ARCHIVED = "archived"


def availability(
    day: date, window_days: int, today: Optional[date] = None
) -> str:
    """Classify `day` against a desktop window of `window_days` past days.

    `today` is injectable so the boundaries can be tested without waiting for
    midnight; it defaults to the IST today every other date calculation in the
    desktop uses.

    The oldest available date is `today - window_days`, so a window of 3 admits
    four dates in all: today and the three before it.
    """
    reference = today if today is not None else ist_today()
    if day > reference:
        return DateAvailability.FUTURE
    if day < reference - timedelta(days=window_days):
        return DateAvailability.ARCHIVED
    return DateAvailability.AVAILABLE


def screenshot_availability(day: date, today: Optional[date] = None) -> str:
    """Availability of `day` in the Screenshots tab."""
    return availability(day, SCREENSHOT_DESKTOP_DAYS, today)


def activity_availability(day: date, today: Optional[date] = None) -> str:
    """Availability of `day` in the Apps and URLs tabs."""
    return availability(day, ACTIVITY_DESKTOP_DAYS, today)
