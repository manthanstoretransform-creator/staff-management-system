"""
recovery_service — Detects unclean shutdown and drives deterministic recovery.

The audit found no way for the application to know whether the previous run
ended cleanly. That mattered because the previous run frequently *did not*:
the 4 MB un-checkpointed WAL in `~/.monitra` was evidence that the process was
routinely being killed rather than exiting, and the instrumented reproduction
confirmed the process would not exit on request.

This service maintains a small durable runtime record — pid, heartbeat,
generation, clean-shutdown flag — so the next launch can tell the difference
between "the user quit" and "the process died", and recover accordingly.

Recovery is idempotent by construction. It adopts persisted records rather
than replaying operations, so running it twice produces the same state and can
never create duplicate time entries or duplicate queue items.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal

from core.logging_setup import session_generation
from core.service import LoopService

#: Key under which the durable runtime record lives in app_state.
RUNTIME_STATE_KEY = "runtime_state"


class RecoveryService(LoopService):
    """
    Records runtime liveness and reports on the previous run.

    Signals:
        unclean_shutdown_detected(dict) — the previous run's last record
        recovery_completed(dict)        — summary of what was recovered
    """

    name = "recovery"

    unclean_shutdown_detected = Signal(dict)
    recovery_completed = Signal(dict)

    #: Liveness is written at this cadence, on the service's own thread.
    HEARTBEAT_INTERVAL_MS = 15_000
    #: A heartbeat older than this means the process did not shut down cleanly.
    STALE_AFTER_SECONDS = 120.0

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self.interval_ms = self.HEARTBEAT_INTERVAL_MS
        self._previous: Optional[Dict[str, Any]] = None
        self._was_unclean = False

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def previous_run(self) -> Optional[Dict[str, Any]]:
        return dict(self._previous) if self._previous else None

    @property
    def previous_run_was_unclean(self) -> bool:
        return self._was_unclean

    # ── Inspection of the previous run ────────────────────────────────────────

    def inspect_previous_run(self) -> bool:
        """
        Read the previous run's record. Call once, before services start.

        :return: True if the previous run ended uncleanly.
        """
        try:
            record = self._cache.load_app_state(RUNTIME_STATE_KEY)
        except Exception:  # noqa: BLE001
            self.log.exception("could not read previous runtime record")
            return False

        if not record or not isinstance(record, dict):
            self.log.info("no previous runtime record; treating as first run")
            return False

        self._previous = record
        if record.get("clean_shutdown"):
            self.log.info("previous run exited cleanly")
            return False

        last_beat = record.get("last_heartbeat") or 0
        age = time.time() - last_beat
        self._was_unclean = True
        self.log.warning(
            "previous run (pid %s) did not shut down cleanly; last heartbeat %.0fs ago",
            record.get("pid"), age,
        )
        self.unclean_shutdown_detected.emit(dict(record))
        return True

    def recover(self) -> Dict[str, Any]:
        """
        Run recovery for an unclean previous shutdown.

        Ordering matters and is fixed: durable queue claims are released before
        the timer is recovered, so a recovered timer's stop can never be
        blocked behind a stranded 'processing' row.
        """
        summary: Dict[str, Any] = {"unclean": self._was_unclean}

        try:
            self._cache.reset_processing_actions()
            self._cache.reset_processing_app_usage()
            summary["queue_pending"] = self._cache.get_pending_count()
        except Exception:  # noqa: BLE001
            self.log.exception("queue recovery failed")
            summary["queue_pending"] = 0

        timer = getattr(self.runtime, "timer", None)
        if timer is not None:
            recovered = timer.recover()
            summary["timer_recovered"] = bool(recovered)
            if recovered:
                summary["timer_entry_id"] = recovered.get("entry_id")
                summary["timer_task_id"] = recovered.get("task_id")

        self.log.info("recovery complete: %s", summary)
        self.recovery_completed.emit(summary)
        return summary

    # ── Liveness ──────────────────────────────────────────────────────────────

    def _write_record(self, clean: bool) -> None:
        try:
            self._cache.save_app_state(
                RUNTIME_STATE_KEY,
                {
                    "pid": os.getpid(),
                    "last_heartbeat": time.time(),
                    "clean_shutdown": clean,
                    "session_generation": session_generation(),
                },
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not write runtime record")

    def tick(self) -> Optional[int]:
        self._write_record(clean=False)
        self.heartbeat()
        return self.HEARTBEAT_INTERVAL_MS

    def mark_clean_shutdown(self) -> None:
        """
        Record that this run is ending deliberately.

        Called by the runtime's shutdown sequence *before* services stop, so
        the flag is written while the database is still fully available.
        """
        self._write_record(clean=True)
        self.log.info("clean shutdown recorded")
