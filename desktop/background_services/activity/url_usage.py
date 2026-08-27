"""
url_usage — Browser URL usage aggregation for display in desktop UI.

Merges backend URL usage summary with pending local SQLite cache records.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.logging_setup import get_logger

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
) -> List[Dict[str, Any]]:
    """
    Build the ranked URL usage summary shown in the Activity section.
    Merges backend URL history with pending local SQLite records.
    """
    url_items: Dict[str, Dict[str, Any]] = {}

    params: Dict[str, Any] = {}
    if user_id:
        params["user_id"] = user_id

    # 1. Fetch from Backend
    try:
        response = api_client.get("/url-usage", params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", []) if isinstance(data, dict) else []
            for item in items:
                domain = item.get("domain") or "unknown"
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

    # 2. Merge local SQLite pending records
    if cache is not None:
        try:
            for record in cache.get_pending_url_usage():
                domain = record.get("domain") or "unknown"
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
