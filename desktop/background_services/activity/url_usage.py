"""
url_usage — Browser URL usage aggregation for display in desktop UI.

Merges backend URL usage summary with pending local SQLite cache records, for
one IST calendar day.

Two defects this shape exists to prevent:

  * **All-time totals.** Both halves of the merge are filtered by the selected
    day's window. Previously neither was, so yesterday's browsing stayed in
    today's list.
  * **A truncated day.** The backend read is `GET /url-usage/summary`, which
    aggregates in the database. It used to be `GET /url-usage`, a raw row
    listing behind `limit=100`: on a day with more than a hundred URL rows the
    tab quietly showed a partial total and called it the day's usage.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from core.logging_setup import get_logger
from core.time_format import ist_day_bounds_utc

log = get_logger("activity.url_usage")

COLOR_PALETTE = [
    "#3B82F6", "#10B981", "#EC4899", "#8B5CF6", "#F97316",
    "#6366F1", "#1DB954", "#4B5563", "#0284C7", "#D97706",
]


def _format_duration(seconds: int) -> str:
    if seconds >= 3600:
        hours, minutes = seconds // 3600, (seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    if seconds >= 60:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _initials(name: str) -> str:
    words = name.split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    if len(name) >= 2:
        return name[:2].upper()
    return name.upper()


def build_url_usage_summary(
    api_client,
    cache=None,
    user_id: Optional[int] = None,
    day: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Build the ranked URL usage summary for one IST calendar day.

    Records without a domain are skipped rather than displayed. Nothing is
    substituted for a missing site: the capture layer only stores a URL
    record when it actually read one (see
    `background_services/activity/url_usage_service.py`), and a row here is
    therefore always a page the user really visited. The previous
    `domain or "unknown"` default is what turned an unreadable address bar
    into the link `https://unknown-domain` in the UI.

    Remote is read before local, for the same reason as in `app_usage.py`: a
    row leaves the local queue only once the server has acknowledged it, so
    that order counts a row uploading mid-refresh exactly once instead of
    twice. Local rows keep their own `client_event_id`, which is what the
    backend de-duplicates on, so nothing here disturbs idempotency.

    :param day: The IST calendar day to summarise. None returns nothing rather
        than an all-time total.
    """
    url_items: Dict[str, Dict[str, Any]] = {}
    if day is None:
        return []

    start, end = ist_day_bounds_utc(day)
    params: Dict[str, Any] = {
        "start_date": start.isoformat(),
        # This endpoint's end_date is exclusive by design, so the day is the
        # half-open [start, next start) every other filter here uses.
        "end_date": end.isoformat(),
    }
    if user_id:
        params["user_id"] = user_id

    # 1. Fetch the day's aggregate from the backend. Every page once, with its
    #    complete duration -- not a capped page of raw rows.
    try:
        response = api_client.get("/url-usage/summary", params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("pages", []) if isinstance(data, dict) else []
            for item in items:
                domain = item.get("domain")
                if not domain:
                    continue
                url_str = item.get("url") or f"https://{domain}"
                title = item.get("page_title") or domain
                key = url_str

                if key not in url_items:
                    url_items[key] = {
                        "url": url_str,
                        "title": title,
                        "domain": domain,
                        "seconds": 0,
                    }
                url_items[key]["seconds"] += item.get("duration_seconds", 0)
    except Exception as exc:  # noqa: BLE001
        log.info("backend url-usage summary unavailable (%s); using local records only", exc)

    # 2. Merge the same day's local rows that have not been uploaded yet.
    if cache is not None:
        try:
            for record in cache.get_unsynced_url_usage_between(
                start.isoformat(), end.isoformat()
            ):
                domain = record.get("domain")
                if not domain:
                    continue
                url_str = record.get("url") or f"https://{domain}"
                title = record.get("page_title") or domain
                key = url_str

                if key not in url_items:
                    url_items[key] = {
                        "url": url_str,
                        "title": title,
                        "domain": domain,
                        "seconds": 0,
                    }
                url_items[key]["seconds"] += record.get("duration_seconds", 0)
        except Exception:  # noqa: BLE001
            log.exception("could not merge pending local url usage")

    total = sum(item["seconds"] for item in url_items.values())
    rows: List[Dict[str, Any]] = []
    ranked = sorted(url_items.values(), key=lambda item: item["seconds"], reverse=True)

    for index, item in enumerate(ranked):
        seconds = item["seconds"]
        dom = item["domain"]
        rows.append({
            "url": item["url"],
            "title": item["title"],
            "domain": dom,
            "seconds": seconds,
            "duration_seconds": seconds,
            "time_str": _format_duration(seconds),
            "percentage": round(seconds / total * 100) if total else 0,
            "color": COLOR_PALETTE[index % len(COLOR_PALETTE)],
            "letter": _initials(dom),
        })

    return rows
