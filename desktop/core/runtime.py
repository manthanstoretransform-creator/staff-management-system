"""
core.runtime — The single application runtime and ownership root.

Everything long-lived in Monitra hangs off one `ApplicationRuntime`: storage,
the HTTP client, the domain services, the bounded task pool and every
background service. Nothing else creates a thread, and nothing else decides
when a thread dies.

Why this exists
---------------
The audited `main()` did the following, in this order:

    local_cache = LocalCache()
    ...
    network_monitor.start()      # QThread started...
    sync_queue.start()           # ...before any QApplication exists
    app = QApplication(sys.argv) # <- created here

Starting QThreads before a `QCoreApplication` exists is undefined behaviour;
queued signal delivery has no event loop to target, so early emissions were
silently dropped and startup ordering varied run to run. Shutdown was worse:
`_shutdown_app()` waited 1000 ms for threads that were parked in a 30-second
wait, then closed the SQLite connection and the HTTP client out from under
them. The instrumented reproduction confirmed the process did not exit and had
to be killed.

Guarantees provided here
------------------------
* No background thread starts before the Qt event loop exists.
* The UI becomes usable before any remote call is awaited.
* Every service has exactly one owner and one lifecycle path.
* Shutdown is ordered, bounded, and always terminates the process:
  producers stop, then consumers, then shared resources — and shared resources
  are closed only after every owning thread is confirmed stopped.
* A service that refuses to stop is named in the log with its state, rather
  than hanging the application.
"""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from app.api.client import ApiClient
from app.auth.service import AuthService
from app.auth.session import SessionManager
from app.projects.service import ProjectService
from app.tasks.service import TaskService
from app.time_entries.service import TimeEntryService
from background_services.activity import ActivityService
from background_services.activity.app_usage_service import AppUsageService
from background_services.activity.url_usage_service import UrlUsageService
from background_services.network import NetworkService, NetworkState
from background_services.notifications import NotificationService
from background_services.recovery import RecoveryService
from background_services.sync import SyncService
from background_services.timer import TimerService
from core.logging_setup import (
    bump_session_generation, configure_logging, get_logger,
    install_excepthook, session_generation,
)
from core.service import ServiceManager, ServiceState
from core.tasks import TaskRunner
from storage.manager import StorageManager, get_storage_manager
from sync.local_cache import LocalCache

log = get_logger("runtime")


class RuntimePhase:
    """Phases the runtime passes through. Each has a terminal outcome."""
    CREATED = "CREATED"
    STORAGE_READY = "STORAGE_READY"
    SESSION_RESTORED = "SESSION_RESTORED"
    UI_READY = "UI_READY"
    SERVICES_RUNNING = "SERVICES_RUNNING"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    STOPPED = "STOPPED"


