import unittest
from types import SimpleNamespace

from app.schemas.teams import TeamMemberCardResponse, TeamSummaryResponse
from app.services.teams import TeamsService, _initials, _percent, _status_key


class TeamsTests(unittest.TestCase):
    def test_progress_handles_empty_projects(self):
        self.assertEqual(_percent(0, 0), 0)
        self.assertEqual(_percent(2, 5), 40)

    def test_initials_and_status_keys(self):
        self.assertEqual(_initials("Alice Cooper"), "AC")
        self.assertEqual(_initials("Single"), "S")
        self.assertEqual(_status_key("To Do"), "todo")
        self.assertEqual(_status_key("In Progress"), "in_progress")

    def test_summary_response_shape(self):
        response = TeamSummaryResponse(
            team_leaders=3,
            employees=8,
            total_projects=35,
            active_projects=8,
        )
        self.assertEqual(response.model_dump(), {
            "team_leaders": 3,
            "employees": 8,
            "total_projects": 35,
            "active_projects": 8,
        })

    def test_member_card_serializes_task_status(self):
        member = SimpleNamespace(id=7, name="Alice Cooper", designation="Engineer", role_name="employee")
        task = SimpleNamespace(id=15, task_name="Implement fix", assignee_id=7, status_id=2)
        task_status = SimpleNamespace(id=2, name="In Progress", color="#2563EB")

        response = TeamsService._member_card(
            None,
            member,
            13,
            [task],
            {2: task_status},
            set(),
        )

        validated = TeamMemberCardResponse.model_validate(response)
        self.assertEqual(validated.tasks[0].status.model_dump(), {
            "id": 2,
            "name": "In Progress",
            "color": "#2563EB",
        })


if __name__ == "__main__":
    unittest.main()
