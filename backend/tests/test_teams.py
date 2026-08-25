import unittest

from app.schemas.teams import TeamSummaryResponse, TaskProgressResponse
from app.services.teams import _initials, _percent, _status_key


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


if __name__ == "__main__":
    unittest.main()
