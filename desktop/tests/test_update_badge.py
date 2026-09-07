"""
The account menu's "Updates (n)" entry.

A toast is transient. The user who was away from the desk, or who dismissed
the notification without reading it, had no way back to the download — the
update was announced and then simply gone. This badge is that way back.

The rule the tests below pin down is that the count is **derived, never
tallied**: it is the number of recorded versions strictly newer than
`version.VERSION`. Nothing increments it and nothing has to remember to clear
it, so installing the update makes it vanish by arithmetic. A hand-maintained
counter is precisely the kind of second source of truth this project has been
burned by before.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import version
from background_services.network import NetworkState
from background_services.update import UpdateService
from background_services.update.update_service import (
    ANNOUNCED_VERSIONS_KEY, newer_than_installed,
)
from ui.sidebar import SidebarWidget, updates_menu_label


class FakeApi:
    def __init__(self, payload):
        self.payload = payload

    def get_latest_version(self):
        return self.payload


class FakeCache:
    """The one row of `app_state` this feature persists."""

    def __init__(self, initial=None):
        self.state = {} if initial is None else {ANNOUNCED_VERSIONS_KEY: initial}

    def save_app_state(self, key, value):
        self.state[key] = value

    def load_app_state(self, key):
        return self.state.get(key)


def make_service(payload=None, stored=None):
    runtime = SimpleNamespace(
        api_client=SimpleNamespace(access_token="token"),
        network=SimpleNamespace(network_state=NetworkState.BACKEND_REACHABLE),
        notifications=SimpleNamespace(notify=lambda *a, **k: True),
        storage=None,
    )
    cache = FakeCache(stored)
    service = UpdateService(runtime, FakeApi(payload), cache)
    return service, cache


def available(latest, url="https://example.invalid/releases"):
    return {
        "latest_version": latest, "download_url": url,
        "release_notes_url": None, "update_available": True,
        "client_version": version.VERSION,
    }


def _check(service):
    """Run one real check (the first tick is the deliberate startup delay)."""
    service.tick()
    service.tick()


# ── The counting rule ─────────────────────────────────────────────────────────

def test_only_versions_newer_than_the_installed_build_count():
    assert newer_than_installed(["1.0.0", "1.0.1", "2.0.0"], "1.0.1") == ["2.0.0"]
    # Installing the update empties it -- no acknowledgement step, no flag.
    assert newer_than_installed(["2.0.0"], "2.0.0") == []
    assert newer_than_installed(["2.0.0"], "2.1.0") == []


def test_versions_are_ordered_numerically_not_as_strings():
    assert newer_than_installed(["1.10.0", "1.9.0"], "1.0.0") == ["1.9.0", "1.10.0"]


def test_unparseable_versions_are_ignored_rather_than_guessed_at():
    assert newer_than_installed(["not-a-version", "9.9.9"], "1.0.1") == ["9.9.9"]


def test_duplicates_are_counted_once():
    assert newer_than_installed(["9.9.9", "9.9.9"], "1.0.1") == ["9.9.9"]


# ── The service ───────────────────────────────────────────────────────────────

def test_an_announced_release_raises_the_badge_and_is_persisted():
    service, cache = make_service(available("9.9.9"))
    counts = []
    service.pending_count_changed.connect(counts.append)

    _check(service)

    assert service.pending_count == 1
    assert counts == [1]
    # Durable: a restart must not lose it, which is the entire point.
    assert cache.state[ANNOUNCED_VERSIONS_KEY] == ["9.9.9"]


def test_a_second_release_makes_it_two():
    service, _cache = make_service(available("9.9.9"))
    _check(service)
    service._update_api.payload = available("10.0.0")
    service.tick()

    assert service.pending_count == 2


def test_the_same_release_announced_again_does_not_double_count():
    # The backend answers "9.9.9 is available" on every poll. A tallied
    # counter would climb forever; a derived one cannot.
    service, _cache = make_service(available("9.9.9"))
    _check(service)
    service.tick()
    service.tick()

    assert service.pending_count == 1


def test_the_count_is_published_only_when_it_changes():
    service, _cache = make_service(available("9.9.9"))
    counts = []
    service.pending_count_changed.connect(counts.append)

    _check(service)
    service.tick()
    service.tick()

    assert counts == [1], "a repeated poll must not re-emit the same count"


def test_a_restart_restores_the_badge_before_the_first_check():
    # The user who restarted specifically to deal with an update must not be
    # shown an empty menu for the first 30 seconds.
    service, _cache = make_service(available("9.9.9"), stored=["9.9.9"])
    service.on_start()
    try:
        assert service.pending_count == 1
    finally:
        service.on_stop(2000)


def test_installing_the_update_clears_the_badge_and_prunes_the_record():
    # The record holds a version this build already is. Nothing acknowledges
    # anything -- the arithmetic simply stops finding it newer.
    service, cache = make_service(available("9.9.9"), stored=[version.VERSION])
    service.on_start()
    try:
        assert service.pending_count == 0
        assert cache.state[ANNOUNCED_VERSIONS_KEY] == []
    finally:
        service.on_stop(2000)


def test_a_client_that_is_up_to_date_reports_no_pending_updates():
    service, _cache = make_service({
        "latest_version": version.VERSION, "download_url": None,
        "release_notes_url": None, "update_available": False,
        "client_version": version.VERSION,
    })
    _check(service)

    assert service.pending_count == 0


def test_withdrawing_the_release_clears_the_badge():
    # The rollback lever: an operator clears DESKTOP_LATEST_VERSION, so the
    # endpoint stops offering anything. The badge must go with the toast --
    # a withdrawn release is still numerically newer than the installed
    # build, so merely recounting would leave the entry pointing at a build
    # that had just been pulled, and (since the URL is withdrawn too) at
    # nothing at all.
    service, cache = make_service(available("9.9.9"))
    _check(service)
    assert service.pending_count == 1

    service._update_api.payload = {
        "latest_version": None, "download_url": None,
        "release_notes_url": None, "update_available": False,
        "client_version": version.VERSION,
    }
    service.tick()

    assert service.pending_count == 0
    assert cache.state[ANNOUNCED_VERSIONS_KEY] == []


def test_a_re_published_release_announces_itself_again():
    # Withdrawn, then put back after the fix. The user must be told again,
    # not have it swallowed as "already announced this session".
    service, _cache = make_service(available("9.9.9"))
    _check(service)
    service._update_api.payload = {
        "latest_version": None, "download_url": None,
        "release_notes_url": None, "update_available": False,
        "client_version": version.VERSION,
    }
    service.tick()
    service._update_api.payload = available("9.9.9")
    service.tick()

    assert service.pending_count == 1


def test_a_corrupt_record_is_discarded_rather_than_crashing_startup():
    service, _cache = make_service(available("9.9.9"), stored="not a list")
    service.on_start()
    try:
        assert service.pending_count == 0
    finally:
        service.on_stop(2000)


def test_the_download_url_comes_from_the_check_not_a_second_request():
    service, _cache = make_service(available("9.9.9"))
    _check(service)

    assert service.download_url() == "https://example.invalid/releases"


def test_no_published_download_url_is_reported_as_none():
    service, _cache = make_service(available("9.9.9", url=None))
    _check(service)

    assert service.download_url() is None


def test_logout_clears_the_badge():
    service, _cache = make_service(available("9.9.9"))
    _check(service)
    assert service.pending_count == 1

    service.reset_session()

    assert service.pending_count == 0


# ── The menu entry ────────────────────────────────────────────────────────────

def test_the_label_carries_the_count():
    assert updates_menu_label(1) == "Updates (1)"
    assert updates_menu_label(2) == "Updates (2)"
    assert updates_menu_label(0) == "Updates"


@pytest.fixture
def sidebar(qapp):
    widget = SidebarWidget()
    yield widget
    widget.deleteLater()


def _labels(menu):
    return [a.text().replace("&&", "&") for a in menu.actions() if not a.isSeparator()]


def test_the_entry_is_absent_when_nothing_is_pending(sidebar):
    menu, _profile, _feedback, _logout, updates_action = sidebar._build_user_menu()
    try:
        assert updates_action is None
        # An "Updates" row with nothing to open would be a dead end on every
        # day but release day.
        assert _labels(menu) == ["Profile", "Feedback & Help", "Sign Out"]
    finally:
        menu.deleteLater()


def test_the_entry_appears_with_its_count(sidebar):
    sidebar.set_pending_updates(2)
    menu, _profile, _feedback, _logout, updates_action = sidebar._build_user_menu()
    try:
        assert updates_action is not None
        assert updates_action.text() == "Updates (2)"
        assert not updates_action.icon().isNull()
        assert _labels(menu) == [
            "Profile", "Feedback & Help", "Updates (2)", "Sign Out",
        ]
    finally:
        menu.deleteLater()


def test_the_entry_disappears_once_the_update_is_installed(sidebar):
    sidebar.set_pending_updates(1)
    sidebar.set_pending_updates(0)
    menu, _profile, _feedback, _logout, updates_action = sidebar._build_user_menu()
    try:
        assert updates_action is None
        assert "Updates" not in " ".join(_labels(menu))
    finally:
        menu.deleteLater()


def test_a_negative_count_is_refused(sidebar):
    sidebar.set_pending_updates(-3)
    assert sidebar.pending_updates == 0


if __name__ == "__main__":
    pytest.main([__file__])
