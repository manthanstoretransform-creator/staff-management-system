"""
Coverage for the task card's own layout.

The card has no section header of its own any more: the project name, the
task count, the project total and the "Active" pill all lived in a strip
that repeated what the sidebar selection and the summary cards already say,
so the card now starts at its column headers. Search, Add Task and Request
live in the top bar; the dialogs and the filtering stay here.
"""
from unittest.mock import MagicMock

from ui.task_table import COLUMN_LABELS, COLUMN_ORDER, TaskSection


def _make_section(elapsed: int = 0, running: bool = False) -> TaskSection:
    api = MagicMock()
    api.timer_elapsed_seconds.return_value = elapsed
    api.is_timer_running.return_value = running
    return TaskSection(api=api, task_service=MagicMock())


def _tasks():
    return [
        {"id": 1, "name": "Alpha", "time_tracked_seconds": 3600},
        {"id": 2, "name": "Beta", "time_tracked_seconds": 1800},
        {"id": 3, "name": "Gamma", "time_tracked_seconds": 0},
    ]


def test_the_first_column_is_named_task(qapp):
    """It used to read MEMO, which named the field rather than the row."""
    assert COLUMN_LABELS["task"] == "TASK"
    section = _make_section()
    assert section._column_header_labels["task"].text() == "TASK"


def test_every_column_header_still_renders(qapp):
    section = _make_section()
    assert [section._column_header_labels[key].text() for key in COLUMN_ORDER] == [
        "TASK", "CREATE ON", "HOURS", "ACTION",
    ]


def test_no_section_header_widgets_remain(qapp):
    """The strip is gone, not merely hidden -- a hidden widget would still
    reserve its place in the card's layout."""
    section = _make_section()
    for attribute in (
        "_section_label", "_title_label", "_count_badge",
        "_total_hours_lbl", "_active_task_lbl", "_current_task_lbl",
    ):
        assert not hasattr(section, attribute), attribute


def test_the_card_starts_at_the_column_headers(qapp):
    """The first thing inside the card is the column header row itself."""
    section = _make_section()
    card_layout = section._column_header_labels["task"].parent().parent().layout()
    first = card_layout.itemAt(0).widget()
    assert first is section._column_header_labels["task"].parent()


def test_global_controls_live_in_the_top_bar(qapp):
    section = _make_section()
    assert not hasattr(section, "_manual_entry_btn")
    assert not hasattr(section, "_add_task_btn")
    assert not hasattr(section, "_search")
    assert callable(section.open_manual_entry_dialog)
    assert callable(section.open_add_task_dialog)
    assert callable(section.apply_search)


def test_search_still_filters_the_rows(qapp):
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 7, "project_name": "Test"}, "#3B82F6")
    assert len(section._task_rows) == 3

    section.apply_search("Alpha")
    assert len(section._task_rows) == 1

    section.apply_search("")
    assert len(section._task_rows) == 3


def test_completed_tasks_stay_out_of_the_list(qapp):
    section = _make_section()
    tasks = _tasks()
    tasks[2]["status"] = "completed"
    section.set_tasks(tasks, {"id": 7, "project_name": "Test"}, "#3B82F6")
    assert len(section._task_rows) == 2


def test_add_task_availability_is_published_for_the_header_button(qapp):
    """The button is the top bar's, so its enabled state has to follow the
    selection over a signal rather than a direct widget call."""
    section = _make_section()
    seen = []
    section.add_task_available.connect(seen.append)

    section.set_tasks(_tasks(), {"id": 7, "project_name": "Test"}, "#3B82F6")
    assert seen == [True]
    section.clear()
    assert seen == [True, False]


def test_stopping_a_timer_banks_the_session_on_the_task(qapp):
    """The row folds the finished session into its own displayed total; the
    task dict has to be folded too, or a rebuild before the next refresh
    (a search, a project reload) would show the row's time going backwards."""
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 7, "project_name": "Test"}, "#3B82F6")
    section._running_task_id = 1
    section._on_timer_stopped({"session": {"task_id": 1}, "elapsed_seconds": 600})

    banked = next(t["time_tracked_seconds"] for t in section._tasks if t["id"] == 1)
    assert banked == 3600 + 600

    section.apply_search("Alpha")           # forces a rebuild of the row
    assert section._task_rows[0]._elapsed_seconds == 4200


def test_the_running_task_name_falls_back_to_the_service(qapp):
    """The tracked task can belong to a project that is not on screen, so
    the name comes from the timer's own session rather than a guess."""
    section = _make_section()
    section.api.active_session.return_value = {"task_id": 99, "task_name": "Elsewhere"}
    section._running_task_id = 99
    assert section._running_task_display_name() == "Elsewhere"

    section._running_task_id = None
    assert section._running_task_display_name() is None
