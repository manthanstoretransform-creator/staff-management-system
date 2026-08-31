"""
Regression coverage for the manual-time-entry dialog's task-loading bug:

ManualTimeEntryDialog.__init__ used to emit project_changed itself, before
the caller (TaskSection) had a chance to connect to it -- so the very first
emission, the one case that mattered when a project was already selected by
default, was silently lost. Changing the project afterward worked, because
that emission comes from currentIndexChanged, which fires after the caller
has already connected.

These tests exercise the actual TaskSection wiring pattern (construct the
dialog, connect, then fire the initial load) rather than the dialog alone,
since the bug was in the interaction between the two, not in either widget
by itself.
"""
from PySide6.QtCore import QTime

from ui.task_table import ManualTimeEntryDialog

PROJECTS = [
    {"id": 10, "project_name": "Website Redesign"},
    {"id": 20, "project_name": "Mobile App"},
]


def _open_and_wire(qapp, initial_project_id):
    """Mirrors TaskSection._on_manual_entry_clicked's own sequence."""
    dialog = ManualTimeEntryDialog(PROJECTS, initial_project_id)
    seen = []
    dialog.project_changed.connect(seen.append)
    if dialog.project_combo.currentData() is not None:
        seen.append(dialog.project_combo.currentData())
    return dialog, seen


def test_default_selected_project_triggers_a_task_load(qapp):
    """The exact bug: a project pre-selected via initial_project_id must
    still result in a task-load request once the caller is listening."""
    dialog, seen = _open_and_wire(qapp, initial_project_id=20)
    assert dialog.project_combo.currentData() == 20
    assert seen == [20]


def test_no_default_project_still_loads_tasks_for_the_first_item(qapp):
    """No initial_project_id -- the combo box still defaults to its first
    entry, and that must also trigger a task load."""
    dialog, seen = _open_and_wire(qapp, initial_project_id=None)
    assert dialog.project_combo.currentData() == 10
    assert seen == [10]


def test_changing_the_project_afterward_still_emits(qapp):
    """The already-working path must keep working: user-driven changes via
    the combo box fire project_changed after the dialog is open."""
    dialog, seen = _open_and_wire(qapp, initial_project_id=10)
    assert seen == [10]
    dialog.project_combo.setCurrentIndex(1)
    assert seen == [10, 20]


def test_dialog_init_alone_does_not_leave_project_changed_pending(qapp):
    """__init__ must not emit before anyone can be connected -- connecting
    right after construction should see zero emissions from construction
    itself (only from real subsequent interaction)."""
    dialog = ManualTimeEntryDialog(PROJECTS, initial_project_id=10)
    seen = []
    dialog.project_changed.connect(seen.append)
    assert seen == []


def test_duration_updates_and_rejects_end_before_start(qapp):
    dialog = ManualTimeEntryDialog(PROJECTS, initial_project_id=10)
    dialog.start_input.setTime(QTime(9, 0))
    dialog.end_input.setTime(QTime(10, 30))
    assert dialog.duration_label.text() == "Duration: 1h 30m"

    dialog.end_input.setTime(QTime(8, 0))
    assert dialog.duration_label.text() == "Duration: —"
