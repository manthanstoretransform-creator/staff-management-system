"""
network_monitor — Lightweight periodic network health checker.

Pings the API server at regular intervals and emits Qt Signals
for online/offline state transitions. The SyncQueue and TopBar
connect to these signals.

Behavior:
  - When healthy: check every 30 seconds
  - After a failure: check every 5 seconds until recovered
  - Emits status_changed(is_online) only on transitions
"""
from typing import Optional

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiConnectionError, ApiTimeoutError, ApiHttpError


class NetworkMonitor(QThread):
    """
    Background thread that periodically checks API reachability.

    Signals:
        status_changed(bool)  — emitted only on online↔offline transitions
        latency_measured(int) — emitted with round-trip ms on each successful check
    """
    status_changed = Signal(bool)   # True = online, False = offline
    latency_measured = Signal(int)  # milliseconds

    HEALTHY_INTERVAL_MS = 30000   # 30s between checks when online
    UNHEALTHY_INTERVAL_MS = 5000  # 5s between checks when offline

    def __init__(self, api_client: ApiClient, parent=None) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._running = True
        self._is_online = True  # assume online at start
        self._mutex = QMutex()
        self._condition = QWaitCondition()

    @property
    def is_online(self) -> bool:
        """Current network status."""
        return self._is_online

    def stop(self) -> None:
        """Signal the monitor to stop."""
        self._running = False
        self._condition.wakeAll()

    def check_now(self) -> None:
        """Force an immediate health check."""
        self._condition.wakeAll()

    def run(self) -> None:
        """Main monitoring loop."""
        while self._running:
            was_online = self._is_online

            try:
                import time
                start = time.monotonic()
                self._api_client.get("/auth/me")
                elapsed_ms = int((time.monotonic() - start) * 1000)

                self._is_online = True
                self.latency_measured.emit(elapsed_ms)

            except (ApiConnectionError, ApiTimeoutError):
                self._is_online = False
            except ApiHttpError as e:
                # HTTP response received (e.g. 401, 403, 404) -> server is reachable!
                elapsed_ms = int((time.monotonic() - start) * 1000)
                self._is_online = True
                self.latency_measured.emit(elapsed_ms)
            except Exception:
                self._is_online = False

            # Emit signal only on state transitions
            if self._is_online != was_online:
                self.status_changed.emit(self._is_online)

            # Sleep — shorter interval when offline for faster recovery detection
            interval = self.HEALTHY_INTERVAL_MS if self._is_online else self.UNHEALTHY_INTERVAL_MS

            self._mutex.lock()
            self._condition.wait(self._mutex, interval)
            self._mutex.unlock()
