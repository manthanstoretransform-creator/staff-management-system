"""
background_services.public_api — The supported surface for UI and features.

UI and feature modules must import from **this module only**. They must not
import service implementations, and must never touch QThread, worker
lifecycles, sync-queue internals or network polling internals directly. That
boundary is enforced by `tools/check_architecture.py` in CI.

The rule exists because the audit traced several production failures to
feature code owning runtime concerns: transient widgets owning long-running
threads, a dashboard slot wired straight to a queue-internal signal (which
produced the two-threads-per-second storm), and per-widget elapsed-time
counters competing with the timer's own state.

Everything here is a thin, intention-revealing call onto the runtime.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from background_services.activity.app_usage import build_app_usage_summary
from background_services.network import NetworkState
from background_services.notifications import NotificationLevel, create_app_icon
from background_services.timer import TimerStatus
from core.tasks import TaskHandle

__all__ = [
    "BackgroundApi", "NetworkState", "NotificationLevel", "TimerStatus",
    "TaskHandle", "create_app_icon",
]


class BackgroundApi:
    """
    Facade over the ApplicationRuntime, handed to UI components.

    Holds no state of its own; it exists so that UI code has a narrow,
    documented surface and cannot reach into service internals.
    """

    def __init__(self, runtime) -> None:
        self._runtime = runtime

    # ── Background work ───────────────────────────────────────────────────────

    def run_in_background(
        self,
        fn: Callable[[], Any],
        *,
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[BaseException], None]] = None,
        key: Optional[str] = None,
    ) -> Optional[TaskHandle]:
        """
        Run `fn` off the GUI thread on the shared bounded pool.

        Callbacks are delivered on the GUI thread. Passing `key` de-duplicates:
        if a task with that key is already running, this call is dropped and
        None is returned. UI code must use this instead of creating a QThread.
        """
        return self._runtime.tasks.submit(
            fn, on_success=on_success, on_error=on_error, key=key
        )

    def cancel(self, handle: Optional[TaskHandle]) -> None:
        self._runtime.tasks.cancel(handle)

    def cancel_key(self, key: str) -> None:
        self._runtime.tasks.cancel_key(key)

    # ── Timer ─────────────────────────────────────────────────────────────────

    @property
    def timer(self):
        """
        The authoritative timer service.

        Read `elapsed_seconds()` from it for display; never maintain a separate
        counter in a widget.
        """
        return self._runtime.timer

    def start_timer(self, project_id: int, task_id: int, task_name: Optional[str] = None) -> None:
        self._runtime.timer.start_tracking(project_id, task_id, task_name)

    def stop_timer(self) -> None:
        self._runtime.timer.stop_tracking()

    def switch_timer(self, project_id: int, task_id: int, task_name: Optional[str] = None) -> None:
        self._runtime.timer.switch_tracking(project_id, task_id, task_name)

    def timer_elapsed_seconds(self) -> int:
        return self._runtime.timer.elapsed_seconds()

    def is_timer_running(self) -> bool:
        return self._runtime.timer.is_running()

    def active_session(self) -> Optional[Dict[str, Any]]:
        return self._runtime.timer.active_session()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def enqueue(self, action_type: str, payload: Dict[str, Any], **kwargs) -> str:
        """
        Durably enqueue an operation for background synchronisation.

        The only supported way to schedule sync work. Feature modules must not
        implement their own queues, retry loops or backoff.
        """
        return self._runtime.sync.enqueue(action_type, payload, **kwargs)

    @property
    def sync(self):
        """The sync service, for connecting to its public signals."""
        return self._runtime.sync

    def pending_count(self) -> int:
        return self._runtime.cache.get_pending_count()

    # ── Network ───────────────────────────────────────────────────────────────

    @property
    def network(self):
        """The authoritative network service. There is exactly one."""
        return self._runtime.network

    def network_state(self) -> str:
        return self._runtime.network.network_state

    def is_online(self) -> bool:
        return self._runtime.network.is_online

    # ── Activity ──────────────────────────────────────────────────────────────

    @property
    def activity(self):
        return self._runtime.activity

    def activity_supported(self) -> bool:
        """False when this platform cannot measure input activity."""
        return self._runtime.activity.supported

    def current_activity_percent(self) -> int:
        return self._runtime.activity.current_percent()

    def activity_percent_for_entry(self, entry_id: int) -> int:
        return self._runtime.activity.percent_for_entry(entry_id)

    def app_usage_summary(self) -> list:
        """
        Build the ranked application-usage summary.

        Blocking: call it through `run_in_background`, never on the GUI thread.
        """
        return build_app_usage_summary(self._runtime.api_client, self._runtime.cache)

    # ── Notifications ─────────────────────────────────────────────────────────

    @property
    def notifications(self):
        return self._runtime.notifications

    def notify(self, message: str, level: str = NotificationLevel.INFO,
               key: Optional[str] = None) -> None:
        self._runtime.notifications.notify(message, level, key=key)

    # ── Data access ───────────────────────────────────────────────────────────

    @property
    def cache(self):
        """Repository access to local storage. Read/write via its methods only."""
        return self._runtime.cache

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def health_report(self) -> dict:
        return self._runtime.health_report()
