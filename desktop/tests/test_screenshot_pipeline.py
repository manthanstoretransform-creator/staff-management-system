"""The screenshot pipeline: image, cache, queue, upload and cleanup.

The invariant these exist to protect is the one that loses a user's captured
work if it breaks: **the local file is deleted only after the backend has
confirmed it stored the image.** A test that merely checked "upload was
called" would pass on an implementation that deletes first and uploads after.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from background_services.screenshot import config, image_processor, store
from background_services.screenshot.capture import RawCapture

pytest.importorskip("PIL", reason="Pillow is required to process screenshots")


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    """Point the whole data directory at a throwaway location."""
    from core import paths

    monkeypatch.setenv("MONITRA_DATA_DIR", str(tmp_path / "monitra"))
    paths.reset_cache()
    yield tmp_path / "monitra" / config.CACHE_DIR_NAME
    paths.reset_cache()


def _raw(width: int, height: int) -> RawCapture:
    """A synthetic BGRA frame of the given geometry."""
    return RawCapture(
        pixels=bytes([40, 80, 120, 255] * (width * height)),
        width=width, height=height, monitor_number=1,
    )


class TestImageProcessing:
    def test_the_output_is_always_exactly_1000x1000_webp(self):
        from PIL import Image

        for geometry in ((1920, 1080), (1366, 768), (2560, 1440), (800, 1280)):
            processed = image_processor.process(_raw(*geometry))
            assert processed is not None
            assert (processed.width, processed.height) == (1000, 1000)
            assert processed.mime_type == "image/webp"
            with Image.open(__import__("io").BytesIO(processed.data)) as image:
                assert image.size == (1000, 1000)
                assert image.format == "WEBP"

    def test_a_widescreen_desktop_is_letterboxed_rather_than_squashed(self):
        # A distorted screenshot is not a smaller screenshot, it is a wrong
        # one: the text in it stops being legible, which is the only reason
        # the image is captured at all.
        from PIL import Image

        processed = image_processor.process(_raw(1600, 800))
        with Image.open(__import__("io").BytesIO(processed.data)) as image:
            rgb = image.convert("RGB")
            # 2:1 content on a square canvas leaves a quarter of the height as
            # padding top and bottom, and the content band in the middle.
            top = rgb.getpixel((500, 20))
            middle = rgb.getpixel((500, 500))
        assert _close(top, config.PAD_COLOR)
        assert not _close(middle, config.PAD_COLOR)

    def test_compression_is_aggressive_but_stops_at_a_readable_floor(self):
        processed = image_processor.process(_raw(1920, 1080))
        assert processed.size_bytes > 0
        assert processed.quality >= config.WEBP_QUALITY_MIN
        assert processed.quality <= config.WEBP_QUALITY_START

    def test_the_real_encoded_size_is_reported_not_an_estimate(self):
        processed = image_processor.process(_raw(1280, 720))
        assert processed.size_bytes == len(processed.data)


def _close(a, b, tolerance: int = 12) -> bool:
    return all(abs(x - y) <= tolerance for x, y in zip(a, b))


class TestDailyCache:
    def test_screenshots_are_written_to_a_dated_folder_under_the_data_dir(self, cache_root):
        from datetime import datetime

        when = datetime(2026, 9, 7, 10, 6, 24)
        path = store.write_screenshot("abc-123", b"RIFFxxxxWEBP", when)
        assert path is not None
        assert path.parent.name == "2026-09-07"
        assert path.parent.parent == cache_root
        assert path.read_bytes() == b"RIFFxxxxWEBP"

    def test_a_new_day_gets_its_own_folder_without_a_restart(self, cache_root):
        from datetime import datetime

        store.write_screenshot("a", b"one", datetime(2026, 9, 7, 23, 58))
        store.write_screenshot("b", b"two", datetime(2026, 9, 8, 0, 2))
        assert {p.name for p in cache_root.iterdir()} == {"2026-09-07", "2026-09-08"}

    def test_nothing_is_written_outside_the_monitra_data_directory(self, cache_root):
        path = store.write_screenshot("abc", b"data")
        assert str(cache_root) in str(path)
        for forbidden in ("Desktop", "Documents", "Downloads"):
            assert forbidden not in str(path)

    def test_a_partial_write_never_leaves_a_readable_file(self, cache_root):
        # The file is written under a .part name and renamed, so a crash
        # mid-write cannot leave a truncated image the uploader would send.
        path = store.write_screenshot("abc", b"data")
        assert list(path.parent.glob("*.part")) == []

    def test_a_day_folder_is_removed_only_once_it_is_empty(self, cache_root):
        from datetime import datetime

        when = datetime(2026, 9, 7, 12, 0)
        path = store.write_screenshot("abc", b"data", when)
        store.prune_empty_day_folders([])
        assert path.parent.exists(), "a folder holding a file must not be removed"

        store.delete_screenshot(str(path))
        store.prune_empty_day_folders([])
        assert not path.parent.exists()

    def test_a_folder_holding_unsynced_work_is_protected_from_pruning(self, cache_root):
        from datetime import datetime

        path = store.write_screenshot("abc", b"data", datetime(2026, 9, 7, 12, 0))
        # The file is gone from disk but the queue still references it, so the
        # folder is not ours to remove yet.
        os.remove(path)
        store.prune_empty_day_folders([str(path)])
        assert path.parent.exists()


class TestQueue:
    """The durable SQLite queue behind every capture."""

    def _queue(self, cache, **overrides):
        payload = dict(
            client_screenshot_id="uuid-1",
            local_file_path="/tmp/ss.webp",
            captured_at="2026-09-07T10:06:24+00:00",
            window_start="2026-09-07T10:00:00+00:00",
            width=1000, height=1000, file_size_bytes=54321,
            time_entry_id=100, monitor_number=1,
        )
        payload.update(overrides)
        return cache.save_screenshot(**payload)

    def test_a_capture_is_queued_before_anything_is_uploaded(self, cache):
        self._queue(cache)
        pending = cache.get_pending_screenshots()
        assert len(pending) == 1
        assert pending[0]["client_screenshot_id"] == "uuid-1"
        assert pending[0]["file_size_bytes"] == 54321

    def test_the_same_capture_cannot_be_queued_twice(self, cache):
        self._queue(cache)
        self._queue(cache, local_file_path="/tmp/other.webp")
        assert len(cache.get_pending_screenshots()) == 1

    def test_a_capture_with_no_entry_id_waits_to_be_attributed(self, cache):
        # A capture taken before the backend issued an entry id has nothing to
        # upload against; uploading it against `None` would be rejected.
        self._queue(cache, time_entry_id=None)
        assert cache.get_pending_screenshots() == []

        bound = cache.bind_screenshots_to_entry("2026-09-07T10:00:00+00:00", 555)
        assert bound == 1
        assert cache.get_pending_screenshots()[0]["time_entry_id"] == 555

    def test_only_captures_from_the_matching_window_are_adopted(self, cache):
        self._queue(cache, client_screenshot_id="a", time_entry_id=None,
                    window_start="2026-09-07T10:00:00+00:00")
        self._queue(cache, client_screenshot_id="b", time_entry_id=None,
                    window_start="2026-09-07T09:00:00+00:00")
        assert cache.bind_screenshots_to_entry("2026-09-07T10:00:00+00:00", 555) == 1

    def test_completing_a_screenshot_returns_the_file_to_delete(self, cache):
        self._queue(cache)
        path = cache.complete_screenshot("uuid-1")
        assert path == "/tmp/ss.webp"
        assert cache.get_pending_screenshots() == []

    def test_a_failure_schedules_a_backed_off_retry_rather_than_dropping_it(self, cache):
        self._queue(cache)
        assert cache.fail_screenshot("uuid-1", "network down") is True
        # Backed off, so it is not immediately re-attempted.
        assert cache.get_pending_screenshots() == []
        assert cache.count_screenshots_by_status() == {"pending": 1}

    def test_an_exhausted_screenshot_is_parked_but_its_file_is_kept(self, cache):
        self._queue(cache)
        for _ in range(4):
            cache.fail_screenshot("uuid-1", "still down", max_retries=3)
        assert cache.count_screenshots_by_status() == {"failed": 1}
        # Still referenced, so the file is protected from cleanup: discarding
        # captured evidence because the network was down for a day is not an
        # acceptable outcome.
        assert cache.get_screenshot_backlog_paths() == ["/tmp/ss.webp"]

    def test_an_exhausted_screenshot_is_reclaimed_at_the_next_launch(self, cache):
        # An exhausted screenshot means the backend was rejecting uploads for
        # hours — a misconfiguration someone has since fixed. Its file is still
        # on disk and the capture is still valid, so a launch retries it with a
        # fresh budget instead of discarding real evidence.
        self._queue(cache)
        for _ in range(4):
            cache.fail_screenshot("uuid-1", "storage not configured", max_retries=3)
        assert cache.count_screenshots_by_status() == {"failed": 1}

        assert cache.requeue_failed_screenshots() == 1
        pending = cache.get_pending_screenshots()
        assert len(pending) == 1
        assert pending[0]["retry_count"] == 0, "a reclaimed screenshot gets a full budget"

    def test_an_upload_interrupted_by_a_crash_is_resumed_on_the_next_run(self, cache):
        self._queue(cache)
        cache.mark_screenshots_uploading(["uuid-1"])
        assert cache.get_pending_screenshots() == []  # claimed

        # The process dies here. The next launch releases the claim.
        assert cache.reset_uploading_screenshots() == 1
        assert len(cache.get_pending_screenshots()) == 1

    def test_the_backlog_lists_every_file_that_has_not_landed(self, cache):
        self._queue(cache, client_screenshot_id="a", local_file_path="/tmp/a.webp")
        self._queue(cache, client_screenshot_id="b", local_file_path="/tmp/b.webp")
        cache.mark_screenshots_uploading(["b"])
        assert sorted(cache.get_screenshot_backlog_paths()) == ["/tmp/a.webp", "/tmp/b.webp"]


class TestUpload:
    """SyncService is the only uploader, and the only thing that deletes."""

    @pytest.fixture
    def sync(self, cache, tmp_path, monkeypatch):
        from types import SimpleNamespace

        from background_services.sync.sync_service import SyncService

        runtime = SimpleNamespace(storage=cache.storage, queue_floor_generation=0)
        entries = SimpleNamespace(upload_screenshot=None)
        service = SyncService(runtime, cache, entries, SimpleNamespace())
        return service, entries

    def _capture(self, cache, tmp_path, name="uuid-1"):
        path = tmp_path / f"{name}.webp"
        path.write_bytes(b"RIFF0000WEBPimage-bytes")
        cache.save_screenshot(
            client_screenshot_id=name, local_file_path=str(path),
            captured_at="2026-09-07T10:06:24+00:00",
            window_start="2026-09-07T10:00:00+00:00",
            width=1000, height=1000, file_size_bytes=path.stat().st_size,
            time_entry_id=100,
        )
        return path

    def test_the_local_file_is_deleted_only_after_a_confirmed_upload(self, sync, cache, tmp_path):
        service, entries = sync
        path = self._capture(cache, tmp_path)
        seen = {}

        def upload(entry_id, image, file_name, metadata, timeout=None):
            # The file must still exist at the moment of upload — an
            # implementation that deleted first would fail here.
            seen["existed_during_upload"] = path.exists()
            seen["entry_id"] = entry_id
            seen["metadata"] = metadata
            seen["bytes"] = image
            return {"success": True}

        entries.upload_screenshot = upload
        service._sync_screenshots()

        assert seen["existed_during_upload"] is True
        assert seen["entry_id"] == 100
        assert seen["bytes"] == b"RIFF0000WEBPimage-bytes"
        assert seen["metadata"]["client_screenshot_id"] == "uuid-1"
        assert not path.exists(), "an uploaded screenshot must be removed locally"
        assert cache.count_screenshots_by_status() == {}

    def test_a_failed_upload_keeps_both_the_file_and_the_queue_row(self, sync, cache, tmp_path):
        from app.api.exceptions import ApiError

        service, entries = sync
        path = self._capture(cache, tmp_path)

        def upload(*args, **kwargs):
            raise ApiError("Network connection error")

        entries.upload_screenshot = upload
        service._sync_screenshots()

        assert path.exists(), "an unsent screenshot must survive to be retried"
        assert cache.count_screenshots_by_status() == {"pending": 1}

    def test_going_offline_and_coming_back_uploads_the_backlog(self, sync, cache, tmp_path):
        from app.api.exceptions import ApiError

        service, entries = sync
        paths = [self._capture(cache, tmp_path, f"uuid-{i}") for i in range(3)]

        entries.upload_screenshot = lambda *a, **k: (_ for _ in ()).throw(ApiError("offline"))
        service._sync_screenshots()
        assert all(p.exists() for p in paths)

        # Back online. The backoff has not elapsed, so the rows are not yet
        # due; clearing it is what a passing retry timer does.
        cache.storage.execute("UPDATE pending_screenshots SET next_retry_at = 0")
        entries.upload_screenshot = lambda *a, **k: {"success": True}
        service._sync_screenshots()

        assert not any(p.exists() for p in paths)
        assert cache.count_screenshots_by_status() == {}

    def test_a_permanently_rejected_screenshot_is_dropped_rather_than_retried(self, sync, cache, tmp_path):
        from app.api.exceptions import ApiError

        service, entries = sync
        path = self._capture(cache, tmp_path)

        def upload(*args, **kwargs):
            raise ApiError("gone", status_code=404)

        entries.upload_screenshot = upload
        service._sync_screenshots()

        assert not path.exists()
        assert cache.count_screenshots_by_status() == {}

    def test_an_expired_session_holds_the_queue_instead_of_burning_retries(self, sync, cache, tmp_path):
        from app.api.exceptions import ApiError

        service, entries = sync
        path = self._capture(cache, tmp_path)

        def upload(*args, **kwargs):
            raise ApiError("Session expired", status_code=401)

        entries.upload_screenshot = upload
        service._sync_screenshots()

        assert path.exists()
        assert service._should_hold() == "awaiting re-authentication"

    def test_a_screenshot_whose_file_vanished_is_dropped_not_retried_forever(self, sync, cache, tmp_path):
        service, entries = sync
        path = self._capture(cache, tmp_path)
        path.unlink()
        entries.upload_screenshot = lambda *a, **k: pytest.fail("nothing to upload")

        service._sync_screenshots()
        assert cache.count_screenshots_by_status() == {}

    def test_the_upload_carries_the_idempotency_key_so_a_retry_cannot_duplicate(self, sync, cache, tmp_path):
        service, entries = sync
        self._capture(cache, tmp_path, "uuid-abc")
        captured = {}
        entries.upload_screenshot = lambda e, i, n, m, t=None: captured.update(m) or {"ok": True}

        service._sync_screenshots()
        assert captured["client_screenshot_id"] == "uuid-abc"
        assert captured["captured_at"] == "2026-09-07T10:06:24+00:00"
        assert captured["width"] == 1000 and captured["height"] == 1000


class TestTimerIntegration:
    """Capture happens while time is tracked, and at no other moment."""

    #: A fixed instant just after a window boundary. The clock is frozen for
    #: these tests rather than read: the service replans whenever the window
    #: index changes, so a test that forces a capture time and then ticks is
    #: racing the wall clock — and it lost, intermittently, whenever the suite
    #: happened to straddle a boundary.
    NOW = 1_757_000_400.0

    @pytest.fixture
    def service(self, qapp, cache, cache_root, monkeypatch):
        from types import SimpleNamespace

        from background_services.screenshot import screenshot_service as module

        grabs = {"count": 0}

        def fake_grab():
            grabs["count"] += 1
            return _raw(640, 480)

        monkeypatch.setattr(module.capture, "supported", lambda: True)
        monkeypatch.setattr(module.capture, "capture_primary_monitor", fake_grab)
        # Only `time.time()` is used here, so a stub with that one name keeps
        # the freeze local to this module instead of patching the clock
        # process-wide.
        monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: self.NOW))

        runtime = SimpleNamespace(
            storage=cache.storage,
            timer=SimpleNamespace(active_session=lambda: {"entry_id": 100}),
            sync=SimpleNamespace(wake=lambda: None),
        )
        return module.ScreenshotService(runtime, cache), grabs

    def _fire_now(self, svc):
        """Make the next tick take a capture, with no dependence on real time."""
        svc.tick()                       # plan the (frozen) current window
        svc._planned_times = [self.NOW]  # due exactly now
        svc.tick()

    def test_a_stopped_timer_captures_nothing(self, service, cache):
        svc, grabs = service
        for _ in range(5):
            svc.tick()
        assert grabs["count"] == 0
        assert cache.count_screenshots_by_status() == {}

    def test_starting_the_timer_captures_within_the_window_and_queues_it(self, service, cache):
        svc, grabs = service
        svc.start_tracker({"entry_id": 100})
        self._fire_now(svc)

        assert grabs["count"] == 1
        pending = cache.get_pending_screenshots()
        assert len(pending) == 1
        assert pending[0]["time_entry_id"] == 100
        assert pending[0]["width"] == 1000 and pending[0]["height"] == 1000
        assert Path(pending[0]["local_file_path"]).exists()

    def test_stopping_the_timer_stops_capture_immediately(self, service, cache):
        svc, grabs = service
        svc.start_tracker({"entry_id": 100})
        svc.stop_tracker()
        svc._planned_times = [self.NOW]
        for _ in range(5):
            svc.tick()
        assert grabs["count"] == 0

    def test_a_window_spends_its_budget_once_even_across_a_restart(self, service, cache):
        # The budget lives in app_state, not in the service, precisely so a
        # relaunch four minutes into a window cannot take a second screenshot
        # the window has already paid for.
        svc, grabs = service
        svc.start_tracker({"entry_id": 100})
        self._fire_now(svc)
        assert grabs["count"] == 1

        # A fresh service on the same cache is the restart.
        restarted = type(svc)(svc.runtime, cache)
        restarted.start_tracker({"entry_id": 100})
        for _ in range(3):
            restarted.tick()
        assert grabs["count"] == 1

    def test_a_capture_taken_before_the_entry_id_arrives_is_attributed_later(self, service, cache):
        svc, _ = service
        svc.runtime.timer.active_session = lambda: {}
        svc.start_tracker({"entry_id": None})
        self._fire_now(svc)

        # Queued but not yet uploadable.
        assert cache.get_pending_screenshots() == []
        svc.bind_entry_id(777)
        pending = cache.get_pending_screenshots()
        assert len(pending) == 1 and pending[0]["time_entry_id"] == 777

    def test_a_machine_that_cannot_capture_queues_nothing_and_says_so(self, service, cache, monkeypatch):
        # No placeholder image, exactly as there is no placeholder domain in
        # the URL tracker. An honest absence beats fabricated evidence.
        svc, grabs = service
        monkeypatch.setattr(
            "background_services.screenshot.screenshot_service.capture.supported",
            lambda: False,
        )
        reasons = []
        svc.capture_unavailable.connect(reasons.append)
        svc.start_tracker({"entry_id": 100})
        svc._planned_times = [self.NOW]
        svc.tick()

        assert grabs["count"] == 0
        assert cache.count_screenshots_by_status() == {}
        assert reasons and "unavailable" in reasons[0]

    def test_the_loop_sleeps_until_the_next_capture_rather_than_polling(self, service):
        # A per-second poll of an idle window is the shape of defect that
        # produced the historical worker storm; the tick returns the real
        # interval instead.
        svc, _ = service
        svc.start_tracker({"entry_id": 100})
        delay = svc.tick()
        assert delay is not None and delay >= 250
