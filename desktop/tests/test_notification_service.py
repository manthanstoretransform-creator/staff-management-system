"""
Notification service: admission control and thread safety.

The module was already sound in its lifecycle handling -- one owned
single-shot dismissal timer, one tray icon, an explicit Windows
AppUserModelID -- so this covers the parts that had no test behind them:
de-duplication, the per-minute ceiling, and the rule that a widget is only
ever touched on the thread that owns it.
"""
from __future__ import annotations

import threading

import pytest
from PySide6.QtCore import QThread
from unittest.mock import MagicMock

from background_services.notifications.notification_service import (
    NotificationLevel,
    NotificationService,
)


@pytest.fixture
def service(qapp):
    svc = NotificationService(MagicMock())
    # Stand in for the tray so the tests exercise admission and dispatch
    # without depending on a system tray existing in a headless run.
    svc._available = True
    svc._tray = MagicMock()
    svc._icon = MagicMock()
    svc._icon.isNull.return_value = False
    yield svc
    svc._dismiss_timer.stop()


def test_repeat_of_the_same_key_is_suppressed(service):
    assert service.notify("Back online", key="network") is True
    assert service.notify("Back online", key="network") is False
    assert service._tray.showMessage.call_count == 1


def test_network_flapping_produces_one_message_not_a_storm(service):
    """ONLINE/OFFLINE/ONLINE/OFFLINE... must not become a toast per
    transition."""
    for _ in range(20):
        service.notify("Connection lost", NotificationLevel.WARNING, key="network")
        service.notify("Back online", NotificationLevel.SUCCESS, key="network")

    assert service._tray.showMessage.call_count == 1


def test_distinct_events_are_not_suppressed_by_each_other(service):
    """Throttling must not silence unrelated, important events."""
    assert service.notify("Logged in", key="login") is True
    assert service.notify("Timer started", key="timer-started") is True
    assert service.notify("Sync failed", key="sync-error") is True
    assert service._tray.showMessage.call_count == 3


def test_the_per_minute_ceiling_is_enforced(service):
    admitted = sum(
        1 for index in range(NotificationService.MAX_PER_MINUTE + 10)
        if service.notify(f"message {index}", key=f"key-{index}")
    )
    assert admitted == NotificationService.MAX_PER_MINUTE


def test_a_dismissal_timer_is_armed_for_every_shown_notification(service):
    service.notify("Timer started", key="timer-started")
    assert service._dismiss_timer.isActive()
    assert service._dismiss_timer.isSingleShot()


def test_stopping_disarms_the_dismissal_timer(service):
    service.notify("Timer started", key="timer-started")
    service.on_stop(1000)
    assert not service._dismiss_timer.isActive()
    assert service._tray is None


def test_notifying_from_a_worker_thread_does_not_touch_the_tray_there(service):
    """The tray is a widget: a background service must never mutate it from
    its own thread. Off-thread calls are handed to the owning thread through
    a queued signal instead, so `showMessage` is not called inline."""
    result = {}

    def worker():
        result["thread"] = QThread.currentThread()
        result["returned"] = service.notify("From a worker", key="worker")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert result["returned"] is True
    assert result["thread"] is not service.thread()
    # Delivery was deferred, not performed on the worker thread.
    service._tray.showMessage.assert_not_called()

    # It arrives once the owning thread runs its event loop.
    qapp = service.thread()
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.processEvents()
    service._tray.showMessage.assert_called_once()
    assert qapp is service.thread()
