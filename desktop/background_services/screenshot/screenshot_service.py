"""
screenshot_service — Captures screenshots while, and only while, time is tracked.

Ownership
---------
This is a `LoopService`, registered with `ApplicationRuntime` and driven by
`TimerService` through the same `start_tracker` / `bind_entry_id` /
`stop_tracker` contract the activity, app-usage and URL trackers already use.
It owns no thread of its own beyond the one `LoopService` gives it, it runs no
retry loop (the durable queue and `SyncService` do that), and it never touches
the UI. A second background timer next to the runtime's is exactly the class of
"quick fix" that destabilised this application before — see DO_NOT_DO.md.

What a tick does
----------------
The tick is a scheduler, not a sleeper. It asks
`scheduler.plan_window()` for the capture instants inside the current window,
takes the ones that have come due, and returns the milliseconds until the next
one — so an idle window costs one wake-up, not a poll per second.

The per-window budget survives a restart: how many captures a window has spent
is persisted in `app_state` under `SCREENSHOT_WINDOW_KEY`, so relaunching
Monitra four minutes into a window cannot take a second screenshot the window
has already paid for.

Nothing here uploads. A capture is processed, written to the daily cache and
registered in the durable queue; `SyncService` drains that queue and deletes
the local file only once the backend confirms storage.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal

from background_services.screenshot import capture, config, image_processor, scheduler, store
from core.service import LoopService

#: Durable record of the window budget already spent, so a restart inside a
#: window cannot exceed `SCREENSHOTS_PER_WINDOW`.
SCREENSHOT_WINDOW_KEY = "screenshot_window_state"


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


class ScreenshotService(LoopService):
    """
    Owns screenshot capture.

    Signals:
        screenshot_captured(dict) — one capture queued for upload
        capture_unavailable(str)  — this machine cannot take screenshots
    """

    name = "screenshot"

    screenshot_captured = Signal(dict)
    capture_unavailable = Signal(str)

    #: Idle cadence. Overridden every tick by the time until the next capture,
    #: so this only bounds how long the service can sleep through a stop.
    IDLE_INTERVAL_MS = 5_000
    #: Never sleep longer than this, so `stop_tracker` is noticed promptly and
    #: a system clock jump cannot park the loop for a whole window.
    MAX_SLEEP_MS = 30_000

    #: Capturing and encoding a 4K frame takes a moment; give shutdown enough
    #: budget that a tick in progress finishes rather than being terminated.
    stop_timeout_ms = 5_000

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self.interval_ms = self.IDLE_INTERVAL_MS

        self._tracking = False
        self._entry_id: Optional[int] = None
        #: The window a session's first captures belong to, used to attribute
        #: them once the backend issues an entry id.
        self._session_window_start: Optional[str] = None

        self._planned_index: Optional[int] = None
        self._planned_times: List[float] = []
        self._unavailable_reported = False

    # ── Tracker contract (driven by TimerService) ─────────────────────────────

    def start_tracker(self, session: Dict[str, Any]) -> None:
        """Begin capturing for a tracking session."""
        if not config.enabled():
            self.log.info("screenshot capture is disabled by configuration")
            return
        self._entry_id = session.get("entry_id")
        self._tracking = True
        self._planned_index = None
        self._planned_times = []
        self._session_window_start = _iso(
            scheduler.window_bounds(
                scheduler.window_index(time.time(), config.window_seconds()),
                config.window_seconds(),
            )[0]
        )
        self.log.info(
            "screenshot capture started for entry %s (%d per %ds window)",
            self._entry_id, config.screenshots_per_window(), config.window_seconds(),
        )
        self.wake()

    def bind_entry_id(self, entry_id: int) -> None:
        """
        Attach the backend entry id once it arrives.

        Captures already queued for this session's window are attributed to the
        entry, so a screenshot taken in the first seconds of tracking — or
        during an offline start — is uploaded rather than stranded.
        """
        self._entry_id = entry_id
        if not self._session_window_start:
            return
        try:
            bound = self._cache.bind_screenshots_to_entry(self._session_window_start, entry_id)
        except Exception:  # noqa: BLE001
            self.log.exception("could not bind queued screenshots to entry %s", entry_id)
            return
        if bound:
            self.log.info("attributed %d queued screenshot(s) to entry %s", bound, entry_id)

    def stop_tracker(self) -> None:
        """Stop capturing immediately. Queued screenshots still upload."""
        if self._tracking:
            self.log.info("screenshot capture stopped for entry %s", self._entry_id)
        self._tracking = False
        self._entry_id = None
        self._planned_index = None
        self._planned_times = []
        self._session_window_start = None

    # ── Window budget ─────────────────────────────────────────────────────────

    def _spent(self, index: int) -> int:
        """How many captures the given window has already taken."""
        try:
            record = self._cache.load_app_state(SCREENSHOT_WINDOW_KEY)
        except Exception:  # noqa: BLE001
            self.log.exception("could not read the screenshot window budget")
            return 0
        if not isinstance(record, dict) or record.get("index") != index:
            return 0
        return int(record.get("captured", 0))

    def _record_capture(self, index: int) -> None:
        try:
            self._cache.save_app_state(
                SCREENSHOT_WINDOW_KEY,
                {"index": index, "captured": self._spent(index) + 1},
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not persist the screenshot window budget")

    # ── Loop ──────────────────────────────────────────────────────────────────

    def tick(self) -> Optional[int]:
        if not self._tracking or self.stopping:
            return self.IDLE_INTERVAL_MS

        if not self._capture_available():
            return self.IDLE_INTERVAL_MS

        now = time.time()
        window = config.window_seconds()
        index = scheduler.window_index(now, window)

        if index != self._planned_index:
            self._planned_index = index
            self._planned_times = scheduler.plan_window(
                index, window, config.screenshots_per_window(), now,
                already_captured=self._spent(index),
            )
            if self._planned_times:
                self.log.info(
                    "window %d: %d capture(s) planned at %s",
                    index, len(self._planned_times),
                    ", ".join(
                        datetime.fromtimestamp(t).strftime("%H:%M:%S")
                        for t in self._planned_times
                    ),
                )

        # Take everything that has come due. Normally one; a machine that was
        # suspended can wake with several past instants in the same window, and
        # capturing the same screen twice a second apart is pointless — so only
        # the most recent overdue instant is honoured and the rest are dropped.
        overdue = [t for t in self._planned_times if t <= now]
        if overdue:
            self._planned_times = [t for t in self._planned_times if t > now]
            self._capture_now(index)
            self.heartbeat()

        return self._sleep_ms(now, index, window)

    def _sleep_ms(self, now: float, index: int, window: int) -> int:
        """Milliseconds until the next planned capture, or the window boundary."""
        if self._planned_times:
            target = self._planned_times[0]
        else:
            # Nothing left in this window; wake at the next window's start to
            # plan it. Never a per-second poll.
            target = scheduler.window_bounds(index + 1, window)[0]
        return max(250, min(self.MAX_SLEEP_MS, int((target - now) * 1000)))

    def _capture_available(self) -> bool:
        """Whether this machine can capture and process a screenshot at all."""
        if capture.supported() and image_processor.supported():
            return True
        if not self._unavailable_reported:
            self._unavailable_reported = True
            reason = (
                "screen capture is unavailable on this installation"
                if not capture.supported()
                else "image processing is unavailable on this installation"
            )
            self.log.warning("%s; no screenshots will be captured", reason)
            self.capture_unavailable.emit(reason)
        return False

    # ── Capture ───────────────────────────────────────────────────────────────

    def _capture_now(self, index: int) -> None:
        """Capture, process, persist and queue one screenshot."""
        raw = capture.capture_primary_monitor()
        if raw is None:
            return  # already logged; the window's budget is deliberately not spent

        processed = image_processor.process(raw)
        if processed is None or not processed.data:
            return

        client_screenshot_id = str(uuid.uuid4())
        captured_at = datetime.now(timezone.utc)
        path = store.write_screenshot(client_screenshot_id, processed.data, captured_at)
        if path is None:
            return

        window_start = _iso(scheduler.window_bounds(index, config.window_seconds())[0])
        entry_id = self._entry_id
        if entry_id is None:
            # The backend has not issued an id yet (a slow or offline start).
            # The row is queued unattributed and bound by `bind_entry_id`.
            session = self.runtime.timer.active_session() or {}
            entry_id = session.get("entry_id")
            self._entry_id = entry_id

        try:
            self._cache.save_screenshot(
                client_screenshot_id=client_screenshot_id,
                local_file_path=str(path),
                captured_at=captured_at.isoformat(),
                window_start=window_start,
                width=processed.width,
                height=processed.height,
                file_size_bytes=processed.size_bytes,
                time_entry_id=entry_id,
                monitor_number=raw.monitor_number,
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not queue screenshot %s", client_screenshot_id)
            store.delete_screenshot(str(path))
            return

        self._record_capture(index)
        self.log.info(
            "captured screenshot %s for entry %s (%dx%d, %d bytes, quality %d)",
            client_screenshot_id, entry_id, processed.width, processed.height,
            processed.size_bytes, processed.quality,
        )
        self.screenshot_captured.emit({
            "client_screenshot_id": client_screenshot_id,
            "time_entry_id": entry_id,
            "captured_at": captured_at.isoformat(),
            "window_start": window_start,
            "file_size_bytes": processed.size_bytes,
        })
        # Upload promptly rather than on the sync loop's idle cadence.
        sync = getattr(self.runtime, "sync", None)
        if sync is not None:
            sync.wake()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_start(self) -> None:
        # Anything a previous process left claimed goes back to pending, so a
        # crash mid-upload resumes rather than stranding the file.
        try:
            recovered = self._cache.reset_uploading_screenshots()
            if recovered:
                self.log.info("recovered %d interrupted screenshot upload(s)", recovered)
        except Exception:  # noqa: BLE001
            self.log.exception("could not recover interrupted screenshot uploads")
        super().on_start()

    def on_stop(self, timeout_ms: int) -> bool:
        self._tracking = False
        return super().on_stop(timeout_ms)
