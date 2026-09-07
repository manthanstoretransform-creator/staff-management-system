"""
screenshot.capture — Reading pixels off the screen.

`mss` is imported lazily and its absence is reported honestly rather than
worked around: on a machine where the screen cannot be read, no screenshot is
produced and no row is queued. There is no placeholder image, exactly as there
is no placeholder domain in the URL tracker (see DO_NOT_DO.md).

Only the primary monitor is captured. `mss.monitors[0]` is the union of every
display and `monitors[1]` is the primary one; the union is deliberately not
used, because a two-monitor desktop letterboxed into 1000x1000 is unreadable.
The captured display's index is returned so it can be stored as
`monitor_number`, which is what a future multi-monitor capture will vary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.logging_setup import get_logger

log = get_logger("screenshot.capture")

#: Resolved once; `None` until the first probe, then the module or False.
_mss_module = None


@dataclass(frozen=True)
class RawCapture:
    """One screen grab, before any processing."""

    #: Raw BGRA bytes as `mss` produces them.
    pixels: bytes
    width: int
    height: int
    #: 1-based display index, matching `time_entry_screenshots.monitor_number`.
    monitor_number: int


def _load_mss():
    global _mss_module
    if _mss_module is None:
        try:
            import mss  # type: ignore

            _mss_module = mss
        except Exception:  # noqa: BLE001 - ImportError, and platform load errors
            log.warning(
                "mss is not available; screen capture is unsupported on this "
                "installation and no screenshots will be taken",
                exc_info=True,
            )
            _mss_module = False
    return _mss_module or None


def supported() -> bool:
    """Whether this machine can produce a screenshot at all."""
    return _load_mss() is not None


def capture_primary_monitor() -> Optional[RawCapture]:
    """
    Grab the primary display.

    :return: the capture, or None when the screen cannot be read. Never
        raises: a failed grab must not take down the service thread.
    """
    module = _load_mss()
    if module is None:
        return None

    try:
        # A fresh instance per capture: mss's screen handles are not safe to
        # share across threads, and a capture happens at most once every few
        # minutes, so there is nothing to gain from caching one.
        with module.mss() as sct:
            monitors = sct.monitors
            if len(monitors) < 2:
                # Only the "all monitors" pseudo-entry exists — a headless or
                # virtual session. Nothing meaningful to capture.
                log.warning("no physical display reported; skipping capture")
                return None
            shot = sct.grab(monitors[1])
            return RawCapture(
                pixels=bytes(shot.bgra),
                width=shot.width,
                height=shot.height,
                monitor_number=1,
            )
    except Exception:  # noqa: BLE001
        log.exception("screen capture failed")
        return None
