"""
network_service — The single authoritative source of network state.

Replaces `sync/network_monitor.py`, which had four defects that together
produced the reported "Online / Online (Slow: 2.3s) / Offline" flicker:

  * it assumed `is_online = True` before the first probe ever ran, so the UI
    published a state it had not measured;
  * a single transient failure flipped the state immediately — no debounce, no
    hysteresis;
  * it could not distinguish "this machine has no network" from "the backend
    is down" from "the token expired", so a 500 from the API read as offline
    and paused the sync queue;
  * it subclassed QThread with a `while` loop parked in a 30-second
    `QWaitCondition.wait()`, which `quit()` cannot interrupt.

This service runs on the `LoopService` pattern (QObject + moveToThread +
QTimer), so shutdown is deterministic. Probes are strictly sequential on one
thread, which is what makes stale-result-overwrites-newer-result structurally
impossible rather than merely unlikely; a monotonic probe sequence is still
recorded and published so consumers can reason about ordering.
"""
from __future__ import annotations

import socket
import time
from typing import Optional
from urllib.parse import urlparse

from PySide6.QtCore import Signal

from app.api.client import ApiClient
from app.api.exceptions import ApiConnectionError, ApiHttpError, ApiTimeoutError
from core.service import LoopService, ServiceState


class NetworkState:
    """Meaningful connectivity states (STEP 11 of the stability spec)."""
    UNKNOWN = "UNKNOWN"
    NO_NETWORK = "NO_NETWORK"
    NETWORK_AVAILABLE = "NETWORK_AVAILABLE"
    BACKEND_REACHABLE = "BACKEND_REACHABLE"
    BACKEND_UNREACHABLE = "BACKEND_UNREACHABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"

    #: States in which it is worth attempting API work.
    USABLE = frozenset({BACKEND_REACHABLE, AUTH_REQUIRED})


