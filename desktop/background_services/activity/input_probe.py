"""
input_probe — OS-level user-input detection, without new dependencies.

The audit established that Monitra had **no** input capture of any kind: no
keyboard hook, no mouse hook, no `pynput`, and no backend field to send a
result to. `activity_percent` was only ever read off a backend screenshot
record with a default of `0`, which is exactly why every screenshot displayed
`0% Activity`. Nothing was broken — nothing existed.

This module supplies the missing capture stage using facilities already
present on the platform:

**Windows** — `GetLastInputInfo` reports the tick of the most recent keyboard
or mouse input, system-wide, including while Monitra is not focused. That is
the correct signal for a time-tracking product, and unlike an input hook it
requires no elevated privileges, installs nothing global, and cannot drop or
intercept the user's keystrokes. `GetCursorPos` separates pointer movement from
other input so keyboard and mouse can be reported apart.

**Other platforms** — no equivalent unprivileged system-wide API exists, so the
probe reports `supported = False` and the activity service records windows as
unmeasured rather than fabricating a number. A cross-platform implementation
needs an input-hook dependency (`pynput`), which is a deliberate product
decision rather than something to adopt silently.

Note on granularity: this measures *whether* input occurred in an interval, not
how many individual keystrokes. Per-keystroke counts require a hook. The
percentage Monitra reports is therefore "share of sampled seconds during which
the user was interacting", which is the standard definition for this class of
product and is exactly what the stored `active_seconds / window_seconds`
expresses.
"""
from __future__ import annotations

import sys
from typing import Optional, Tuple

from core.logging_setup import get_logger

log = get_logger("activity.probe")

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:  # pragma: no cover - platform specific
    import ctypes
    from ctypes import wintypes

    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32


class InputProbe:
    """Samples system-wide input state. One instance, owned by ActivityService."""

    def __init__(self) -> None:
        self._supported = _IS_WINDOWS
        self._last_input_tick: Optional[int] = None
        self._last_cursor: Optional[Tuple[int, int]] = None
        if not self._supported:
            log.warning(
                "system-wide input detection is unavailable on %s; "
                "activity will be recorded as unmeasured",
                sys.platform,
            )

    @property
    def supported(self) -> bool:
        return self._supported

    def _idle_seconds(self) -> Optional[float]:
        """Seconds since the last system-wide keyboard or mouse input."""
        if not self._supported:
            return None
        try:  # pragma: no cover - platform specific
            info = _LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
            if not _user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            # Both are 32-bit millisecond tick counts that wrap roughly every
            # 49 days; the masked subtraction stays correct across the wrap.
            now_ticks = _kernel32.GetTickCount()
            return ((now_ticks - info.dwTime) & 0xFFFFFFFF) / 1000.0
        except Exception:  # noqa: BLE001
            log.exception("GetLastInputInfo failed; disabling input probe")
            self._supported = False
            return None

    def _cursor_moved(self) -> bool:
        if not self._supported:
            return False
        try:  # pragma: no cover - platform specific
            point = _POINT()
            if not _user32.GetCursorPos(ctypes.byref(point)):
                return False
            position = (point.x, point.y)
            moved = self._last_cursor is not None and position != self._last_cursor
            self._last_cursor = position
            return moved
        except Exception:  # noqa: BLE001
            return False

    def sample(self, window_seconds: float) -> Optional[dict]:
        """
        Determine whether the user interacted during the last `window_seconds`.

        :return: {"active": bool, "mouse": bool, "keyboard": bool}, or None if
            input detection is unsupported on this platform.
        """
        idle = self._idle_seconds()
        if idle is None:
            return None
        moved = self._cursor_moved()
        # Input newer than the sampling window means it happened during it.
        active = idle < window_seconds or moved
        return {
            "active": active,
            "mouse": moved,
            # Input that is not pointer movement is attributed to the keyboard.
            # Distinguishing precisely requires an input hook; see module docs.
            "keyboard": active and not moved,
        }
