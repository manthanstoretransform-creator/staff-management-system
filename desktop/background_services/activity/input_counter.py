"""
input_counter — cross-platform keyboard/mouse *event counting* via pynput.

The existing `input_probe.py` answers "did any input occur this second?"
(Windows `GetLastInputInfo`, two cheap syscalls, no hook). It cannot count
keystrokes, clicks, or movements, and it has no macOS implementation. This
module supplies the counting stage the backend's `time_entry_activity`
columns need (`keyboard_strokes` / `mouse_clicks` / `mouse_movements`),
using a different backend per platform:

- **Windows** — `pynput` global listeners, a dependency adopted with
  explicit user sign-off (input_probe.py's own docstring calls that "a
  deliberate product decision rather than something to adopt silently").
- **macOS** — a listen-only Quartz event tap (`mac_input_tap.py`). pynput
  is *not* used, and is not even installed, because its macOS keyboard
  listener resolves keys through Carbon's Text Services Manager, which on
  macOS 26 raises an uncatchable SIGTRAP when called off the main dispatch
  queue and killed Monitra the instant a timer started. The tap needs no
  extra dependency and never decodes a key at all.

Privacy contract, enforced here and nowhere else:

- Only *counters* are kept. Which character was typed is never stored,
  logged, or transmitted — the keyboard callback increments an integer
  and, for the small set of `watch_keys` the unwanted-activity rules
  register (e.g. "ctrl"), a per-key press tally. Nothing else about the
  key survives the callback.
- Listeners run only while a tracking session is active: `start()` on
  timer start, `stop()` on timer stop. No capture outside a session.

Platform permissions:

- **Windows**: pynput uses a low-level hook (`SetWindowsHookEx`); no
  special permission or elevation is required.
- **macOS**: global input monitoring requires the user to grant this app
  **Input Monitoring** (and, on some versions, Accessibility) permission
  in System Settings → Privacy & Security. If the permission is missing,
  macOS typically delivers no events rather than raising — so counts stay
  at zero and activity falls back to "unmeasured", exactly like the
  pre-existing probe behaviour. A hard failure to create the listener
  (some macOS versions raise) is caught and reported as unsupported. The
  app never crashes over a denied permission.

Threading: pynput runs its listeners on their own native threads (not
QThreads — the architecture checker's QThread prohibition is about Qt
threading, and these are owned and stopped deterministically by this
class). Callbacks touch shared counters under a lock; `stop()` stops both
listeners and is called from the owning service's `stop_tracker`/
`on_stop`, inside the runtime's shutdown budget.
"""
from __future__ import annotations

import sys
import threading
from typing import Dict, Iterable, Optional

from core.logging_setup import get_logger

log = get_logger("activity.counter")


def _normalize_key(key) -> Optional[str]:
    """Collapse a pynput key object to a stable lowercase name.

    Special keys collapse left/right variants ("ctrl_l" → "ctrl") so a
    rule for "ctrl" matches either. Character keys normalize to their
    lowercase character. Returns None for anything unrecognizable.
    """
    try:
        name = getattr(key, "name", None)  # keyboard.Key.* (special keys)
        if name:
            for prefix in ("ctrl", "shift", "alt", "cmd"):
                if name.startswith(prefix):
                    return prefix
            return name
        char = getattr(key, "char", None)  # keyboard.KeyCode (printable)
        if char:
            return char.lower()
    except Exception:  # noqa: BLE001
        pass
    return None


