"""
app_usage — Application-usage aggregation for display.

Extracted from `ui.workers.LoadAppUsageWorker` so the logic is a plain,
testable function rather than a QThread subclass. It merges what the backend
has already recorded with what is still queued locally, so usage captured
while offline is visible immediately instead of only after a successful sync.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.logging_setup import get_logger

log = get_logger("activity.app_usage")

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


def build_app_usage_summary(
    api_client,
    cache=None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Build the ranked application-usage summary shown in the Activity section.

    Runs on a background thread via the shared task pool. It must not touch
    any widget.

    :param api_client: ApiClient used to fetch the backend summary.
    :param cache: LocalCache; pending local records are merged in.
    :param user_id: Optional user filter.
    :return: Rows ready for rendering, ordered by descending duration.
    """
    durations: Dict[str, int] = {}

    params: Dict[str, Any] = {}
    if user_id:
        params["user_id"] = user_id

    try:
        response = api_client.get("/app-usage/summary", params=params)
        if response.status_code == 200:
            for entry in response.json().get("applications", []):
                name = entry.get("application_name", "Unknown")
                durations[name] = durations.get(name, 0) + entry.get("duration_seconds", 0)
    except Exception as exc:  # noqa: BLE001
        # A backend failure must not hide locally captured usage.
        log.info("backend app-usage summary unavailable (%s); using local records only", exc)

    if cache is not None:
        try:
            for record in cache.get_pending_app_usage():
                name = record.get("application_name", "Unknown")
                durations[name] = durations.get(name, 0) + record.get("duration_seconds", 0)
        except Exception:  # noqa: BLE001
            log.exception("could not merge pending local app usage")

    total = sum(durations.values())
    rows: List[Dict[str, Any]] = []
    ranked = sorted(durations.items(), key=lambda item: item[1], reverse=True)

    for index, (name, seconds) in enumerate(ranked):
        rows.append({
            "name": name,
            "application_name": name,
            "seconds": seconds,
            "duration_seconds": seconds,
            "time_str": _format_duration(seconds),
            "percentage": round(seconds / total * 100) if total else 0,
            "color": COLOR_PALETTE[index % len(COLOR_PALETTE)],
            "letter": _initials(name),
        })
    return rows