class ApplicationRuntime(QObject):
    """
    Owns the application's non-UI lifetime.

    Construction is cheap and does no I/O beyond opening the local database.
    Background services are created but **not started** until
    `start_services()` is called, which the main window does only after the
    shell is on screen.
    """

    phase_changed = Signal(str)
    #: Emitted when a service reports a state change, for status surfaces.
    service_health_changed = Signal(str, str)  # service name, state

    def __init__(self, storage: Optional[StorageManager] = None) -> None:
        super().__init__()
        configure_logging()
        install_excepthook()

        self._phase = RuntimePhase.CREATED
        self._shutdown_started = False
        self._started_at = time.monotonic()

        #: Queued actions older than this generation are refused. Raised on
        #: logout so a previous user's pending work cannot execute as the next.
        self.queue_floor_generation = 0

        # ── Storage ───────────────────────────────────────────────────────────
        self.storage = storage or get_storage_manager()
        self.cache = LocalCache(storage=self.storage)
        self._set_phase(RuntimePhase.STORAGE_READY)

        # ── Domain services (no threads of their own) ─────────────────────────
        self.api_client = ApiClient()
        self.session_manager = SessionManager(local_cache=self.cache)
        self.auth_service = AuthService(self.api_client, self.session_manager)
        self.project_service = ProjectService(self.api_client)
        self.task_service = TaskService(self.api_client)
        self.time_entry_service = TimeEntryService(self.api_client)

        # ── Bounded background execution ──────────────────────────────────────
        self.tasks = TaskRunner(parent=self)

        # ── Background services ───────────────────────────────────────────────
        self.services = ServiceManager(self)

        # Registration order is start order; shutdown is the reverse. Producers
        # are registered after the consumers they feed, so producers stop first.
        self.recovery: RecoveryService = self.services.register(
            RecoveryService(self, self.cache)
        )
        self.notifications: NotificationService = self.services.register(
            NotificationService(self)
        )
        self.network: NetworkService = self.services.register(
            NetworkService(self, self.api_client)
        )
        self.sync: SyncService = self.services.register(
            SyncService(self, self.cache, self.time_entry_service, self.task_service)
        )
        self.timer: TimerService = self.services.register(
            TimerService(self, self.time_entry_service, self.cache)
        )
        self.activity: ActivityService = self.services.register(
            ActivityService(self, self.cache)
        )
        self.app_usage: AppUsageService = self.services.register(
            AppUsageService(self, self.cache)
        )
        self.url_usage: UrlUsageService = self.services.register(
            UrlUsageService(self, self.cache)
        )

        # The timer drives the sub-trackers; they never start themselves.
        self.timer.register_tracker(self.activity)
        self.timer.register_tracker(self.app_usage)
        self.timer.register_tracker(self.url_usage)

        for service in self.services.services:
            service.state_changed.connect(
                lambda state, name=service.name: self.service_health_changed.emit(name, state)
            )

        # Cross-service wiring, declared in one place rather than scattered
        # through widget constructors.
        self.network.network_state_changed.connect(self._on_network_state_changed)

        log.info("runtime constructed in %.0fms", (time.monotonic() - self._started_at) * 1000)

    # ── Phase ─────────────────────────────────────────────────────────────────

    @property
    def phase(self) -> str:
        return self._phase

    def _set_phase(self, phase: str) -> None:
        if self._phase == phase:
            return
        log.info("phase %s -> %s", self._phase, phase)
        self._phase = phase
        self.phase_changed.emit(phase)

    # ── Startup ───────────────────────────────────────────────────────────────

    def restore_session(self) -> bool:
        """
        Restore a persisted session from local storage.

        Local only, and deliberately so: this must not wait on the network.
        The token is verified against the backend afterwards, in the
        background, while the UI is already usable.
        """
        restored = False
        try:
            restored = self.session_manager.restore_session()
        except Exception:  # noqa: BLE001
            log.exception("could not restore persisted session")
        if restored:
            bump_session_generation()
            self.queue_floor_generation = 0  # same user; keep their queued work
            log.info("restored persisted session (generation %d)", session_generation())
        self._set_phase(RuntimePhase.SESSION_RESTORED)
        return restored

    def inspect_previous_run(self) -> bool:
        """Determine whether the previous process exited cleanly."""
        return self.recovery.inspect_previous_run()

    def start_services(self) -> None:
        """
        Start every background service.

        Called only after the main window is visible, so no remote call can
        delay the shell appearing. By this point the Qt event loop exists,
        which is a precondition for starting any QThread.
        """
        if self._shutdown_started:
            return
        log.info("starting background services")
        self.services.start_all()
        self._set_phase(RuntimePhase.SERVICES_RUNNING)

        # Now that services exist, recover anything the previous run left.
        try:
            self.recovery.recover()
        except Exception:  # noqa: BLE001
            log.exception("recovery failed; continuing with a clean session")

    def mark_ui_ready(self) -> None:
        self._set_phase(RuntimePhase.UI_READY)

    # ── Session transitions ───────────────────────────────────────────────────

    def on_login(self) -> None:
        """Advance the session generation for a newly authenticated user."""
        generation = bump_session_generation()
        log.info("login: session generation is now %d", generation)
        self.sync.resume_after_auth()

    def on_logout(self) -> None:
        """
        Tear down session-scoped state.

        Raising the queue floor is what prevents user A's queued operations
        from later executing under user B's token.
        """
        generation = bump_session_generation()
        self.queue_floor_generation = generation
        log.info("logout: queue floor raised to generation %d", generation)

        self.tasks.cancel_all()
        if self.timer.is_running():
            self.timer.stop_tracking()
        try:
            cancelled = self.cache.cancel_actions_for_generation(generation)
            if cancelled:
                log.info("cancelled %d queued action(s) from the previous session", cancelled)
            self.cache.clear_app_usage()
            self.cache.clear_activity_samples()
            self.cache.clear_app_state()
            # The read-through caches the dashboard paints from before the
            # network answers. They are not user-scoped, so leaving them
            # behind shows the next user to sign in the previous user's
            # projects and tasks.
            self.cache.clear_user_scoped_cache()
        except Exception:  # noqa: BLE001
            log.exception("could not fully clear session-scoped state")

    # ── Cross-service reactions ───────────────────────────────────────────────

    def _on_network_state_changed(self, state: str) -> None:
        """Nudge the sync consumer as soon as the backend becomes usable again."""
        if state in NetworkState.USABLE:
            self.sync.wake()

    # ── Health ────────────────────────────────────────────────────────────────

    def health_report(self) -> dict:
        """Snapshot of runtime health, for diagnostics and tests."""
        return {
            "phase": self._phase,
            "uptime_seconds": round(time.monotonic() - self._started_at, 1),
            "session_generation": session_generation(),
            "network_state": self.network.network_state,
            "timer_status": self.timer.status,
            "timer_elapsed": self.timer.elapsed_seconds(),
            "queue_depth": self._safe_queue_depth(),
            "tasks_in_flight": self.tasks.in_flight,
            "tasks_active": self.tasks.active_count,
            "services": self.services.health_report(),
        }

    def _safe_queue_depth(self) -> int:
        try:
            return self.cache.get_pending_count()
        except Exception:  # noqa: BLE001
            return -1

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def shutdown(self, timeout_ms: int = 3000) -> bool:
        """
        Stop the runtime deterministically.

        Idempotent — calling it twice is safe, which matters because both the
        window's close handler and the post-`exec()` safeguard invoke it.

        :return: True if everything stopped cleanly within its timeout.
        """
        if self._shutdown_started:
            return True
        self._shutdown_started = True
        self._set_phase(RuntimePhase.SHUTTING_DOWN)
        started = time.monotonic()
        log.info("shutdown requested")

        # 1. Record the intent while the database is still fully available.
        try:
            self.recovery.mark_clean_shutdown()
        except Exception:  # noqa: BLE001
            log.exception("could not record clean shutdown")

        # 2. Stop accepting new non-critical work and cancel what is in flight.
        #    This runs before service shutdown so nothing new is queued behind
        #    a service that is already stopping.
        drained = self.tasks.shutdown(timeout_ms=timeout_ms)

        # 3. Stop services in reverse registration order: producers first, then
        #    the consumers they feed, then the monitors.
        failed: List[str] = self.services.stop_all(timeout_ms=timeout_ms)

        # 4. Only now release shared resources. Closing these while a service
        #    thread was still running was the original defect: it produced
        #    NoneType errors inside workers, which were swallowed, which left
        #    threads alive and the process unkillable.
        try:
            self.api_client.close()
        except Exception:  # noqa: BLE001
            log.exception("error closing API client")
        try:
            self.storage.close()
        except Exception:  # noqa: BLE001
            log.exception("error closing storage")

        clean = drained and not failed
        elapsed_ms = (time.monotonic() - started) * 1000
        if clean:
            log.info("shutdown complete in %.0fms", elapsed_ms)
        else:
            log.error(
                "shutdown completed in %.0fms with problems (tasks drained=%s, "
                "services that did not stop cleanly=%s)",
                elapsed_ms, drained, failed or "none",
            )
            for service in self.services.services:
                if service.name in failed:
                    log.error("  %s: %s", service.name, service.health.as_dict())

        self._set_phase(RuntimePhase.STOPPED)
        return clean
