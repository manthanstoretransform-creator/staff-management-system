"""
Coverage for the shared cyan-to-violet button gradient
(ui.styles.BUTTON_GRADIENT) that every primary action button uses: Add
Task, Save / Save Entry, and Start/Stop (Refresh moved to an icon-only
control in the top bar and is no longer part of this gradient family --
see test_topbar.py).
"""
from unittest.mock import MagicMock

from ui.styles import BUTTON_GRADIENT, BUTTON_GRADIENT_REVERSED
from ui.task_table import (
    AddTaskDialog,
    EditTaskDialog,
    ManualTimeEntryDialog,
    TaskRow,
)
from ui.topbar import TopBar


def test_add_task_dialog_save_button_uses_the_shared_gradient(qapp):
    dlg = AddTaskDialog("Demo Project")
    assert BUTTON_GRADIENT in dlg.styleSheet()


def test_edit_task_dialog_save_button_uses_the_shared_gradient(qapp):
    dlg = EditTaskDialog({"id": 1, "name": "Task A"}, [{"id": 1, "name": "Open"}])
    assert BUTTON_GRADIENT in dlg.styleSheet()


def test_manual_time_entry_dialog_save_entry_button_uses_the_shared_gradient(qapp):
    dlg = ManualTimeEntryDialog(projects=[{"id": 1, "project_name": "Demo"}])
    assert BUTTON_GRADIENT in dlg.styleSheet()


def test_add_task_button_uses_the_shared_gradient(qapp):
    """Add Task moved to the top bar; the gradient moved with it."""
    bar = TopBar()
    assert BUTTON_GRADIENT in bar.styleSheet()
    assert not bar._add_task_btn.icon().isNull()


def test_start_button_uses_the_normal_gradient_direction(qapp):
    row = TaskRow({"id": 1, "name": "Task A"}, project_id=1, project_name="P", project_color="#000")
    assert BUTTON_GRADIENT in row._timer_btn.styleSheet()
    assert BUTTON_GRADIENT_REVERSED not in row._timer_btn.styleSheet()


def test_stop_button_uses_the_reversed_gradient_direction(qapp):
    """Same two colors as Start, mirrored direction -- the only visual cue
    (besides the button's own text/label) that the timer is running."""
    row = TaskRow({"id": 1, "name": "Task A"}, project_id=1, project_name="P", project_color="#000")
    row.mark_running(entry_id=5)
    assert BUTTON_GRADIENT_REVERSED in row._timer_btn.styleSheet()
    assert BUTTON_GRADIENT not in row._timer_btn.styleSheet()

    row.mark_stopped(banked_seconds=60)
    assert BUTTON_GRADIENT in row._timer_btn.styleSheet()
    assert BUTTON_GRADIENT_REVERSED not in row._timer_btn.styleSheet()
