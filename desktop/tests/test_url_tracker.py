import unittest
from unittest.mock import MagicMock, patch
import time
from datetime import datetime, timezone

from tracking.browsers import (
    ChromeAdapter, EdgeAdapter, FirefoxAdapter, BrowserManager, get_browser_manager
)
from tracking.browsers.manager import normalize_domain_and_url
from background_services.activity.url_usage_service import UrlUsageService


class TestBrowserAdapters(unittest.TestCase):
    def test_chrome_adapter_detection(self):
        adapter = ChromeAdapter()
        self.assertTrue(adapter.is_supported_app("chrome.exe"))
        self.assertTrue(adapter.is_supported_app("brave.exe"))
        self.assertFalse(adapter.is_supported_app("code.exe"))

    def test_edge_adapter_detection(self):
        adapter = EdgeAdapter()
        self.assertTrue(adapter.is_supported_app("msedge.exe"))
        self.assertFalse(adapter.is_supported_app("firefox.exe"))

    def test_firefox_adapter_detection(self):
        adapter = FirefoxAdapter()
        self.assertTrue(adapter.is_supported_app("firefox.exe"))
        self.assertFalse(adapter.is_supported_app("chrome.exe"))

    def test_browser_manager_routing(self):
        manager = get_browser_manager()
        self.assertTrue(manager.is_browser_app("chrome.exe"))
        self.assertTrue(manager.is_browser_app("msedge.exe"))
        self.assertTrue(manager.is_browser_app("firefox.exe"))
        self.assertFalse(manager.is_browser_app("devenv.exe"))

    def test_domain_and_url_normalization(self):
        domain, norm_url = normalize_domain_and_url("https://github.com/organization/repository/issues/")
        self.assertEqual(domain, "github.com")
        self.assertEqual(norm_url, "https://github.com/organization/repository/issues")

        domain2, norm_url2 = normalize_domain_and_url(None, "Issues · repository · GitHub")
        self.assertEqual(domain2, "github.com")
        self.assertEqual(norm_url2, "https://github.com")


class TestUrlUsageService(unittest.TestCase):
    def setUp(self):
        self.runtime = MagicMock()
        self.cache = MagicMock()
        self.service = UrlUsageService(self.runtime, self.cache)

    def test_start_and_stop_tracker(self):
        session = {"entry_id": 123}
        self.service.start_tracker(session)
        self.assertTrue(self.service._tracking)
        self.assertEqual(self.service._entry_id, 123)

        self.service.stop_tracker()
        self.assertFalse(self.service._tracking)
        self.assertIsNone(self.service._entry_id)

    @patch("background_services.activity.url_usage_service.get_active_window_info")
    def test_session_accumulation_and_flush_on_app_switch(self, mock_active_window):
        # 1. Start tracker
        self.service.start_tracker({"entry_id": 100})

        # 2. First tick: Chrome active on GitHub
        mock_active_window.return_value = ("chrome.exe", "Issues · repository · GitHub")
        self.service.tick()

        self.assertEqual(self.service._current_browser, "Google Chrome")
        self.assertEqual(self.service._current_domain, "github.com")
        initial_event_id = self.service._current_client_event_id
        self.assertIsNotNone(initial_event_id)

        # 3. Fast forward time slightly (same URL session, 10s elapsed)
        now = time.monotonic()
        self.service._session_start = now - 10.0
        self.service._last_observed = now

        # 4. User switches away to VS Code
        mock_active_window.return_value = ("code.exe", "main.py - Visual Studio Code")
        self.service.tick()

        # 5. Verify local cache received save_url_usage with stable client_event_id
        self.cache.save_url_usage.assert_called_once()
        kwargs = self.cache.save_url_usage.call_args.kwargs
        self.assertEqual(kwargs["time_entry_id"], 100)
        self.assertEqual(kwargs["browser_name"], "Google Chrome")
        self.assertEqual(kwargs["domain"], "github.com")
        self.assertEqual(kwargs["client_event_id"], initial_event_id)
        self.assertGreaterEqual(kwargs["duration_seconds"], 10)

    @patch("background_services.activity.url_usage_service.get_active_window_info")
    def test_url_switch_finalizes_previous_session(self, mock_active_window):
        self.service.start_tracker({"entry_id": 100})

        # Tick 1: GitHub
        mock_active_window.return_value = ("chrome.exe", "Issues · GitHub")
        self.service.tick()

        now = time.monotonic()
        self.service._session_start = now - 15.0
        self.service._last_observed = now

        # Tick 2: Stack Overflow
        mock_active_window.return_value = ("chrome.exe", "Python questions - Stack Overflow")
        self.service.tick()

        # Verify previous session was saved
        self.cache.save_url_usage.assert_called_once()
        call_kwargs = self.cache.save_url_usage.call_args.kwargs
        self.assertEqual(call_kwargs["domain"], "github.com")
        self.assertGreaterEqual(call_kwargs["duration_seconds"], 15)

        # Verify new session started
        self.assertEqual(self.service._current_domain, "stackoverflow.com")
