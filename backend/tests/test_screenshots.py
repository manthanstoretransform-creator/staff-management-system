"""Screenshot upload, viewing and timeline grouping.

Unit tests in the style of the rest of this suite: the session, the
repositories and Google Drive are mocked, so the rules are exercised without a
database and without a network. What they pin down is the part a client must
not be trusted with — whose entry a screenshot may be attached to, whether a
retry can store the image twice, whether a rejected image can reach storage,
and whether a window's activity percentage describes that window alone.
"""

import io
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.time_entry import TimeEntry
from app.models.time_entry_screenshot import TimeEntryScreenshot
from app.models.user import User
from app.services.time_entry_screenshot import TimeEntryScreenshotService

SVC = "app.services.time_entry_screenshot"

T0 = datetime(2026, 9, 7, 4, 30, tzinfo=timezone.utc)  # 10:00 IST


def _user(**overrides) -> User:
    defaults = dict(id=1, organization_id=10, permissions={}, role_name="employee")
    defaults.update(overrides)
    return User(**defaults)


def _entry(**overrides) -> TimeEntry:
    defaults = dict(
        id=100, organization_id=10, user_id=1, project_id=5, task_id=7,
        start_time=T0, end_time=None, total_seconds=0, status="running",
        is_manual=False, is_billable=False,
    )
    defaults.update(overrides)
    return TimeEntry(**defaults)


