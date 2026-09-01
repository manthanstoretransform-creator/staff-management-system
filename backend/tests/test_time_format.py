"""
Tests for the one authoritative duration formatter and the IST timestamp
strategy. These are the guarantees the rest of the time module leans on: if
format_hms ever wraps at 24 hours, or ist_day_start_utc drifts off the real
Asia/Kolkata offset, every tracked-time display in the product goes wrong at
once and nothing else would catch it.
"""
import unittest
from datetime import date, datetime, timedelta, timezone

from app.core.time_format import (
    IST,
    elapsed_seconds,
    format_hms,
    ist_day_end_utc,
    ist_day_start_utc,
    to_ist,
)


class FormatHmsTests(unittest.TestCase):
    def test_boundaries(self):
        cases = {
            0: "00:00:00",
            1: "00:00:01",
            59: "00:00:59",
            60: "00:01:00",
            61: "00:01:01",
            3599: "00:59:59",
            3600: "01:00:00",
            3661: "01:01:01",
            86399: "23:59:59",
            86400: "24:00:00",
            90061: "25:01:01",
            20742: "05:45:42",
        }
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(format_hms(seconds), expected)

    def test_durations_do_not_wrap_past_24_hours(self):
        # 100:05:09 must stay 100 hours, not roll over into a clock time.
        self.assertEqual(format_hms(360309), "100:05:09")
        self.assertEqual(format_hms(1000 * 3600), "1000:00:00")

    def test_no_hidden_rounding(self):
        # 5h59m59s must never be presented as 06:00:00.
        self.assertEqual(format_hms(5 * 3600 + 59 * 60 + 59), "05:59:59")

    def test_negative_and_none_clamp_to_zero(self):
        self.assertEqual(format_hms(-1), "00:00:00")
        self.assertEqual(format_hms(None), "00:00:00")

    def test_float_seconds_truncate_rather_than_round_up(self):
        self.assertEqual(format_hms(59.9), "00:00:59")


class IstTimestampTests(unittest.TestCase):
    def test_offset_is_five_thirty(self):
        moment = datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)
        self.assertEqual(to_ist(moment).strftime("%Y-%m-%d %H:%M:%S"), "2026-09-01 11:00:00")

    def test_naive_input_is_treated_as_utc(self):
        naive = datetime(2026, 9, 1, 5, 30)
        aware = datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)
        self.assertEqual(to_ist(naive), to_ist(aware))

    def test_date_rollover_around_utc_boundaries(self):
        cases = {
            datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc): "2026-09-01 05:30:00",
            datetime(2026, 9, 1, 5, 29, tzinfo=timezone.utc): "2026-09-01 10:59:00",
            datetime(2026, 9, 1, 18, 29, tzinfo=timezone.utc): "2026-09-01 23:59:00",
            # Crosses into the next IST day while still 1 Sep in UTC.
            datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc): "2026-09-02 00:00:00",
        }
        for moment, expected in cases.items():
            with self.subTest(moment=moment):
                self.assertEqual(to_ist(moment).strftime("%Y-%m-%d %H:%M:%S"), expected)

    def test_no_double_conversion(self):
        moment = datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)
        self.assertEqual(to_ist(to_ist(moment)), to_ist(moment))

    def test_ist_day_bounds_are_utc_instants(self):
        start = ist_day_start_utc(date(2026, 9, 1))
        end = ist_day_end_utc(date(2026, 9, 1))
        # 00:00 IST on 1 Sep is 18:30 UTC on 31 Aug.
        self.assertEqual(start, datetime(2026, 8, 31, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(end - start, timedelta(hours=24))

    def test_ist_day_bounds_bracket_early_morning_ist_work(self):
        # 00:30 IST on 1 Sep -- the case the old UTC-day bounds mis-filed
        # under 31 August.
        worked_at = datetime(2026, 9, 1, 0, 30, tzinfo=IST)
        self.assertTrue(ist_day_start_utc(date(2026, 9, 1)) <= worked_at < ist_day_end_utc(date(2026, 9, 1)))


class ElapsedSecondsTests(unittest.TestCase):
    def test_stopped_entry_uses_both_timestamps(self):
        start = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 42, 18, tzinfo=timezone.utc)
        self.assertEqual(elapsed_seconds(start, end), 9738)
        self.assertEqual(format_hms(elapsed_seconds(start, end)), "02:42:18")

    def test_running_entry_measures_against_now(self):
        start = datetime.now(timezone.utc) - timedelta(hours=2, minutes=15, seconds=27)
        self.assertAlmostEqual(elapsed_seconds(start), 8127, delta=2)

    def test_duration_is_timezone_independent(self):
        start_utc = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
        end_utc = datetime(2026, 9, 1, 11, 30, tzinfo=timezone.utc)
        self.assertEqual(
            elapsed_seconds(start_utc, end_utc),
            elapsed_seconds(to_ist(start_utc), to_ist(end_utc)),
        )

    def test_backwards_clock_never_reports_negative(self):
        start = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        self.assertEqual(elapsed_seconds(start, end), 0)


class ExactAggregationTests(unittest.TestCase):
    def test_totals_sum_seconds_not_rounded_hours(self):
        entries = [3600, 1800, 125]
        self.assertEqual(format_hms(sum(entries)), "01:32:05")

    def test_multiple_entries_example(self):
        entries = [
            1 * 3600 + 20 * 60 + 15,
            45 * 60 + 30,
            2 * 3600 + 10 * 60 + 5,
        ]
        self.assertEqual(format_hms(sum(entries)), "04:15:50")


class TimeEntryReadContractTests(unittest.TestCase):
    """A running entry must report its current duration, not wait to be stopped."""

    @staticmethod
    def _entry(**overrides):
        from types import SimpleNamespace

        base = dict(
            id=1, organization_id=1, user_id=1, project_id=1, task_id=1,
            start_time=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
            end_time=None, total_seconds=0, status="running", is_manual=False,
            is_billable=False, description=None,
            created_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_running_entry_reports_current_elapsed(self):
        from app.schemas.time_entry import TimeEntryRead

        start = datetime.now(timezone.utc) - timedelta(hours=2, minutes=17, seconds=18)
        read = TimeEntryRead.model_validate(self._entry(start_time=start))
        self.assertTrue(read.is_running)
        self.assertAlmostEqual(read.elapsed_seconds, 8238, delta=2)
        self.assertRegex(read.elapsed_time, r"^02:17:1[6-9]$")

    def test_stopped_entry_reports_persisted_duration(self):
        from app.schemas.time_entry import TimeEntryRead

        read = TimeEntryRead.model_validate(self._entry(
            end_time=datetime(2026, 9, 1, 11, 42, 18, tzinfo=timezone.utc),
            total_seconds=9738,
            status="stopped",
        ))
        self.assertFalse(read.is_running)
        self.assertEqual(read.elapsed_seconds, 9738)
        self.assertEqual(read.elapsed_time, "02:42:18")


if __name__ == "__main__":
    unittest.main()
