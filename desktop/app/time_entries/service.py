from typing import Optional, Dict, Any
from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError

class TimeEntryService:
    """Service layer coordinating communication with backend time entry endpoints."""

    def __init__(self, api_client: ApiClient) -> None:
        """
        Initialize TimeEntryService.
        
        :param api_client: Shared ApiClient instance.
        """
        self.api_client = api_client

    def start_time_entry(self, project_id: int, task_id: int) -> int:
        """
        Create a new time entry on the backend for the selected project and task.
        
        :param project_id: Project identifier.
        :param task_id: Task identifier.
        :raises ApiError: On session expiry (401), active timer conflict (409), validation errors, or network drop.
        :return: Created time entry database ID.
        """
        payload = {
            "project_id": project_id,
            "task_id": task_id,
            "description": None,
            "is_billable": None
        }
        try:
            response = self.api_client.post("/time-entries/start", json_data=payload)
            data = response.json()
            entry_id = data.get("id")
            if not entry_id:
                raise ApiError("Successfully communicated with backend, but response was missing time entry ID.")
            return entry_id
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 409:
                raise ApiError("User already has an active timer.", status_code=409)
            if e.status_code == 422:
                raise ApiError("Validation error occurred during time entry start.", status_code=422)
            raise ApiError(f"Failed to start timer on backend: HTTP {e.status_code}.", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to start timer: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to start timer: {str(e)}")

    def stop_time_entry(self, entry_id: int, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Stop/finalize the specified active time entry on the backend.
        
        :param entry_id: Time entry database ID.
        :param timeout: Optional custom timeout in seconds.
        :raises ApiError: On session expiry (401), timer not found (404), already stopped (409), or network drop.
        :return: Response dictionary of finalized time entry details.
        """
        payload = {
            "description": None
        }
        try:
            response = self.api_client.post(f"/time-entries/{entry_id}/stop", json_data=payload, timeout=timeout)
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 404:
                raise ApiError("Active timer not found on backend.", status_code=404)
            if e.status_code == 409:
                raise ApiError("Timer is already stopped.", status_code=409)
            raise ApiError(f"Failed to stop timer on backend: HTTP {e.status_code}.", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to stop timer: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to stop timer: {str(e)}")
