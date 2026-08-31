"""
Coverage for the running-task row's visual style: a dark/gradient
background, explicitly *no* shadow and *no* border -- both were the
previous design and were asked to be removed in favor of the gradient.
"""
from ui.task_table import TaskRow


def _make_row(**overrides):
    task = {
        "id": 1, "name": "Design homepage", "time_tracked_seconds": 120,
        "estimated_hours": 4, "description": "A short description",
    }
    task.update(overrides)
    return TaskRow(task, project_id=1, project_name="Test", project_color="#3B82F6")


def test_running_row_has_no_shadow_effect(qapp):
    row = _make_row()
    row.mark_running(entry_id=5)
    assert row.graphicsEffect() is None


def test_running_row_has_no_border_declaration(qapp):
    row = _make_row()
    row.mark_running(entry_id=5)
    assert "border:" not in row.styleSheet()
    assert "border-color" not in row.styleSheet()


def test_running_row_uses_a_gradient_background(qapp):
    row = _make_row()
    row.mark_running(entry_id=5)
    assert "qlineargradient" in row.styleSheet()


def test_stopped_row_still_has_no_shadow_or_gradient(qapp):
    """Only the running state changed -- the idle row's look is untouched."""
    row = _make_row()
    assert row.graphicsEffect() is None
    assert "qlineargradient" not in row.styleSheet()


def test_running_row_relightens_every_text_label_for_the_dark_background(qapp):
    row = _make_row()
    row.mark_running(entry_id=5)
    # Every label rendered on top of the new dark background must use a
    # light color -- the original dark-on-white colors would be unreadable.
    assert row._name_label.styleSheet() == "color: #F8FAFC;"
    assert row._desc_label.styleSheet() == "color: #CBD5E1;"
    assert "#4ADE80" in row._time_label.styleSheet()

    row.mark_stopped(banked_seconds=60)
    assert "#F8FAFC" not in row._name_label.styleSheet()


def test_progress_bar_switches_to_its_dark_track_color_while_running(qapp):
    row = _make_row()
    assert row._progress_bar is not None
    assert row._progress_bar._dark is False
    row.mark_running(entry_id=5)
    assert row._progress_bar._dark is True
    row.mark_stopped(banked_seconds=60)
    assert row._progress_bar._dark is False
