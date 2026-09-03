"""
input_probe — OS-level user-input detection and counter tracking.

Tracks:
- Total keyboard strokes
- Total mouse clicks
- Total mouse movements
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Optional, Tuple, Dict, Any

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

    class _MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", _POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong)
        ]

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong)
        ]

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    # Win32 Constants
    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14

    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104

    WM_LBUTTONDOWN = 0x0201
    WM_RBUTTONDOWN = 0x0204
    WM_MBUTTONDOWN = 0x0207

    WM_MOUSEMOVE = 0x0200


class InputProbe:
    """Samples system-wide input counts and state."""

    def __init__(self) -> None:
        self._supported = _IS_WINDOWS
        self._last_cursor: Optional[Tuple[int, int]] = None

        self._lock = threading.Lock()
        self._keyboard_strokes = 0
        self._mouse_clicks = 0
        self._mouse_movements = 0

        self._hook_thread: Optional[threading.Thread] = None
        self._running = False
        self._kbd_hook = None
        self._mouse_hook = None

        if self._supported:
            self._start_hook_listener()
        else:
            log.warning(
                "system-wide input detection is unavailable on %s; "
                "activity will be recorded as unmeasured",
                sys.platform,
            )

    @property
    def supported(self) -> bool:
        return self._supported

    def _start_hook_listener(self) -> None:
        """Start Win32 low-level hooks in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._hook_thread = threading.Thread(target=self._hook_loop, daemon=True, name="InputHookThread")
        self._hook_thread.start()

    def _hook_loop(self) -> None:  # pragma: no cover - platform specific
        if not _IS_WINDOWS:
            return

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        def low_level_keyboard_proc(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0:
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    with self._lock:
                        self._keyboard_strokes += 1
            return _user32.CallNextHookEx(None, nCode, wParam, lParam)

        last_pos = [None]

        def low_level_mouse_proc(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0:
                if wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN):
                    with self._lock:
                        self._mouse_clicks += 1
                elif wParam == WM_MOUSEMOVE:
                    ms_struct = _MSLLHOOKSTRUCT.from_address(lParam)
                    curr_pos = (ms_struct.pt.x, ms_struct.pt.y)
                    if last_pos[0] is not None:
                        dx = curr_pos[0] - last_pos[0][0]
                        dy = curr_pos[1] - last_pos[0][1]
                        if (dx * dx + dy * dy) > 16:  # > 4px movement threshold
                            with self._lock:
                                self._mouse_movements += 1
                            last_pos[0] = curr_pos
                    else:
                        last_pos[0] = curr_pos
            return _user32.CallNextHookEx(None, nCode, wParam, lParam)

        try:
            self._kbd_proc = HOOKPROC(low_level_keyboard_proc)
            self._mouse_proc = HOOKPROC(low_level_mouse_proc)

            self._kbd_hook = _user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._kbd_proc, _kernel32.GetModuleHandleW(None), 0
            )
            self._mouse_hook = _user32.SetWindowsHookExW(
                WH_MOUSE_LL, self._mouse_proc, _kernel32.GetModuleHandleW(None), 0
            )

            msg = wintypes.MSG()
            while self._running:
                b_ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if b_ret <= 0:
                    break
                _user32.TranslateMessage(ctypes.byref(msg))
                _user32.DispatchMessageW(ctypes.byref(msg))

        except Exception:
            log.exception("Error in Win32 input hook loop")
        finally:
            if self._kbd_hook:
                _user32.UnhookWindowsHookEx(self._kbd_hook)
            if self._mouse_hook:
                _user32.UnhookWindowsHookEx(self._mouse_hook)

    def idle_seconds(self) -> Optional[float]:
        """Seconds since the last system-wide keyboard or mouse input.

        `None` when this platform cannot measure it, which callers must treat
        as "unknown" rather than as zero or as idle. Two cheap syscalls, so it
        is safe to call on every tick.

        This is the authoritative inactivity reading. Idle detection uses it
        rather than starting listeners of its own: the hooks and counters that
        feed the activity percentage are already the one place system input is
        observed, and a second global listener for the same events would be a
        duplicate capture path.
        """
        return self._idle_seconds()

    def _idle_seconds(self) -> Optional[float]:
        """Seconds since the last system-wide keyboard or mouse input."""
        if not self._supported:
            return None
        try:  # pragma: no cover - platform specific
            info = _LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
            if not _user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            now_ticks = _kernel32.GetTickCount()
            return ((now_ticks - info.dwTime) & 0xFFFFFFFF) / 1000.0
        except Exception:  # noqa: BLE001
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

    def sample(self, window_seconds: float) -> Optional[Dict[str, Any]]:
        """
        Snapshot input event counts and active status.
        Resets count snapshot for next interval.
        """
        if not self._supported:
            return None

        idle = self._idle_seconds()
        moved = self._cursor_moved()

        with self._lock:
            k_strokes = self._keyboard_strokes
            m_clicks = self._mouse_clicks
            m_moves = self._mouse_movements

            # Reset internal interval counters
            self._keyboard_strokes = 0
            self._mouse_clicks = 0
            self._mouse_movements = 0

        # Fallback activity check if hooks registered 0
        active = (idle is not None and idle < window_seconds) or moved or k_strokes > 0 or m_clicks > 0 or m_moves > 0

        return {
            "active": active,
            "mouse": moved or m_clicks > 0 or m_moves > 0,
            "keyboard": k_strokes > 0 or (active and not moved),
            "keyboard_strokes": k_strokes,
            "mouse_clicks": m_clicks,
            "mouse_movements": m_moves
        }

    def stop(self) -> None:
        self._running = False
