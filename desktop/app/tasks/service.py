from typing import List, Dict, Any, Optional
from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError

class TaskService:
    """Service responsible for managing project tasks via the backend API."""

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
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 404:
                raise ApiError("Project not found or access denied.", status_code=404)
            raise ApiError(f"Failed to load tasks: Server error (HTTP {e.status_code}).", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to load tasks: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to load tasks: {str(e)}")

    def create_task(self, project_id: int, task_name: str, description: Optional[str] = None, estimated_hours: Optional[float] = None, is_duplicate: bool = False) -> Dict[str, Any]:
        """
        Create a new task nested under the specified project.
        """
        payload = {
            "task_name": task_name,
            "description": description,
            "estimated_hours": estimated_hours,
            "is_duplicate": is_duplicate,
            "start_date": None,
            "due_date": None,
            "assignee_id": None
        }
        try:
            response = self.api_client.post(f"/projects/{project_id}/tasks", json_data=payload)
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 403:
                raise ApiError("Forbidden: You do not have permission to create tasks.", status_code=403)
            raise ApiError(f"Failed to create task: Server error (HTTP {e.status_code}).", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to create task: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to create task: {str(e)}")

    def update_task(self, project_id: int, task_id: int, task_name: str, description: Optional[str] = None, estimated_hours: Optional[float] = None) -> Dict[str, Any]:
        """
        Update an existing task.
        """
        payload = {
            "task_name": task_name,
            "description": description,
            "estimated_hours": estimated_hours
        }
        try:
            response = self.api_client.put(f"/projects/{project_id}/tasks/{task_id}", json_data=payload)
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 403:
                raise ApiError("Forbidden: You do not have permission to update tasks.", status_code=403)
            raise ApiError(f"Failed to update task: Server error (HTTP {e.status_code}).", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to update task: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to update task: {str(e)}")

    def delete_task(self, project_id: int, task_id: int) -> Dict[str, Any]:
        """
        Archive (delete) an existing task.
        """
        try:
            response = self.api_client.patch(f"/projects/{project_id}/tasks/{task_id}/archive")
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 403:
                raise ApiError("Forbidden: You do not have permission to delete tasks.", status_code=403)
            raise ApiError(f"Failed to delete task: Server error (HTTP {e.status_code}).", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to delete task: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to delete task: {str(e)}")
