"""
Coverage for the unwanted-activity rule engine
(background_services/activity/unwanted_activity.py) -- pure logic, no Qt,
no storage, no listeners: fed synthetic per-tick key counts with explicit
timestamps so every path is deterministic.
"""
from background_services.activity.unwanted_activity import (
    ALERT_MESSAGE,
    DetectionRule,
    UnwantedActivityMonitor,
)


RULE = DetectionRule(
    activity_type="repeated_key", key="ctrl", threshold=15,
    window_seconds=60, cooldown_seconds=120, deduct_after=3,
    deduction_seconds=600,
)


def _monitor(events, alerts, rules=None):
    return UnwantedActivityMonitor(
        rules=rules if rules is not None else [RULE],
        on_event=events.append,
        on_alert=alerts.append,
    )


def test_threshold_crossing_produces_one_event_and_one_alert():
    events, alerts = [], []
    m = _monitor(events, alerts)
    m.start_session()

    for i in range(14):
        m.feed({"ctrl": 1}, now=100.0 + i)
    assert events == []  # 14 presses: below threshold

    m.feed({"ctrl": 1}, now=114.0)  # the 15th
    assert len(events) == 1
    assert alerts == [ALERT_MESSAGE]
    record = events[0]
    assert record["activity_type"] == "repeated_key"
    assert record["key_or_action"] == "ctrl"
    assert record["occurrence_count"] == 15
    assert record["alerted"] is True
    assert record["alert_count"] == 1
    assert record["deduction_seconds"] == 0  # first occurrence: no deduction
    assert record["client_event_id"]


def test_cooldown_suppresses_immediate_retrigger():
    events, alerts = [], []
    m = _monitor(events, alerts)
    m.start_session()

    for i in range(15):
        m.feed({"ctrl": 1}, now=100.0 + i)
    assert len(events) == 1

    # A storm of further presses inside the cooldown: no new events/alerts.
    for i in range(50):
        m.feed({"ctrl": 5}, now=116.0 + i)
    assert len(events) == 1
    assert len(alerts) == 1

    # After the cooldown expires, a fresh threshold's worth triggers again.
    base = 100.0 + 15 + RULE.cooldown_seconds + 1
    for i in range(15):
        m.feed({"ctrl": 1}, now=base + i)
    assert len(events) == 2
    assert events[1]["alert_count"] == 2


def test_third_occurrence_carries_the_deduction():
    events, alerts = [], []
    m = _monitor(events, alerts)
    m.start_session()

    now = 0.0
    for occurrence in range(3):
        for _ in range(15):
            now += 1.0
            m.feed({"ctrl": 15}, now=now)  # burst; window sums past threshold fast
        now += RULE.cooldown_seconds + 1  # let the cooldown lapse

    assert len(events) == 3
    assert events[0]["deduction_seconds"] == 0
    assert events[1]["deduction_seconds"] == 0
    assert events[2]["deduction_seconds"] == 600
    assert events[2]["occurrence_index"] == 3


def test_presses_older_than_the_window_do_not_count():
    events, alerts = [], []
    m = _monitor(events, alerts)
    m.start_session()

    # 14 presses, then a long pause that expires the rolling window, then 1:
    # never 15 inside any 60s window, so no event.
    for i in range(14):
        m.feed({"ctrl": 1}, now=100.0 + i)
    m.feed({"ctrl": 1}, now=100.0 + 14 + RULE.window_seconds + 1)
    assert events == []


def test_nothing_happens_without_an_active_session():
    events, alerts = [], []
    m = _monitor(events, alerts)
    # no start_session()
    for i in range(100):
        m.feed({"ctrl": 10}, now=float(i))
    assert events == []
    assert alerts == []

    m.start_session()
    m.stop_session()
    for i in range(100):
        m.feed({"ctrl": 10}, now=200.0 + i)
    assert events == []


def test_session_restart_resets_occurrence_and_alert_counts():
    events, alerts = [], []
    m = _monitor(events, alerts)
    m.start_session()
    for i in range(15):
        m.feed({"ctrl": 1}, now=100.0 + i)
    assert events[0]["alert_count"] == 1

    m.stop_session()
    m.start_session()  # a new time entry: counts start over
    for i in range(15):
        m.feed({"ctrl": 1}, now=500.0 + i)
    assert events[1]["alert_count"] == 1
    assert events[1]["occurrence_index"] == 1


def test_rules_are_declarative_not_ctrl_specific():
    """A second rule (excessive clicking, fed from the mouse counter under
    the name 'click') works with zero engine changes -- the extensibility
    requirement."""
    click_rule = DetectionRule(
        activity_type="excessive_clicking", key="click", threshold=5,
        window_seconds=10, cooldown_seconds=30, deduct_after=3,
        deduction_seconds=600,
    )
    events, alerts = [], []
    m = _monitor(events, alerts, rules=[RULE, click_rule])
    assert m.watch_keys == {"ctrl", "click"}
    m.start_session()

    for i in range(5):
        m.feed({"click": 1}, now=50.0 + i)
    assert len(events) == 1
    assert events[0]["activity_type"] == "excessive_clicking"
