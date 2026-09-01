"""
unwanted_activity — declarative detection of suspicious input patterns
during an active tracking session.

Owned and driven by `ActivityService` (composition — this module starts no
threads and owns no timers; `feed()` is called from the service's own tick
with the per-second watched-key counts from `InputEventCounter`). It knows
nothing about Qt, storage, or the network: detections come back to the
caller through two callbacks so the service can queue records and raise
alerts through the channels that already own those jobs.

Rule semantics, per `DetectionRule`:

- A rolling window (`window_seconds`) of matching input counts is kept.
  When the count inside the window reaches `threshold`, that is one
  *occurrence*: recorded, alerted (subject to cooldown), counted.
- After an occurrence the rule enters a cooldown (`cooldown_seconds`);
  matching input during cooldown neither alerts nor records again, so a
  user holding CTRL cannot generate an event per second. The rolling
  window restarts after each occurrence.
- Every `deduct_after`-th occurrence within the same time entry requests
  a deduction of `deduction_seconds` (the caller queues it; the backend
  records it as an auditable adjustment, never touching the original
  tracked seconds).

The default rule set implements the requested "CTRL pressed 15+ times"
example. New rules are added by appending to DEFAULT_RULES — nothing in
the engine is specific to CTRL or to keyboards (an "excessive clicking"
rule is just a different key name fed from the mouse counters).
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, List, Optional, Tuple

from core.logging_setup import get_logger

log = get_logger("activity.unwanted")

#: Alert shown when a rule triggers. Tone matches the app's existing
#: notifications: factual, not accusatory, and actionable.
ALERT_MESSAGE = (
    "It looks like there has been repeated inactive/unwanted activity "
    "during your current time entry. Please make sure you are actively "
    "working."
)


@dataclass(frozen=True)
class DetectionRule:
    """One configurable suspicious-input pattern (spec item 7A's shape)."""
    activity_type: str          # e.g. "repeated_key"
    key: str                    # normalized input name, e.g. "ctrl"
    threshold: int              # matching inputs within window_seconds -> one occurrence
    window_seconds: int = 60    # rolling window the threshold applies to
    cooldown_seconds: int = 120  # no re-trigger sooner than this after an occurrence
    deduct_after: int = 3       # every Nth occurrence requests a deduction
    deduction_seconds: int = 600  # 10 minutes, per the requirement


DEFAULT_RULES: List[DetectionRule] = [
    DetectionRule(activity_type="repeated_key", key="ctrl", threshold=15),
]


@dataclass
class _RuleState:
    presses: Deque[Tuple[float, int]] = field(default_factory=deque)
    occurrences: int = 0
    alerts: int = 0
    cooldown_until: float = 0.0


class UnwantedActivityMonitor:
    """Feeds per-tick watched-key counts through the rule set.

    Callbacks (both invoked synchronously from `feed`, on the caller's
    thread):
      on_event(record: dict)      — one occurrence to persist/queue
      on_alert(message: str)      — the user-facing warning for it
    The deduction request is part of the event record
    (`deduction_seconds` > 0 on every `deduct_after`-th occurrence).
    """

    def __init__(
        self,
        rules: Optional[List[DetectionRule]] = None,
        on_event: Optional[Callable[[dict], None]] = None,
        on_alert: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rules = list(rules if rules is not None else DEFAULT_RULES)
        self._on_event = on_event
        self._on_alert = on_alert
        self._states: Dict[str, _RuleState] = {}
        self._active = False

    @property
    def watch_keys(self) -> set:
        """The key names the input counter must tally for these rules."""
        return {rule.key for rule in self.rules}

    # ── Session lifecycle (mirrors ActivityService's tracker interface) ──────

    def start_session(self) -> None:
        """Reset all rule state for a fresh tracking session."""
        self._states = {}
        self._active = True

    def stop_session(self) -> None:
        self._active = False
        self._states = {}

    # ── Detection ─────────────────────────────────────────────────────────────

    def feed(self, key_counts: Dict[str, int], now: Optional[float] = None) -> None:
        """Consume one tick's watched-key press counts.

        No-ops entirely when no session is active: no records, no alerts,
        no deductions outside a running time entry, by construction.
        """
        if not self._active or not key_counts:
            return
        now = time.monotonic() if now is None else now

        for rule in self.rules:
            count = key_counts.get(rule.key, 0)
            if count <= 0:
                continue
            state = self._states.setdefault(rule.key, _RuleState())

            if now < state.cooldown_until:
                continue  # matching input during cooldown is deliberately ignored

            state.presses.append((now, count))
            cutoff = now - rule.window_seconds
            while state.presses and state.presses[0][0] < cutoff:
                state.presses.popleft()

            in_window = sum(c for _, c in state.presses)
            if in_window < rule.threshold:
                continue

            # One occurrence: record, alert, maybe deduct; then cool down
            # and restart the window so the next occurrence needs a fresh
            # `threshold` presses.
            state.occurrences += 1
            state.alerts += 1
            state.cooldown_until = now + rule.cooldown_seconds
            state.presses.clear()

            deduct = state.occurrences % rule.deduct_after == 0
            record = {
                "client_event_id": str(uuid.uuid4()),
                "activity_type": rule.activity_type,
                "key_or_action": rule.key,
                "occurrence_count": in_window,
                "alerted": True,
                "alert_count": state.alerts,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "deduction_seconds": rule.deduction_seconds if deduct else 0,
                "occurrence_index": state.occurrences,
            }
            log.info(
                "unwanted activity: %s '%s' x%d (occurrence %d%s)",
                rule.activity_type, rule.key, in_window, state.occurrences,
                ", deducting" if deduct else "",
            )
            if self._on_event is not None:
                self._on_event(record)
            if self._on_alert is not None:
                self._on_alert(ALERT_MESSAGE)