class NetworkService(LoopService):
    """
    Probes backend reachability and publishes one debounced, hysteretic state.

    Signals:
        network_state_changed(str)  — emitted only on a committed transition
        latency_measured(int)       — round-trip milliseconds, successful probes
    """

    name = "network"

    network_state_changed = Signal(str)
    latency_measured = Signal(int)

    #: Probe cadence when the backend is healthy.
    HEALTHY_INTERVAL_MS = 30_000
    #: Probe cadence while degraded — faster, but still bounded, and jittered
    #: so a fleet recovering from an outage does not synchronise.
    DEGRADED_INTERVAL_MS = 5_000
    #: Consecutive failures required before committing to a "down" state.
    #: One failure is noise; three in a row is a signal. This asymmetry is the
    #: hysteresis that stops the status pill flickering.
    FAILURES_TO_DEGRADE = 3
    #: Consecutive successes required to commit back to healthy.
    SUCCESSES_TO_RECOVER = 1
    #: A probe slower than this is reported as reachable-but-slow.
    SLOW_THRESHOLD_MS = 2_000
    #: Probes use a short timeout of their own; a health check must never
    #: inherit a 30-second upload timeout.
    PROBE_TIMEOUT_S = 4.0

    def __init__(self, runtime, api_client: ApiClient, parent=None) -> None:
        super().__init__(runtime, parent)
        self._api_client = api_client
        self._state = NetworkState.UNKNOWN
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._probe_sequence = 0
        self._last_latency_ms: Optional[int] = None
        self.interval_ms = self.DEGRADED_INTERVAL_MS

    # ── Public state ──────────────────────────────────────────────────────────

    # NOTE: this is `network_state`, not `state`. `BaseService.state` is the
    # *service lifecycle* (RUNNING / DEGRADED / STOPPED) and belongs to the
    # ServiceManager. An earlier revision overrode `state` here, which made the
    # service manager read connectivity where it expected lifecycle — the same
    # class of mistake as overloading `start()`.

    @property
    def network_state(self) -> str:
        """The committed network state (a `NetworkState` value)."""
        return self._state

    @property
    def is_online(self) -> bool:
        """
        True when API work is worth attempting.

        Retained under this name because existing UI code reads it; it now
        derives from the state machine rather than being its own variable.
        """
        return self._state in NetworkState.USABLE

    @property
    def last_latency_ms(self) -> Optional[int]:
        return self._last_latency_ms

    @property
    def is_slow(self) -> bool:
        return (
            self._last_latency_ms is not None
            and self._last_latency_ms >= self.SLOW_THRESHOLD_MS
        )

    def check_now(self) -> None:
        """Request an immediate probe (safe from any thread)."""
        self.wake()

    # ── Probing ───────────────────────────────────────────────────────────────

    def _host_port(self):
        parsed = urlparse(self._api_client.base_url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.hostname, port

    def _has_network_route(self) -> bool:
        """
        Cheap OS-level check for whether the API host is routable at all.

        This is what lets us distinguish NO_NETWORK from BACKEND_UNREACHABLE,
        so a backend outage does not tell the user their internet is down.
        """
        host, port = self._host_port()
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=2.0):
                return True
        except OSError:
            return False

    def _probe(self) -> str:
        """Run one probe and return the state it implies (uncommitted)."""
        started = time.monotonic()
        try:
            self._api_client.get("/auth/me", timeout=self.PROBE_TIMEOUT_S)
        except (ApiConnectionError, ApiTimeoutError):
            # Could be no network, or the backend being down. Ask the OS.
            return (
                NetworkState.BACKEND_UNREACHABLE
                if self._has_network_route()
                else NetworkState.NO_NETWORK
            )
        except ApiHttpError as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._last_latency_ms = elapsed_ms
            self.latency_measured.emit(elapsed_ms)
            if exc.status_code in (401, 403):
                # The server answered — it is reachable. The token is the
                # problem, which is a different condition entirely and must
                # not be reported to the user as being offline.
                return NetworkState.AUTH_REQUIRED
            if 500 <= exc.status_code < 600:
                return NetworkState.BACKEND_UNREACHABLE
            return NetworkState.BACKEND_REACHABLE
        except Exception:  # noqa: BLE001
            self.log.exception("unexpected error during network probe")
            return NetworkState.BACKEND_UNREACHABLE

        elapsed_ms = int((time.monotonic() - started) * 1000)
        self._last_latency_ms = elapsed_ms
        self.latency_measured.emit(elapsed_ms)
        return NetworkState.BACKEND_REACHABLE

    def tick(self) -> Optional[int]:
        """One probe cycle. Runs on the network service thread."""
        import random

        self._probe_sequence += 1
        sequence = self._probe_sequence
        observed = self._probe()

        healthy = observed in NetworkState.USABLE
        if healthy:
            self._consecutive_successes += 1
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            self._consecutive_successes = 0

        self.heartbeat(success=healthy)
        self.log.debug(
            "probe #%d observed=%s (fail streak=%d, ok streak=%d, %sms)",
            sequence, observed, self._consecutive_failures,
            self._consecutive_successes, self._last_latency_ms,
        )

        # Commit a transition only once the streak clears the threshold.
        commit = False
        if healthy and self._consecutive_successes >= self.SUCCESSES_TO_RECOVER:
            commit = True
        elif not healthy and self._consecutive_failures >= self.FAILURES_TO_DEGRADE:
            commit = True
        # AUTH_REQUIRED vs BACKEND_REACHABLE are both "usable"; switch between
        # them immediately since neither is a connectivity change.
        elif healthy and self._state in NetworkState.USABLE:
            commit = True

        if commit and observed != self._state:
            previous = self._state
            self._state = observed
            self.log.info("network state %s -> %s (probe #%d)", previous, observed, sequence)
            self.network_state_changed.emit(observed)
            self._set_state(
                ServiceState.RUNNING if healthy else ServiceState.DEGRADED,
                None if healthy else f"backend state {observed}",
            )

        base = self.HEALTHY_INTERVAL_MS if self.is_online else self.DEGRADED_INTERVAL_MS
        # Jitter so 200+ clients do not probe in lockstep after an outage.
        return int(base * (0.85 + random.random() * 0.3))

    def on_start(self) -> None:
        self._state = NetworkState.UNKNOWN
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        super().on_start()
