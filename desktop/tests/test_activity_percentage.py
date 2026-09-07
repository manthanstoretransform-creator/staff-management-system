"""How the activity percentage is computed.

The number is derived from the keyboard, click and movement counts actually
observed in a window. It used to be derived from presence — "in how many
sampled seconds did the OS report recent input" — through a branch whose
condition (`active_seconds >= 0`, on a counter) was always true, which made
the weighted model below it unreachable. Two consequences were visible in
production data and are pinned here so they cannot return:

* presence saturates, so a day of screenshots all read an identical 100%;
* presence comes from the OS, which sees input the client's own hooks cannot,
  so windows were recorded at 100% with zero counted events — a number
  nothing in the captured data supported.
"""
from __future__ import annotations

import pytest

from background_services.activity.activity_service import (
    KEYBOARD_WEIGHT, MAX_KEYBOARD_STROKES_PER_INTERVAL,
    MAX_MOUSE_CLICKS_PER_INTERVAL, MAX_MOUSE_MOVEMENTS_PER_INTERVAL,
    MOUSE_CLICK_WEIGHT, MOUSE_MOVEMENT_WEIGHT,
    calculate_activity_percentage as percent,
)


class TestCountsDriveTheNumber:
    def test_a_window_with_no_observed_input_is_zero_however_present_the_user_was(self):
        # The defect exactly: two production rows read 100% and 82% with
        # keys=0, clicks=0, moves=0.
        assert percent(0, 0, 0, active_seconds=60, window_seconds=60) == 0
        assert percent(0, 0, 0, active_seconds=18, window_seconds=18) == 0

    def test_identical_presence_with_different_input_gives_different_numbers(self):
        # Presence made these three indistinguishable at 100%.
        light = percent(2, 1, 200, active_seconds=60, window_seconds=60)
        medium = percent(34, 10, 4607, active_seconds=60, window_seconds=60)
        heavy = percent(120, 30, 5000, active_seconds=60, window_seconds=60)
        assert light < medium < heavy
        assert heavy == 100

    def test_the_real_production_rows_no_longer_all_read_one_hundred(self):
        # Rows taken from the deployment that prompted this, with the value
        # each one reported under the old presence model.
        rows = [
            # (keys, clicks, moves, window_seconds, old_value)
            (34, 10, 4607, 60, 100),
            (15, 11, 5179, 60, 100),
            (41, 14, 4431, 59, 100),
            (8, 1, 1391, 60, 62),
            (0, 0, 0, 18, 100),
        ]
        values = [percent(k, c, m, active_seconds=w, window_seconds=w) for k, c, m, w, _ in rows]
        assert len(set(values)) > 1, "the whole point is that they differ"
        assert values[-1] == 0, "no observed input must not report activity"
        assert all(v <= 100 for v in values)

    def test_each_input_kind_contributes_its_documented_weight(self):
        assert percent(MAX_KEYBOARD_STROKES_PER_INTERVAL, 0, 0, window_seconds=60) == round(
            KEYBOARD_WEIGHT * 100
        )
        assert percent(0, MAX_MOUSE_CLICKS_PER_INTERVAL, 0, window_seconds=60) == round(
            MOUSE_CLICK_WEIGHT * 100
        )
        assert percent(0, 0, MAX_MOUSE_MOVEMENTS_PER_INTERVAL, window_seconds=60) == round(
            MOUSE_MOVEMENT_WEIGHT * 100
        )

    def test_a_component_cannot_exceed_its_weight_however_large_the_count(self):
        # One furious minute of typing must not make the window read 400%.
        assert percent(100_000, 0, 0, window_seconds=60) == round(KEYBOARD_WEIGHT * 100)
        assert percent(100_000, 100_000, 100_000, window_seconds=60) == 100

    def test_the_result_is_always_a_valid_percentage(self):
        for args in [(-5, -5, -5), (0, 0, 0), (10**9, 10**9, 10**9)]:
            value = percent(*args, window_seconds=60)
            assert 0 <= value <= 100


class TestPartialWindows:
    """The last window of a session is whatever was sampled before the timer
    stopped. Scoring it against a full minute's thresholds would report a
    burst of work at the end of every session as near-idle."""

    def test_a_short_window_is_scored_against_its_own_length(self):
        # 12 keystrokes in 6 seconds is the same rate as 120 in a minute.
        assert percent(12, 0, 0, window_seconds=6) == round(KEYBOARD_WEIGHT * 100)

    def test_the_same_rate_scores_the_same_at_any_window_length(self):
        full = percent(60, 15, 200, window_seconds=60)
        half = percent(30, 8, 100, window_seconds=30)
        assert abs(full - half) <= 2

    def test_a_zero_length_window_is_zero_rather_than_a_division_error(self):
        assert percent(10, 10, 10, window_seconds=0) == 0


class TestEntryLevelAgreement:
    """An entry's figure must be built from the same rule as the windows it is
    made of, or the two disagree on the same screen."""

    def test_an_entry_averages_its_windows_weighted_by_their_length(self, cache):
        cache.save_activity_sample(
            time_entry_id=42, window_start="2026-09-07T10:00:00+00:00",
            window_seconds=60, active_seconds=60, activity_percent=80,
        )
        cache.save_activity_sample(
            time_entry_id=42, window_start="2026-09-07T10:01:00+00:00",
            window_seconds=30, active_seconds=30, activity_percent=20,
        )
        # (80*60 + 20*30) / 90 = 60
        assert cache.get_activity_percent_for_entry(42) == 60

    def test_an_entry_with_no_windows_is_zero(self, cache):
        assert cache.get_activity_percent_for_entry(999) == 0