def _webp(width: int = 1000, height: int = 1000) -> bytes:
    """A real WebP of the given size, so the format and dimension checks see
    genuine bytes rather than a hand-built header."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buffer, format="WEBP", quality=50)
    return buffer.getvalue()


class ValidationTests(unittest.TestCase):
    """An upload that is not what it claims must never reach storage."""

    def _upload(self, content, content_type="image/webp"):
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry()), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_client_id", return_value=None), \
             patch(f"{SVC}.drive_service") as drive:
            drive.configured = True
            try:
                TimeEntryScreenshotService.upload_screenshot(
                    db=db, time_entry_id=100, content=content,
                    content_type=content_type, client_screenshot_id="abc",
                    current_user=_user(),
                )
            finally:
                self.drive = drive

    def test_a_non_webp_body_is_rejected_before_anything_is_stored(self):
        with self.assertRaises(HTTPException) as raised:
            self._upload(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        self.assertEqual(raised.exception.status_code, 422)
        self.drive.upload_file.assert_not_called()

    def test_an_empty_body_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            self._upload(b"")
        self.assertEqual(raised.exception.status_code, 400)

    def test_a_content_type_other_than_webp_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            self._upload(_webp(), content_type="image/png")
        self.assertEqual(raised.exception.status_code, 422)

    def test_an_image_of_the_wrong_geometry_is_rejected(self):
        # The dimensions are read from the file, not from the form fields, so
        # a client cannot claim 1000x1000 and store something else.
        with self.assertRaises(HTTPException) as raised:
            self._upload(_webp(800, 600))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("1000x1000", raised.exception.detail)

    def test_an_oversized_body_is_rejected(self):
        with patch(f"{SVC}.settings") as settings:
            settings.SCREENSHOT_MAX_UPLOAD_BYTES = 100
            settings.SCREENSHOT_WINDOW_MINUTES = 10
            with self.assertRaises(HTTPException) as raised:
                self._upload(_webp())
        self.assertEqual(raised.exception.status_code, 413)


class AuthorizationTests(unittest.TestCase):
    def test_a_screenshot_cannot_be_attached_to_another_users_entry(self):
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry(user_id=2)):
            with self.assertRaises(HTTPException) as raised:
                TimeEntryScreenshotService.upload_screenshot(
                    db=db, time_entry_id=100, content=_webp(),
                    content_type="image/webp", client_screenshot_id="abc",
                    current_user=_user(id=1),
                )
        self.assertEqual(raised.exception.status_code, 403)

    def test_an_entry_in_another_organization_reads_as_absent(self):
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry(organization_id=99)):
            with self.assertRaises(HTTPException) as raised:
                TimeEntryScreenshotService.upload_screenshot(
                    db=db, time_entry_id=100, content=_webp(),
                    content_type="image/webp", client_screenshot_id="abc",
                    current_user=_user(),
                )
        self.assertEqual(raised.exception.status_code, 404)

    def test_an_employee_may_not_view_someone_elses_screenshot_and_is_told_404(self):
        # 403 would confirm the id exists, which is itself information about
        # another person's day.
        record = TimeEntryScreenshot(
            id=7, organization_id=10, time_entry_id=100, captured_at=T0,
            file_path="p", monitor_number=1, google_drive_file_id="d",
        )
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_id", return_value=record), \
             patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry(user_id=2)):
            with self.assertRaises(HTTPException) as raised:
                TimeEntryScreenshotService.get_screenshot_bytes(db, 7, _user(id=1))
        self.assertEqual(raised.exception.status_code, 404)

    def test_the_owner_may_view_their_own_screenshot(self):
        record = TimeEntryScreenshot(
            id=7, organization_id=10, time_entry_id=100, captured_at=T0,
            file_path="p", monitor_number=1, google_drive_file_id="drive-1",
            mime_type="image/webp", file_name="s.webp",
        )
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_id", return_value=record), \
             patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry(user_id=1)), \
             patch(f"{SVC}.drive_service") as drive:
            drive.download_file.return_value = b"bytes"
            content, mime, name = TimeEntryScreenshotService.get_screenshot_bytes(
                db, 7, _user(id=1)
            )
        self.assertEqual(content, b"bytes")
        self.assertEqual(mime, "image/webp")
        drive.download_file.assert_called_once_with("drive-1")


class IdempotencyTests(unittest.TestCase):
    """A retry after a lost response must not create a second Drive file."""

    def test_a_repeated_client_screenshot_id_returns_the_existing_record(self):
        existing = TimeEntryScreenshot(
            id=42, organization_id=10, time_entry_id=100, captured_at=T0,
            file_path="p", monitor_number=1, client_screenshot_id="abc",
        )
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry()), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_client_id", return_value=existing), \
             patch(f"{SVC}.drive_service") as drive:
            record, duplicate = TimeEntryScreenshotService.upload_screenshot(
                db=db, time_entry_id=100, content=_webp(),
                content_type="image/webp", client_screenshot_id="abc",
                current_user=_user(),
            )
        self.assertTrue(duplicate)
        self.assertEqual(record.id, 42)
        # Nothing was uploaded, and the image was not even decoded: the
        # duplicate check runs before any work is done.
        drive.upload_file.assert_not_called()

    def test_a_missing_client_screenshot_id_is_refused(self):
        with self.assertRaises(HTTPException) as raised:
            TimeEntryScreenshotService.upload_screenshot(
                db=MagicMock(), time_entry_id=100, content=_webp(),
                content_type="image/webp", client_screenshot_id="",
                current_user=_user(),
            )
        self.assertEqual(raised.exception.status_code, 422)

    def test_a_row_that_loses_the_unique_index_race_discards_its_own_drive_file(self):
        from sqlalchemy.exc import IntegrityError

        winner = TimeEntryScreenshot(
            id=42, organization_id=10, time_entry_id=100, captured_at=T0,
            file_path="p", monitor_number=1, client_screenshot_id="abc",
        )
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry()), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_client_id",
                   side_effect=[None, winner]), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.create_uploaded",
                   side_effect=IntegrityError("x", {}, Exception())), \
             patch(f"{SVC}.drive_service") as drive:
            drive.configured = True
            drive.ensure_screenshot_folder.return_value = ("folder-1", "2026/September/User_1/2026-09-07")
            drive.upload_file.return_value = "orphan-file"
            record, duplicate = TimeEntryScreenshotService.upload_screenshot(
                db=db, time_entry_id=100, content=_webp(),
                content_type="image/webp", client_screenshot_id="abc",
                current_user=_user(),
            )
        self.assertTrue(duplicate)
        self.assertEqual(record.id, 42)
        drive.delete_file.assert_called_once_with("orphan-file")


class StorageTests(unittest.TestCase):
    def test_an_unconfigured_backend_refuses_rather_than_pretending_to_store(self):
        # The desktop deletes its local copy only on success, so accepting an
        # upload we cannot store would destroy the only copy of the capture.
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry()), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_client_id", return_value=None), \
             patch(f"{SVC}.drive_service") as drive:
            drive.configured = False
            with self.assertRaises(HTTPException) as raised:
                TimeEntryScreenshotService.upload_screenshot(
                    db=db, time_entry_id=100, content=_webp(),
                    content_type="image/webp", client_screenshot_id="abc",
                    current_user=_user(),
                )
        self.assertEqual(raised.exception.status_code, 503)

    def test_a_stored_screenshot_lands_in_the_year_month_user_date_folder(self):
        db = MagicMock()
        captured = []

        def create_uploaded(**kwargs):
            captured.append(kwargs)
            return TimeEntryScreenshot(id=1, organization_id=10, time_entry_id=100,
                                       captured_at=T0, file_path=kwargs["file_path"],
                                       monitor_number=1)

        with patch(f"{SVC}.TimeEntryRepository.get_by_id", return_value=_entry()), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.get_by_client_id", return_value=None), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.create_uploaded", side_effect=create_uploaded), \
             patch(f"{SVC}.drive_service") as drive:
            drive.configured = True
            drive.ensure_screenshot_folder.return_value = (
                "folder-1", "2026/September/User_1/2026-09-07"
            )
            drive.upload_file.return_value = "file-1"
            _, duplicate = TimeEntryScreenshotService.upload_screenshot(
                db=db, time_entry_id=100, content=_webp(),
                content_type="image/webp", client_screenshot_id="abc",
                current_user=_user(), captured_at=T0,
            )

        self.assertFalse(duplicate)
        drive.ensure_screenshot_folder.assert_called_once()
        kwargs = drive.ensure_screenshot_folder.call_args.kwargs
        # The folder is keyed on the *entry's* user, not on the caller's claim.
        self.assertEqual(kwargs["user_id"], 1)
        self.assertEqual(kwargs["captured_on"].isoformat(), "2026-09-07")
        self.assertTrue(
            captured[0]["file_path"].startswith("2026/September/User_1/2026-09-07/")
        )
        self.assertEqual(captured[0]["google_drive_file_id"], "file-1")
        self.assertEqual(captured[0]["width"], 1000)
        self.assertEqual(captured[0]["height"], 1000)


class TimelineTests(unittest.TestCase):
    """A window's activity percentage must describe that window alone."""

    def _timeline(self, screenshots, activity, user=None):
        db = MagicMock()
        with patch(f"{SVC}.TimeEntryScreenshotRepository.list_screenshots", return_value=screenshots), \
             patch(f"{SVC}.TimeEntryScreenshotRepository.get_activity_totals_in_range", return_value=activity):
            return TimeEntryScreenshotService.get_timeline(
                db=db, current_user=user or _user(), target_date=T0.date()
            )

    @staticmethod
    def _shot(offset_seconds: int, shot_id: int = 1) -> TimeEntryScreenshot:
        return TimeEntryScreenshot(
            id=shot_id, organization_id=10, time_entry_id=100,
            captured_at=T0 + timedelta(seconds=offset_seconds),
            file_path="p", monitor_number=1, width=1000, height=1000,
            file_size_bytes=1234,
        )

    def test_captures_ten_minutes_apart_land_in_separate_windows(self):
        _, windows = self._timeline([self._shot(120, 1), self._shot(700, 2)], [])
        self.assertEqual(len(windows), 2)
        self.assertEqual([w["screenshot_count"] for w in windows], [1, 1])
        gap = windows[1]["window_start"] - windows[0]["window_start"]
        self.assertEqual(gap, timedelta(minutes=10))

    def test_several_captures_in_one_window_are_grouped_and_counted(self):
        # What a future SCREENSHOTS_PER_WINDOW of 3 produces. The grouping is
        # by timestamp, so nothing here assumes a window holds only one.
        _, windows = self._timeline(
            [self._shot(60, 1), self._shot(300, 2), self._shot(540, 3)], []
        )
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["screenshot_count"], 3)
        self.assertEqual([s["id"] for s in windows[0]["screenshots"]], [1, 2, 3])

    def test_each_window_carries_only_its_own_activity(self):
        activity = [
            # First window: 60s at 20%, 60s at 40% -> 30%.
            (T0 + timedelta(seconds=10), 20, 60),
            (T0 + timedelta(seconds=70), 40, 60),
            # Second window: a single 60s window at 90%.
            (T0 + timedelta(seconds=610), 90, 60),
        ]
        _, windows = self._timeline([self._shot(60, 1), self._shot(700, 2)], activity)
        self.assertEqual([w["activity_percentage"] for w in windows], [30, 90])

    def test_activity_is_weighted_by_the_duration_actually_measured(self):
        # A 12-second tail window at 100% must not count as much as a full one.
        activity = [
            (T0 + timedelta(seconds=10), 0, 60),
            (T0 + timedelta(seconds=80), 100, 12),
        ]
        _, windows = self._timeline([self._shot(60)], activity)
        self.assertEqual(windows[0]["activity_percentage"], 17)
        self.assertEqual(windows[0]["activity_measured_seconds"], 72)

    def test_an_unmeasured_window_reports_zero_measured_seconds(self):
        # 0% and "nothing was measured" are different facts, and a caller has
        # to be able to tell them apart rather than being shown a fabricated
        # number for a window nothing was recorded in.
        _, windows = self._timeline([self._shot(60)], [])
        self.assertEqual(windows[0]["activity_percentage"], 0)
        self.assertEqual(windows[0]["activity_measured_seconds"], 0)

    def test_every_screenshot_is_served_through_the_backend_not_google_drive(self):
        _, windows = self._timeline([self._shot(60, 5)], [])
        url = windows[0]["screenshots"][0]["view_url"]
        self.assertEqual(url, "/time-entry-screenshots/5/view")
        self.assertNotIn("google", url)

    def test_an_employee_may_not_read_another_members_timeline(self):
        db = MagicMock()
        with self.assertRaises(HTTPException) as raised:
            TimeEntryScreenshotService.get_timeline(
                db=db, current_user=_user(id=1, role_name="employee"), user_id=2
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_a_leader_may_not_read_outside_their_visible_team(self):
        db = MagicMock()
        with patch(f"{SVC}.visible_member_ids", return_value={1, 3}):
            with self.assertRaises(HTTPException) as raised:
                TimeEntryScreenshotService.get_timeline(
                    db=db, current_user=_user(id=1, role_name="leader"), user_id=9
                )
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
