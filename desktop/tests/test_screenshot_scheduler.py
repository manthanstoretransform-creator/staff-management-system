"""The screenshot capture rule.

These are the tests for the thing that is otherwise only observable by waiting
ten minutes: that every window gets exactly the configured number of captures,
at random instants inside it, and never more — not across a restart, not when
tracking begins mid-window, and not when the machine wakes from suspend with
several planned instants already in the past.
"""
from __future__ import annotations

import random

from background_services.screenshot import config, scheduler

WINDOW = 600  # ten minutes, the production value


def _index_of(epoch: float) -> int:
    return scheduler.window_index(epoch, WINDOW)


class TestWindowArithmetic:
    def test_windows_are_aligned_to_the_epoch_so_every_client_agrees(self):
        # The backend groups the timeline by the same arithmetic, with no
        # window column stored anywhere, so the two must derive the same
        # boundaries from a bare timestamp.
        start, end = scheduler.window_bounds(_index_of(1_757_000_123), WINDOW)
        assert start % WINDOW == 0
        assert end - start == WINDOW
        assert start <= 1_757_000_123 < end

    def test_instants_ten_minutes_apart_are_in_different_windows(self):
        assert _index_of(1_757_000_000) != _index_of(1_757_000_000 + WINDOW)

    def test_a_zero_length_window_is_refused_rather_than_dividing_by_zero(self):
        try:
            scheduler.window_index(0, 0)
        except ValueError:
            return
        raise AssertionError("a zero-length window should not be accepted")


class TestPlanning:
    def test_one_capture_is_planned_for_a_full_window(self):
        index = _index_of(1_757_000_000)
        start, end = scheduler.window_bounds(index, WINDOW)
        times = scheduler.plan_window(index, WINDOW, 1, now=start)
        assert len(times) == 1
        assert start <= times[0] < end

    def test_the_planned_instant_is_random_rather_than_a_fixed_offset(self):
        # The whole point of the feature is that the user cannot predict when
        # the capture happens. A scheduler that always picked the midpoint
        # would satisfy every other test here.
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        seen = {
            scheduler.plan_window(index, WINDOW, 1, now=start, rng=random.Random(seed))[0]
            for seed in range(40)
        }
        assert len(seen) > 5

    def test_three_per_window_yields_three_distinct_ordered_instants(self):
        # The configuration change the module is designed for. Nothing in the
        # scheduler, the queue or the timeline assumes a window holds one.
        index = _index_of(1_757_000_000)
        start, end = scheduler.window_bounds(index, WINDOW)
        times = scheduler.plan_window(index, WINDOW, 3, now=start)
        assert len(times) == 3
        assert len(set(times)) == 3
        assert times == sorted(times)
        assert all(start <= t < end for t in times)

    def test_five_per_window_yields_five_distinct_instants(self):
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        times = scheduler.plan_window(index, WINDOW, 5, now=start)
        assert len(set(times)) == 5

    def test_a_window_never_plans_more_than_the_configured_count(self):
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        for per_window in (1, 3, 5):
            for seed in range(50):
                times = scheduler.plan_window(
                    index, WINDOW, per_window, now=start, rng=random.Random(seed)
                )
                assert len(times) <= per_window

    def test_planning_never_schedules_into_the_past(self):
        # Tracking usually starts mid-window. An instant already gone cannot be
        # captured, and scheduling one would fire immediately on the next tick.
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        midpoint = start + 300
        for seed in range(30):
            times = scheduler.plan_window(
                index, WINDOW, 3, now=midpoint, rng=random.Random(seed)
            )
            assert all(t > midpoint for t in times)

    def test_a_window_with_only_seconds_left_plans_nothing(self):
        index = _index_of(1_757_000_000)
        _, end = scheduler.window_bounds(index, WINDOW)
        assert scheduler.plan_window(index, WINDOW, 1, now=end - 0.5) == []

    def test_a_capture_is_never_planned_on_the_next_windows_boundary(self):
        # An instant that rounded onto `end` would be attributed to the next
        # window by the backend's grouping, which is the one place the client
        # and the server could silently disagree.
        index = _index_of(1_757_000_000)
        start, end = scheduler.window_bounds(index, WINDOW)
        for seed in range(50):
            for t in scheduler.plan_window(index, WINDOW, 5, now=start, rng=random.Random(seed)):
                assert t < end


class TestBudget:
    """A restart inside a window must not spend the window's budget twice."""

    def test_a_window_that_has_spent_its_budget_plans_nothing_more(self):
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        times = scheduler.plan_window(index, WINDOW, 1, now=start, already_captured=1)
        assert times == []

    def test_a_partially_spent_window_plans_only_the_remainder(self):
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        times = scheduler.plan_window(index, WINDOW, 3, now=start, already_captured=2)
        assert len(times) == 1

    def test_an_over_spent_budget_cannot_produce_a_negative_plan(self):
        index = _index_of(1_757_000_000)
        start, _ = scheduler.window_bounds(index, WINDOW)
        assert scheduler.plan_window(index, WINDOW, 1, now=start, already_captured=5) == []


class TestConfiguration:
    def test_the_production_rule_is_one_capture_per_ten_minute_window(self, monkeypatch):
        # The overrides are cleared first: they are deployment configuration,
        # and a developer's .env must not decide whether the shipped default is
        # correct. (It did — a local one-minute window failed this outright.)
        monkeypatch.delenv("MONITRA_SCREENSHOT_WINDOW_MINUTES", raising=False)
        monkeypatch.delenv("MONITRA_SCREENSHOTS_PER_WINDOW", raising=False)
        assert config.WINDOW_DURATION_MINUTES == 10
        assert config.SCREENSHOTS_PER_WINDOW == 1
        assert config.window_seconds() == 600
        assert config.screenshots_per_window() == 1

    def test_the_count_is_configurable_without_touching_the_scheduler(self, monkeypatch):
        monkeypatch.setenv("MONITRA_SCREENSHOTS_PER_WINDOW", "5")
        assert config.screenshots_per_window() == 5

    def test_a_nonsense_override_falls_back_to_the_shipped_value(self, monkeypatch):
        monkeypatch.setenv("MONITRA_SCREENSHOTS_PER_WINDOW", "not-a-number")
        assert config.screenshots_per_window() == config.SCREENSHOTS_PER_WINDOW

    def test_capture_can_be_disabled_entirely(self, monkeypatch):
        monkeypatch.setenv("MONITRA_SCREENSHOTS", "0")
        assert config.enabled() is False
