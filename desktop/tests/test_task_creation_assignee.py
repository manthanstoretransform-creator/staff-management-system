"""
Coverage for who a new task is assigned to, and for what the user is told
when the backend refuses one.

The production bug this locks down: Add Task had no assignee field, so the
caller assigned every task to whoever was signed in (`self._user_id or 1`).
The backend requires a task's assignee to be an active *employee* who is a
member of the project, so the request succeeded for an employee creating
their own task and failed with HTTP 400 for every admin and leader. It looked
like an account-specific authentication fault; it was a payload the client
could not have got right, reported through an error message that discarded
the backend's explanation.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.api.exceptions import ApiError, ApiHttpError, error_detail
from app.tasks.service import TaskService
from ui.task_table import AddTaskDialog, TaskSection


EMPLOYEES = [
    {"id": 2, "name": "Hardik Raval", "email": "hardik@example.com", "role": "employee"},
    {"id": 5, "name": "Asha Menon", "email": "asha@example.com", "role": "employee"},
]


# ── the backend's explanation reaches the user ───────────────────────────────

def test_error_detail_reads_a_plain_httpexception_detail():
    body = json.dumps({"detail": "Task assignee must be assigned to this project."})
    assert error_detail(body) == "Task assignee must be assigned to this project."


def test_error_detail_flattens_a_schema_validation_body():
    body = json.dumps({"detail": [
        {"loc": ["body", "assignee_id"], "msg": "Field required", "type": "missing"},
    ]})
    assert error_detail(body) == "assignee_id: Field required"


def test_error_detail_never_raises_on_an_unexpected_body():
    assert error_detail(None, "fallback") == "fallback"
    assert error_detail("", "fallback") == "fallback"
    assert error_detail("<html>502 Bad Gateway</html>") == "<html>502 Bad Gateway</html>"
    assert error_detail(json.dumps({"error": "nope"}), "fallback") == "fallback"


def _service_raising(status_code: int, body: str) -> TaskService:
    client = MagicMock()
    client.post.side_effect = ApiHttpError(status_code=status_code, response_body=body)
    return TaskService(client)


def test_a_rejected_create_reports_why_not_just_the_status_code():
    service = _service_raising(
        400, json.dumps({"detail": "Task assignee must be an active employee in this organization."})
    )
    with pytest.raises(ApiError) as caught:
        service.create_task(1, "Write the report", assignee_id=1)

    message = str(caught.value)
    assert "must be an active employee" in message
    assert "Server error" not in message
    assert caught.value.status_code == 400


def test_a_rejection_with_no_usable_body_still_says_something_true():
    service = _service_raising(400, "")
    with pytest.raises(ApiError) as caught:
        service.create_task(1, "Write the report", assignee_id=1)
    assert "rejected the request (HTTP 400)" in str(caught.value)
    assert caught.value.status_code == 400


def test_create_task_sends_only_the_task_fields_not_a_creator_id():
    """The creating user is derived from the bearer token server-side. A
    client-supplied creator id would be both untrusted and, when it came from
    a stale cache, wrong."""
    client = MagicMock()
    service = TaskService(client)
    service.create_task(7, "Write the report", assignee_id=5)

    path, kwargs = client.post.call_args.args[0], client.post.call_args.kwargs
    assert path == "/api/v1/projects/7/tasks"
    assert kwargs["json_data"] == {
        "name": "Write the report", "assignee_id": 5, "status_id": 1
    }


def test_the_assignee_list_is_fetched_per_project(qapp):
    client = MagicMock()
    client.get.return_value.json.return_value = EMPLOYEES
    assert TaskService(client).get_task_assignees(9) == EMPLOYEES
    assert client.get.call_args.args[0] == "/api/v1/projects/9/task-assignees"


# ── the dialog offers a real choice ──────────────────────────────────────────

def test_the_dialog_returns_the_chosen_assignee(qapp):
    dialog = AddTaskDialog("Apollo", EMPLOYEES)
    dialog.name_input.setText("  Write the report  ")
    dialog.assignee_combo.setCurrentIndex(1)

    data = dialog.get_data()
    assert data["task_name"] == "Write the report"
    assert data["assignee_id"] == 5


def test_the_signed_in_user_is_preselected_when_they_are_a_valid_assignee(qapp):
    """An employee adding a task for themselves keeps their one-click flow."""
    dialog = AddTaskDialog("Apollo", EMPLOYEES, default_assignee_id=2)
    assert dialog.get_data()["assignee_id"] == 2


def test_an_admin_is_not_preselected_because_they_are_not_assignable(qapp):
    """The admin's own id is not in the list, so the selection falls to the
    first real employee rather than to the admin -- which is exactly the
    request the backend used to reject with HTTP 400."""
    dialog = AddTaskDialog("Apollo", EMPLOYEES, default_assignee_id=1)
    assert dialog.get_data()["assignee_id"] == 2


# ── the section never builds an impossible request ───────────────────────────

def _section() -> TaskSection:
    api = MagicMock()
    api.timer_elapsed_seconds.return_value = 0
    api.is_timer_running.return_value = False
    return TaskSection(api=api, task_service=MagicMock())


def test_add_task_loads_the_projects_assignees_off_the_gui_thread(qapp):
    section = _section()
    section._project = {"id": 7, "project_name": "Apollo"}

    section._on_add_task_clicked()

    assert section.api.run_in_background.call_count == 1
    assert section.api.run_in_background.call_args.kwargs["key"] == "load-task-assignees:7"
    # The dialog is not constructed until the list arrives.
    section.task_service.create_task.assert_not_called()


def test_a_project_with_no_assignable_employees_explains_itself(qapp, monkeypatch):
    """Rather than sending a task the backend is certain to refuse."""
    from PySide6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: shown.append(args[2])
    )
    section = _section()
    section._project = {"id": 7, "project_name": "Apollo"}

    section._open_add_task_dialog(7, [])

    assert shown and "no employees assigned" in shown[0]
    section.task_service.create_task.assert_not_called()


def test_a_late_assignee_list_for_another_project_is_discarded(qapp):
    section = _section()
    section._project = {"id": 9, "project_name": "Borealis"}

    section._open_add_task_dialog(7, EMPLOYEES)

    section.task_service.create_task.assert_not_called()
