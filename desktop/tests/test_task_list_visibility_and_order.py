"""
Coverage for what the desktop task list shows and in which order.

Two presentation rules, both applied on every rebuild and every timer
transition so a refresh, a project switch or an adopted session can never
leave the list in a different state:

  * a task the server marks "completed" is not rendered (it is untouched in
    self._tasks, in the local cache and on the backend);
  * the actively tracked task is rendered first, everything else keeps the
    order the backend returned.
"""
from unittest.mock import MagicMock

from ui.task_table import TaskSection, is_task_completed


def _make_section() -> TaskSection:
    api = MagicMock()
    api.timer_elapsed_seconds.return_value = 0
    api.is_timer_running.return_value = False
    return TaskSection(api=api, task_service=MagicMock())


def _tasks():
    return [
        {"id": 1, "name": "Task A", "status": "todo"},
        {"id": 2, "name": "Task B", "status": "in_progress"},
        {"id": 3, "name": "Task C", "status": "completed"},
        {"id": 4, "name": "Task D", "status": "todo"},
    ]


def _rendered_ids(section):
    return [row.task.get("id") for row in section._task_rows]


def test_is_task_completed_reads_both_status_shapes():
    assert is_task_completed({"status": "completed"})
    assert is_task_completed({"status": "Completed"})
    assert is_task_completed({"status": {"id": 3, "name": "completed"}})
    assert not is_task_completed({"status": "in_progress"})
    assert not is_task_completed({"status": {"id": 1, "name": "todo"}})
    assert not is_task_completed({})


def test_completed_tasks_are_not_rendered(qapp):
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")

    assert _rendered_ids(section) == [1, 2, 4]


def test_completed_tasks_stay_in_the_underlying_task_list(qapp):
    """Hiding is presentation-only -- nothing is dropped or re-statused."""
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")

    assert [t["id"] for t in section._tasks] == [1, 2, 3, 4]
    assert section._tasks[2]["status"] == "completed"


def test_active_task_is_rendered_first(qapp):
    section = _make_section()
    section._running_task_id = 2
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")

    assert _rendered_ids(section) == [2, 1, 4]
    running = [row.task["id"] for row in section._task_rows if row._is_running]
    assert running == [2]


def test_ordering_and_filtering_survive_a_reload(qapp):
    section = _make_section()
    section._running_task_id = 4
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")

    assert _rendered_ids(section) == [4, 1, 2]


def test_starting_a_task_floats_its_existing_row_to_the_top(qapp):
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")
    assert _rendered_ids(section) == [1, 2, 4]

    section._on_timer_started({"task_id": 4, "entry_id": 77, "task_name": "Task D"})

    assert _rendered_ids(section) == [4, 1, 2]
    assert section._task_rows[0]._is_running


def test_stopping_a_task_restores_the_backend_order(qapp):
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")
    section._on_timer_started({"task_id": 4, "entry_id": 77, "task_name": "Task D"})
    section._on_timer_stopped({"session": {"task_id": 4}, "elapsed_seconds": 30})

    assert _rendered_ids(section) == [1, 2, 4]
    assert not any(row._is_running for row in section._task_rows)


def test_an_adopted_running_session_floats_its_row_to_the_top(qapp):
    """Resuming an existing timer on startup goes through sync_active_timer."""
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")

    section.sync_active_timer(task_id=2, entry_id=88, elapsed=120)

    assert _rendered_ids(section) == [2, 1, 4]
    assert section._task_rows[0]._is_running


def test_a_completed_task_that_is_being_tracked_stays_visible(qapp):
    """It would otherwise be hidden with a live timer and no Stop button."""
    section = _make_section()
    section._running_task_id = 3
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")

    assert _rendered_ids(section) == [3, 1, 2, 4]


def test_search_still_filters_within_the_visible_tasks(qapp):
    section = _make_section()
    section.set_tasks(_tasks(), {"id": 9, "project_name": "P"}, "#3B82F6")
    section._search_text = "task"
    section._rebuild_rows()

    assert _rendered_ids(section) == [1, 2, 4]
