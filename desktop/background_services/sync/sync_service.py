"""
sync_service — The single durable synchronisation coordinator.

Replaces `sync/sync_queue.py`. Two changes matter far more than the rest.

**1. Signals are edge-triggered.**
The old consumer emitted `queue_empty` and `sync_status` on *every* poll of an
empty queue — twice a second, forever. The dashboard had `queue_empty` wired to
a full task reload plus a today's-time reload, so an idle application spawned
two new QThreads and two HTTP requests every second, indefinitely. Instrumented
reproduction measured 48 `LoadTodayTimeEntriesWorker` threads in 25 seconds.
That single defect accounted for the UI freezing, the loader never resolving,
the thread pileup and most of the "works one run, fails the next" behaviour.

Here, `queue_drained` fires once on the non-empty → empty transition, and
`pending_count_changed` fires only when the number actually changes. An idle
application is genuinely idle.

**2. There is exactly one consumer.**
`enqueue()` is the only way to schedule durable work. No feature module runs
its own retry loop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal

from app.api.exceptions import ApiError
from app.tasks.service import TaskService
from app.time_entries.service import TimeEntryService
from background_services.network import NetworkState
from core.logging_setup import session_generation
from core.service import LoopService, ServiceState
from sync.local_cache import LocalCache


class DeferAction(Exception):
    """
    Raised by a handler whose prerequisites are not ready yet.

    The action is rescheduled without counting a failure, so waiting on an
    ordering dependency never burns the retry budget.
    """


class UnresolvableAction(Exception):
    """
    Raised by a handler for an action that can never succeed.

    The action is cancelled rather than retried, so a permanently invalid item
    cannot occupy the queue forever.
    """


class SyncService(LoopService):
    """
    Drains the durable action queue against the backend.

    Signals:
        action_completed(str, str, dict)      — action_id, type, result
        action_failed(str, str, str, bool)    — action_id, type, error, will_retry
        auth_required()                       — 401; queue holds until re-auth
        queue_drained()                       — edge: queue became empty
        pending_count_changed(int)            — edge: depth changed
        synced_at_changed(object)             — edge: a sync to the backend just succeeded (datetime, UTC)
    """

    name = "sync"

    action_completed = Signal(str, str, dict)
    action_failed = Signal(str, str, str, bool)
    auth_required = Signal()
    queue_drained = Signal()
    pending_count_changed = Signal(int)
    synced_at_changed = Signal(object)

    #: Cadence while the queue has work.
    BUSY_INTERVAL_MS = 100
    #: Cadence while the queue is empty. The consumer is woken directly by
    #: `enqueue()`, so this is only a safety net for retry timers coming due.
    IDLE_INTERVAL_MS = 2_000
    #: Cadence while holding (offline or awaiting auth).
    HOLD_INTERVAL_MS = 5_000
    #: How many times a stop may wait for its start before being abandoned.
    #: At the 2s defer delay this is roughly a minute — long enough to cover a
    #: start request still in flight or retrying, short enough that an orphan
    #: does not sit in the queue indefinitely.
    MAX_STOP_DEFERRALS = 30

    #: Priorities — lower runs first.
    PRIORITY = {
        "stop_timer": 1,
        "start_timer": 2,
        "switch_timer": 3,
        "create_task": 5,
        "update_task": 5,
        "delete_task": 5,
        "activity_batch": 6,
        "app_usage_batch": 6,
    }

    def __init__(
        self,
        runtime,
        cache: LocalCache,
        time_entry_service: TimeEntryService,
        task_service: TaskService,
        parent=None,
    ) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self._time_entry_service = time_entry_service
        self._task_service = task_service

        self._awaiting_auth = False
        self._last_pending_count = -1
        self._was_empty = True
        self.interval_ms = self.IDLE_INTERVAL_MS
        #: When a sync last actually succeeded, this session only -- there is
        #: no durable store for it, so a restart starts this back at None.
        self._last_synced_at: Optional[datetime] = None

    # ── Public producer API ───────────────────────────────────────────────────

    def enqueue(
        self,
        action_type: str,
        payload: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> str:
        """
        Durably enqueue an operation. The only supported way to schedule sync
        work — no feature module may implement its own queue or retry loop.
        """
        action_id = self._cache.enqueue_action(
            action_type,
            payload,
            priority=priority if priority is not None else self.PRIORITY.get(action_type, 5),
            idempotency_key=idempotency_key,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        self.wake()
        return action_id

    def resume_after_auth(self) -> None:
        """Release the hold placed by a 401 once the user has re-authenticated."""
        self._awaiting_auth = False
        self.wake()

    @property
    def last_synced_at(self) -> Optional[datetime]:
        """UTC timestamp of the last action or batch upload that actually
        reached the backend successfully, this session. None until the first
        one completes."""
        return self._last_synced_at

    def _mark_synced(self) -> None:
        self._last_synced_at = datetime.now(timezone.utc)
        self.synced_at_changed.emit(self._last_synced_at)

    # ── Loop ──────────────────────────────────────────────────────────────────

    def _publish_depth(self) -> int:
        """Emit depth/drain signals only on an actual edge."""
        pending = self._cache.get_pending_count()

        if pending != self._last_pending_count:
            self._last_pending_count = pending
            self.pending_count_changed.emit(pending)

        is_empty = pending == 0
        if is_empty and not self._was_empty:
            # Edge only. Emitting this every poll was the worker-storm defect.
            self.log.info("queue drained")
            self.queue_drained.emit()
        self._was_empty = is_empty
        return pending

    def _should_hold(self) -> Optional[str]:
        """Return a reason to hold processing, or None to proceed."""
        if self._awaiting_auth:
            return "awaiting re-authentication"
        network = getattr(self.runtime, "network", None)
        if network is not None and network.network_state not in NetworkState.USABLE:
            if network.network_state != NetworkState.UNKNOWN:
                return f"network {network.network_state}"
        return None

    def tick(self) -> Optional[int]:
        hold_reason = self._should_hold()
        if hold_reason:
            self._publish_depth()
            self._set_state(ServiceState.DEGRADED, hold_reason)
            return self.HOLD_INTERVAL_MS

        if self.state == ServiceState.DEGRADED:
            self._set_state(ServiceState.RUNNING)

        action = self._cache.get_next_pending_action()
        if action is None:
            self._publish_depth()
            self._sync_app_usage()
            self._sync_url_usage()
            self._sync_activity()
            self.heartbeat()
            return self.IDLE_INTERVAL_MS

        self._process_action(action)
        self._publish_depth()
        self.heartbeat()
        return self.BUSY_INTERVAL_MS

    # ── Action processing ─────────────────────────────────────────────────────

    def _process_action(self, action: Dict[str, Any]) -> None:
        action_id = action["id"]
        action_type = action["action_type"]
        payload = action["payload"]

        # Work queued by a previous login must never run against the current
        # user's credentials.
        if action.get("session_generation", 0) < getattr(self.runtime, "queue_floor_generation", 0):
            self.log.warning(
                "cancelling stale action %s from generation %s",
                action_type, action.get("session_generation"), extra={"op": action_id},
            )
            self._cache.cancel_action(action_id, "stale session generation")
            return

        handlers = {
            "start_timer": self._handle_start_timer,
            "stop_timer": self._handle_stop_timer,
            "switch_timer": self._handle_switch_timer,
            "create_task": self._handle_create_task,
            "update_task": self._handle_update_task,
            "delete_task": self._handle_delete_task,
        }

        try:
            handler = handlers.get(action_type)
            if handler is None:
                self.log.warning("unknown action type %s; dropping", action_type,
                                 extra={"op": action_id})
                self._cache.complete_action(action_id)
                return
            if action_type == "stop_timer":
                result = handler(payload, action.get("defer_count", 0)) or {}
            else:
                result = handler(payload) or {}
        except DeferAction as exc:
            self.log.info("deferring %s: %s", action_type, exc, extra={"op": action_id})
            self._cache.defer_action(action_id, str(exc))
        except UnresolvableAction as exc:
            self.log.warning("cancelling %s: %s", action_type, exc, extra={"op": action_id})
            self._cache.cancel_action(action_id, str(exc))
        except ApiError as exc:
            self._handle_api_error(action_id, action_type, exc)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            self.log.exception("action %s failed unexpectedly", action_type, extra={"op": action_id})
            will_retry = self._cache.fail_action(action_id, error)
            self.action_failed.emit(action_id, action_type, error, will_retry)
        else:
            self._cache.complete_action(action_id)
            self.log.info("action %s completed", action_type, extra={"op": action_id})
            self._mark_synced()
            self.action_completed.emit(action_id, action_type, result)

    def _handle_api_error(self, action_id: str, action_type: str, exc: ApiError) -> None:
        message = str(exc)
        status = getattr(exc, "status_code", None)
        lowered = message.lower()

        if status == 401 or "session expired" in lowered:
            # Hold rather than burn retries against a token that cannot work.
            self._cache.fail_action(action_id, message, max_retries=0)
            self._awaiting_auth = True
            self.log.warning("authentication required; holding queue", extra={"op": action_id})
            self.auth_required.emit()
            self.action_failed.emit(action_id, action_type, "Session expired", False)
            return

        if status == 409 or "already has an active timer" in lowered or "already stopped" in lowered:
            # The server's state already reflects our intent. This is the
            # idempotency path: treat it as success, not as a failure to retry.
            self._cache.complete_action(action_id)
            self.log.info("action %s reconciled by conflict (409)", action_type,
                          extra={"op": action_id})
            self._mark_synced()
            self.action_completed.emit(action_id, action_type,
                                       {"conflict": True, "status_code": 409})
            return

        if status == 404 or "not found" in lowered:
            self._cache.complete_action(action_id)
            self.action_failed.emit(action_id, action_type, message, False)
            return

        will_retry = self._cache.fail_action(action_id, message)
        self.action_failed.emit(action_id, action_type, message, will_retry)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_start_timer(self, payload):
        entry_id = self._time_entry_service.start_time_entry(
            payload["project_id"], payload["task_id"]
        )
        # A stop queued for this same session has been waiting for this id.
        client_op = payload.get("client_op")
        if client_op and entry_id:
            self._cache.resolve_entry_id_for_client_op(client_op, entry_id)
        return {
            "entry_id": entry_id,
            "project_id": payload["project_id"],
            "task_id": payload["task_id"],
        }

    def _handle_stop_timer(self, payload, deferrals: int = 0):
        entry_id = payload.get("entry_id")
        client_op = payload.get("client_op")

        if not entry_id:
            # The session was started offline, so the backend has no entry to
            # stop yet. Wait for the start to land and resolve the id onto this
            # action, rather than calling stop with `None` — which stopped
            # nothing and left the entry running on the server.
            if client_op and self._cache.has_pending_action_for_client_op(
                client_op, "start_timer"
            ):
                raise DeferAction(f"waiting for the queued start of {client_op}")

            # No queued start — but that does not mean there never will be one.
            # If the user stops within a second of starting, the start request
            # is still in flight on the task pool and has not yet failed over
            # to the queue. Cancelling here orphaned the entry the start went on
            # to create. Wait out a bounded budget before giving up.
            if deferrals < self.MAX_STOP_DEFERRALS:
                raise DeferAction(
                    f"no queued start for {client_op} yet; the start may still "
                    f"be in flight (deferral {deferrals + 1}/{self.MAX_STOP_DEFERRALS})"
                )

            raise UnresolvableAction(
                f"stop_timer has no entry id and no start appeared within "
                f"{self.MAX_STOP_DEFERRALS} deferrals (client_op={client_op})"
            )

        result = self._time_entry_service.stop_time_entry(entry_id)
        if isinstance(result, dict) and payload.get("task_id"):
            result["task_id"] = payload["task_id"]
        return result

    def _handle_switch_timer(self, payload):
        old_entry_id = payload["old_entry_id"]
        stop_result: Dict[str, Any] = {}
        if old_entry_id and old_entry_id > 0:
            try:
                stop_result = self._time_entry_service.stop_time_entry(old_entry_id)
            except ApiError as exc:
                # Already stopped or gone: proceed to start the new entry, but
                # record why rather than discarding the detail.
                self.log.info("switch: old entry %s not stoppable (%s)", old_entry_id, exc)
                stop_result = {"warning": str(exc)}
        new_entry_id = self._time_entry_service.start_time_entry(
            payload["new_project_id"], payload["new_task_id"]
        )
        return {
            "stop_result": stop_result,
            "old_task_id": payload.get("old_task_id"),
            "new_entry_id": new_entry_id,
            "new_project_id": payload["new_project_id"],
            "new_task_id": payload["new_task_id"],
        }

    def _handle_create_task(self, payload):
        return self._task_service.create_task(
            payload["project_id"],
            payload["task_name"],
            payload.get("assignee_id") or 1,
            payload.get("status_id") or 1,
        )

    def _handle_update_task(self, payload):
        return self._task_service.update_task(
            payload["project_id"],
            payload["task_id"],
            payload["task_name"],
            payload.get("status_id") or 1,
            payload.get("assignee_id"),
        )

    def _handle_delete_task(self, payload):
        return self._task_service.delete_task(payload["project_id"], payload["task_id"])

    # ── Batched telemetry ─────────────────────────────────────────────────────

    def _sync_app_usage(self) -> None:
        """Batch-upload captured application usage, grouped by time entry."""
        try:
            pending = self._cache.get_pending_app_usage()
        except Exception:  # noqa: BLE001
            self.log.exception("could not read pending app usage")
            return
        if not pending:
            return

        grouped: Dict[int, list] = {}
        for record in pending:
            grouped.setdefault(record["time_entry_id"], []).append(record)

        for entry_id, records in grouped.items():
            record_ids = [r["id"] for r in records]
            self._cache.mark_app_usage_processing(record_ids)
            batch = {
                "records": [
                    {
                        "application_name": r["application_name"],
                        "window_title": r["window_title"],
                        "duration_seconds": r["duration_seconds"],
                        "recorded_at": r["recorded_at"],
                    }
                    for r in records
                ]
            }
            try:
                self._time_entry_service.batch_sync_app_usage(entry_id, batch)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("app usage batch for entry %s failed: %s", entry_id, exc)
                self._cache.fail_app_usage(record_ids, str(exc))
            else:
                self._cache.complete_app_usage(record_ids)
                self._mark_synced()

    def _sync_url_usage(self) -> None:
        """Batch-upload captured browser URL usage events."""
        try:
            pending = self._cache.get_pending_url_usage()
        except Exception:  # noqa: BLE001
            self.log.exception("could not read pending URL usage")
            return
        if not pending:
            return

        record_ids = [r["id"] for r in pending]
        self._cache.mark_url_usage_processing(record_ids)
        batch = {
            "records": [
                {
                    "time_entry_id": r["time_entry_id"],
                    "browser_name": r["browser_name"],
                    "domain": r["domain"],
                    "url": r["url"],
                    "page_title": r["page_title"],
                    "duration_seconds": r["duration_seconds"],
                    "recorded_at": r["recorded_at"],
                    "client_event_id": r["client_event_id"],
                }
                for r in pending
            ]
        }
        try:
            self._time_entry_service.batch_sync_url_usage(batch)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("URL usage batch sync failed: %s", exc)
            self._cache.fail_url_usage(record_ids, str(exc))
        else:
            self._cache.complete_url_usage(record_ids)
            self._mark_synced()
            self.log.info("URL usage batch sync succeeded for %d records", len(pending))

    def _sync_activity(self) -> None:
        """
        Batch-upload captured activity windows.
        """
        try:
            pending = self._cache.get_pending_activity_samples()
        except Exception:  # noqa: BLE001
            self.log.exception("could not read pending activity samples")
            return
        if not pending:
            return

        session_mgr = getattr(self.runtime, "session_manager", None)
        org_id = 1
        if session_mgr and hasattr(session_mgr, "user") and session_mgr.user:
            org_id = session_mgr.user.get("organization_id", 1)

        ids = [s["id"] for s in pending]
        batch = {
            "activities": [
                {
                    "organization_id": org_id,
                    "time_entry_id": s["time_entry_id"],
                    "recorded_at": s["window_start"],
                    "keyboard_strokes": s.get("keyboard_strokes", s.get("key_events", 0)),
                    "mouse_clicks": s.get("mouse_clicks", 0),
                    "mouse_movements": s.get("mouse_movements", s.get("mouse_events", 0)),
                    "activity_percentage": s.get("activity_percent", 0),
                }
                for s in pending
            ]
        }
        try:
            self._time_entry_service.batch_sync_activity(batch)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("activity batch sync failed: %s", exc)
            self._cache.fail_activity_samples(ids, str(exc))
        else:
            self._cache.complete_activity_samples(ids)
            self.log.info("activity batch sync succeeded for %d records", len(pending))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_start(self) -> None:
        # Recover anything a previous process left mid-flight before consuming.
        self._cache.reset_processing_actions()
        self._cache.reset_processing_app_usage()
        self._cache.reset_processing_url_usage()
        self._cache.clear_stale_actions()
        self._last_pending_count = -1
        self._was_empty = self._cache.get_pending_count() == 0
        super().on_start()

    def on_stop(self, timeout_ms: int) -> bool:
        stopped = super().on_stop(timeout_ms)
        # Release the claim on anything interrupted by shutdown so the next
        # run picks it up instead of leaving it stranded in 'processing'.
        try:
            self._cache.reset_processing_actions()
            self._cache.reset_processing_app_usage()
            self._cache.reset_processing_url_usage()
        except Exception:  # noqa: BLE001
            self.log.exception("could not release in-flight claims during shutdown")
        return stopped
