"""
Coverage for who may be assigned a project task, and for the endpoint that
tells a client who those people are.

POST /api/v1/projects/{id}/tasks requires the assignee to be an active
employee who is a member of the project. That rule is correct, but nothing
exposed the resulting set, so the desktop client guessed -- it assigned every
task to the signed-in user, which works for an employee and is refused with
HTTP 400 for an admin or a leader. These tests pin both halves: the rule, and
the list that makes the rule satisfiable.
"""
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.models.project import Project
from app.models.user import User
from app.schemas.project_management import TaskCreate
from app.services.project_management import ProjectManagementService


def _user(role="admin", user_id=1):
    return User(id=user_id, organization_id=1, role_name=role, permissions={})


def _project():
    return Project(id=7, organization_id=1, status="active")


class TestTaskAssigneeRule(unittest.TestCase):
    """The assignee validation, exercised with the caller as an admin -- the
    account for which task creation failed in production."""

    def setUp(self):
        self.db = MagicMock()
        self.payload = TaskCreate(name="Write the report", assignee_id=1, status_id=1)

    def _create(self, member, assignee, user=None):
        # _project, then the membership lookup, then the assignee lookup.
        self.db.scalar.side_effect = [_project(), member, assignee]
        self.db.get.return_value = MagicMock(id=1)
        return ProjectManagementService.create_task(
            self.db, user or _user(), 7, self.payload
        )

    def test_an_admin_cannot_be_the_assignee_even_as_a_project_member(self):
        """The exact production failure: the desktop self-assigned, so an
        admin's own id arrived as assignee_id and was refused."""
        with self.assertRaises(HTTPException) as ctx:
            self._create(member=MagicMock(), assignee=_user(role="admin"))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("active employee", ctx.exception.detail)

    def test_an_employee_who_is_not_a_project_member_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self._create(member=None, assignee=_user(role="employee", user_id=2))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("assigned to this project", ctx.exception.detail)

    def test_the_refusal_is_a_400_with_an_explanation_a_user_can_act_on(self):
        """The desktop surfaces `detail` verbatim, so it has to say what to
        do about it, not just that something was wrong."""
        with self.assertRaises(HTTPException) as ctx:
            self._create(member=None, assignee=None)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(ctx.exception.detail.strip().endswith("."))

    def test_the_creator_is_taken_from_the_authenticated_user(self):
        """Not from the payload -- TaskCreate has no creator field at all, so
        a client cannot create a task as somebody else."""
        self.assertNotIn("created_by", TaskCreate.model_fields)
        self.assertNotIn("user_id", TaskCreate.model_fields)
        self.assertNotIn("organization_id", TaskCreate.model_fields)


class TestAssignableList(unittest.TestCase):
    def test_it_returns_the_projects_employees(self):
        db = MagicMock()
        employees = [_user(role="employee", user_id=2), _user(role="employee", user_id=5)]
        db.scalar.return_value = _project()
        db.scalars.return_value.all.return_value = employees

        result = ProjectManagementService.task_assignees(db, _user(), 7)

        self.assertEqual([item.id for item in result], [2, 5])

    def test_it_404s_for_a_project_outside_the_callers_organisation(self):
        db = MagicMock()
        db.scalar.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            ProjectManagementService.task_assignees(db, _user(), 7)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_the_query_is_restricted_to_active_employees_of_this_project(self):
        """Compiled once and read, because the whole point of this endpoint is
        that its result set matches what create_task accepts. An org-wide list
        would offer people the create call then refuses."""
        db = MagicMock()
        db.scalar.return_value = _project()
        db.scalars.return_value.all.return_value = []

        ProjectManagementService.task_assignees(db, _user(), 7)

        sql = str(db.scalars.call_args.args[0]).lower()
        self.assertIn("join project_members", sql)
        self.assertIn("users.is_active", sql)
        self.assertIn("users.role_name", sql)


class TestRouteRegistration(unittest.TestCase):
    def test_the_assignee_endpoint_is_mounted_beside_the_create_endpoint(self):
        from app.main import app

        # app.routes carries _IncludedRouter entries alongside real routes in
        # this FastAPI version, so read the paths off the generated schema.
        paths = app.openapi()["paths"]

        self.assertIn("get", paths["/api/v1/projects/{project_id}/task-assignees"])
        # The path the desktop posts to, and the one this list feeds.
        self.assertIn("post", paths["/api/v1/projects/{project_id}/tasks"])
