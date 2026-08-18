from typing import List, Dict, Any
from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError

class TaskService:
    """Service responsible for fetching project tasks from the backend API."""

    def __init__(self, api_client: ApiClient) -> None:
        """
        Initialize TaskService.
        
        :param api_client: Shared instance of ApiClient.
        """
        self.api_client = api_client

    def get_tasks_for_project(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Fetch tasks nested under the specified project.
        
        :param project_id: Project identifier.
        :raises ApiError: On session expiry (401), missing project (404), or network failures.
        :return: List of task dictionaries.
        """
        try:
            response = self.api_client.get(f"/projects/{project_id}/tasks")
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.")
            if e.status_code == 404:
                raise ApiError("Project not found or access denied.")
            raise ApiError(f"Failed to load tasks: Server error (HTTP {e.status_code}).")
        except ApiConnectionError:
            raise ApiError("Failed to load tasks: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to load tasks: {str(e)}")
        
