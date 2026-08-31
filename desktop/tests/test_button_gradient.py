"""
Coverage for the shared cyan-to-violet button gradient
(ui.styles.BUTTON_GRADIENT) that every primary action button uses: Add
Task, Save / Save Entry, Refresh, and Start/Stop.
"""
from unittest.mock import MagicMock

from ui.styles import BUTTON_GRADIENT
from ui.task_table import (
    AddTaskDialog,
    EditTaskDialog,
    ManualTimeEntryDialog,
    TaskRow,
    TaskSection,
)


def test_add_task_dialog_save_button_uses_the_shared_gradient(qapp):
    dlg = AddTaskDialog("Demo Project")
    assert BUTTON_GRADIENT in dlg.styleSheet()


def test_edit_task_dialog_save_button_uses_the_shared_gradient(qapp):
    dlg = EditTaskDialog({"id": 1, "name": "Task A"}, [{"id": 1, "name": "Open"}])
    assert BUTTON_GRADIENT in dlg.styleSheet()


def test_manual_time_entry_dialog_save_entry_button_uses_the_shared_gradient(qapp):
    dlg = ManualTimeEntryDialog(projects=[{"id": 1, "project_name": "Demo"}])
    assert BUTTON_GRADIENT in dlg.styleSheet()


def test_add_task_and_refresh_buttons_use_the_shared_gradient(qapp):
    section = TaskSection(api=MagicMock(), task_service=MagicMock())
    assert BUTTON_GRADIENT in section.styleSheet()
    assert BUTTON_GRADIENT in section._refresh_btn.styleSheet()


def test_start_stop_button_uses_the_shared_gradient_in_both_states(qapp):
    row = TaskRow({"id": 1, "name": "Task A"}, project_id=1, project_name="P", project_color="#000")
    assert BUTTON_GRADIENT in row._timer_btn.styleSheet()  # idle -> "Start"
    row.mark_running(entry_id=5)
    assert BUTTON_GRADIENT in row._timer_btn.styleSheet()  # running -> "Stop"