class InputEventCounter:
    """Counts keystrokes, mouse clicks and mouse movements between
    `snapshot_and_reset()` calls, plus per-key press tallies for the
    registered `watch_keys` (the unwanted-activity rules' keys)."""

    def __init__(self, watch_keys: Optional[Iterable[str]] = None) -> None:
        self._watch_keys = {k.lower() for k in (watch_keys or ())}
        self._lock = threading.Lock()
        self._keystrokes = 0
        self._clicks = 0
        self._movements = 0
        self._watched: Dict[str, int] = {}
        self._keyboard_listener = None
        self._mouse_listener = None
        self._mac_tap = None  # macOS uses a Quartz tap instead; see _start_macos
        self._supported: Optional[bool] = None  # unknown until first start()

    # ── Callbacks (listener threads) ──────────────────────────────────────────

    def _on_press(self, key) -> None:
        name = _normalize_key(key)
        with self._lock:
            self._keystrokes += 1
            if name and name in self._watch_keys:
                self._watched[name] = self._watched.get(name, 0) + 1

    def _on_click(self, x, y, button, pressed) -> None:
        if pressed:
            with self._lock:
                self._clicks += 1

    def _on_move(self, x, y) -> None:
        with self._lock:
            self._movements += 1

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @property
    def supported(self) -> bool:
        """False once a start attempt has failed (pynput missing or the OS
        refused the hook); None-as-unknown reads as True so the first
        start() gets its chance."""
        return self._supported is not False

    def start(self) -> bool:
        """Start counting. Returns True when input events are being counted.

        Never raises: a missing backend or an OS-level refusal marks the
        counter unsupported (logged once) and counting simply stays at
        zero — the caller's existing unmeasured/zero handling covers it.
        """
        if sys.platform == "darwin":
            return self._start_macos()
        if self._keyboard_listener is not None:
            return True  # already running
        try:
            from pynput import keyboard, mouse

            self._keyboard_listener = keyboard.Listener(on_press=self._on_press)
            self._mouse_listener = mouse.Listener(
                on_click=self._on_click, on_move=self._on_move
            )
            self._keyboard_listener.start()
            self._mouse_listener.start()
        except ImportError:
            if self._supported is not False:
                log.warning(
                    "pynput is not installed; keyboard/mouse counting is "
                    "unavailable (activity falls back to presence detection)"
                )
            self._supported = False
            self._keyboard_listener = None
            self._mouse_listener = None
            return False
        except Exception:  # noqa: BLE001 — e.g. macOS permission refusal
            if self._supported is not False:
                log.exception(
                    "input listeners could not start (on macOS this usually "
                    "means Input Monitoring permission has not been granted); "
                    "keyboard/mouse counting is unavailable"
                )
            self._supported = False
            self.stop()
            return False
        self._supported = True
        return True

    def _start_macos(self) -> bool:
        """
        Start the Quartz event tap instead of pynput's listeners.

        pynput's macOS keyboard listener translates every key to a character
        through Carbon's Text Services Manager, which on macOS 26 asserts it
        is being called on the main dispatch queue. From pynput's own
        listener thread that assertion raises SIGTRAP and kills the process
        outright — an EXC_BREAKPOINT no try/except can catch. It was observed
        killing Monitra the instant a timer was started on macOS 26.5.2.

        Monitra only ever needed counts, never characters, so the fix is to
        use an API that does not decode keys at all. See mac_input_tap.py.
        """
        if self._mac_tap is not None:
            return True  # already running

        from background_services.activity.mac_input_tap import (
            MacInputTap, unresolvable_watch_keys,
        )

        unresolvable = unresolvable_watch_keys(self._watch_keys)
        if unresolvable and self._supported is None:
            # Named rather than silently dropped: a rule that never fires is
            # otherwise indistinguishable from a user who never pressed it.
            log.warning(
                "watched keys %s cannot be identified individually on macOS "
                "(a printable key's identity depends on the keyboard layout, "
                "and reading the layout is the call that crashes). They are "
                "still included in the keystroke total.",
                sorted(unresolvable),
            )

        tap = MacInputTap(
            on_key=self._on_mac_key,
            on_click=lambda: self._on_click(0, 0, None, True),
            on_move=lambda: self._on_move(0, 0),
        )
        if not tap.start():
            self._supported = False
            return False

        self._mac_tap = tap
        self._supported = True
        return True

    def _on_mac_key(self, name: Optional[str]) -> None:
        """Count one macOS key event, already reduced to a name or None."""
        with self._lock:
            self._keystrokes += 1
            if name and name in self._watch_keys:
                self._watched[name] = self._watched.get(name, 0) + 1

    def stop(self) -> None:
        """Stop all listeners deterministically. Safe to call repeatedly."""
        if self._mac_tap is not None:
            try:
                self._mac_tap.stop()
            except Exception:  # noqa: BLE001
                log.exception("could not stop the macOS input tap")
            self._mac_tap = None

        for attr in ("_keyboard_listener", "_mouse_listener"):
            listener = getattr(self, attr)
            if listener is not None:
                try:
                    listener.stop()
                except Exception:  # noqa: BLE001
                    log.exception("could not stop %s", attr)
                setattr(self, attr, None)

    # ── Reading ───────────────────────────────────────────────────────────────

    def snapshot_and_reset(self) -> Dict[str, int]:
        """Return counts accumulated since the previous call, and reset."""
        with self._lock:
            out = {
                "keystrokes": self._keystrokes,
                "clicks": self._clicks,
                "movements": self._movements,
            }
            self._keystrokes = 0
            self._clicks = 0
            self._movements = 0
        return out

    def drain_watched_presses(self) -> Dict[str, int]:
        """Per-watched-key press counts since the previous call, and reset."""
        with self._lock:
            out = dict(self._watched)
            self._watched.clear()
        return out
