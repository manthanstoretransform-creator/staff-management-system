"""
Coverage for the redesign's two new shared pieces:

* `core.branding` -- one definition of the Monitra mark, preferring a real
  logo file dropped into desktop/assets/ and falling back to the vendored
  vector mark. The tray/window icon and the sidebar both render from it, so
  they cannot drift apart.
* `ui.stat_cards` -- the four summary cards. Every value is handed in; the
  row derives no duration and reads no service. Unknown values are said
  plainly rather than shown as a measured-looking zero.
"""
import os

import pytest

from core import branding
from ui.stat_cards import StatCardsRow


# ── branding ─────────────────────────────────────────────────────────────────

def test_mark_renders_at_any_requested_size(qapp):
    for size in (16, 32, 44, 256):
        pixmap = branding.logo_pixmap(size)
        assert not pixmap.isNull()
        assert max(pixmap.width(), pixmap.height()) == size


def test_pixmaps_are_cached_per_size(qapp):
    assert branding.logo_pixmap(48) is branding.logo_pixmap(48)


def test_a_bundled_logo_file_wins_over_the_vector_mark(qapp, tmp_path, monkeypatch):
    """Dropping artwork into the assets folder is the whole swap procedure --
    no other code change, and it must actually take precedence."""
    from PySide6.QtGui import QPixmap

    logo = tmp_path / "monitra_logo.png"
    canvas = QPixmap(64, 64)
    canvas.fill()
    assert canvas.save(str(logo))

    monkeypatch.setattr(branding, "ASSETS_DIR", str(tmp_path))
    monkeypatch.setattr(branding, "_logo_path_cache", None)
    monkeypatch.setattr(branding, "_logo_path_resolved", False)
    monkeypatch.setattr(branding, "_pixmap_cache", {})

    assert branding.logo_file_path() == str(logo)
    assert not branding.logo_pixmap(32).isNull()


def test_no_logo_file_still_produces_the_mark(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(branding, "ASSETS_DIR", str(tmp_path / "empty"))
    monkeypatch.setattr(branding, "_logo_path_cache", None)
    monkeypatch.setattr(branding, "_logo_path_resolved", False)
    monkeypatch.setattr(branding, "_pixmap_cache", {})

    assert branding.logo_file_path() is None
    assert not branding.logo_pixmap(32).isNull()


def test_the_app_icon_is_built_from_the_same_mark(qapp):
    """The tray/window icon and the sidebar must be one artwork, not two."""
    from background_services.notifications.notification_service import create_app_icon

    icon = create_app_icon(sizes=[64])
    from_icon = icon.pixmap(64, 64).toImage()
    assert from_icon == branding.logo_pixmap(64).toImage()


# ── stat cards ───────────────────────────────────────────────────────────────

def test_reset_states_are_honest_not_zeroed(qapp):
    row = StatCardsRow()
    assert row.tasks_card._value.text() == "—"
    assert row.tasks_card._progress.isHidden()
    assert row.active_card._value.text() == "No active task"
    assert row.workday_card._sub.text() == "No time logged"


def test_total_card_formats_seconds_and_flags_tracking(qapp):
    row = StatCardsRow()
    row.set_total_seconds(3_725, True)
    assert row.total_card._value.text() == "01:02:05"
    assert row.total_card._sub.text() == "Tracking now"

    row.set_total_seconds(3_725, False)
    assert row.total_card._sub.text() == "Not tracking"


def test_tasks_card_shows_the_ratio_and_its_progress(qapp):
    row = StatCardsRow()
    row.set_tasks_completed(3, 12)
    assert row.tasks_card._value.text() == "3 / 12"
    assert row.tasks_card._progress.value() == 25
    assert not row.tasks_card._progress.isHidden()


def test_tasks_card_without_a_project_hides_the_bar(qapp):
    row = StatCardsRow()
    row.set_tasks_completed(3, 12)
    row.set_tasks_completed(None, None)
    assert row.tasks_card._value.text() == "—"
    assert row.tasks_card._progress.isHidden()


def test_active_task_card_elides_long_names_but_keeps_the_full_one(qapp):
    row = StatCardsRow()
    name = "A very long task name that will not fit the card"
    row.set_active_task(name, "Project X")
    assert row.active_card._value.text().endswith("…")
    assert row.active_card._value.toolTip() == name
    assert row.active_card._sub.text() == "Project X"


def test_work_day_card_says_so_when_the_day_holds_nothing(qapp):
    row = StatCardsRow()
    row.set_work_day(7200, "10:00", "12:00")
    assert row.workday_card._value.text() == "02:00:00"
    assert row.workday_card._sub.text() == "10:00 – 12:00"

    row.set_work_day(None, None, None)
    assert row.workday_card._sub.text() == "No time logged"
