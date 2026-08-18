from typing import List, Dict, Any
from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError

class ProjectService:
    """Service responsible for fetching projects from the backend API."""

    def __init__(self, api_client: ApiClient) -> None:
        """
        Initialize ProjectService.
        
        :param api_client: Shared instance of ApiClient.
        """
        self.api_client = api_client

    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Fetch all active projects scoped to the current user's organization and membership.
        
        :raises ApiError: On session expiry (401), server error, or connection issues.
        :return: List of project dictionaries.
        """
        try:
            response = self.api_client.get("/projects")
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.")
            raise ApiError(f"Failed to load projects: Server error (HTTP {e.status_code}).")
        except ApiConnectionError:
            raise ApiError("Failed to load projects: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to load projects: {str(e)}")
