import json
from typing import Dict, Any, Optional
from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError
from app.auth.session import SessionManager

class AuthService:
    """Service layer that coordinates user authentication and profile synchronization."""

    def __init__(self, api_client: ApiClient, session_manager: SessionManager) -> None:
        """
        Initialize AuthService.
        
        :param api_client: Shared instance of ApiClient.
        :param session_manager: Shared instance of SessionManager.
        """
        self.api_client = api_client
        self.session_manager = session_manager

    def login(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """
        Attempt to authenticate against the backend.
        
        On success, updates ApiClient's token, fetches profile from /auth/me,
        and populates the session.
        
        :param username_or_email: Username or email string.
        :param password: Password string.
        :raises ApiError: For authentication failures or connection issues.
        :return: Mapped user profile dictionary.
        """
        if not username_or_email.strip() or not password:
            raise ApiError("Username/email and password cannot be empty.")

        payload = {
            "username": username_or_email.strip(),
            "password": password
        }

        try:
            # 1. Exchange credentials for JWT token pair
            response = self.api_client.post("/auth/login", json_data=payload)
            token_data = response.json()
            
            access_token = token_data.get("access_token")
            if not access_token:
                raise ApiError("Authentication succeeded but no access token was returned.")

            # 2. Attach access token to the API client immediately so /auth/me is authorized
            self.api_client.access_token = access_token

            # 3. Query /auth/me to verify token works and fetch latest profile fields
            me_response = self.api_client.get("/auth/me")
            user_data = me_response.json()

            # 4. Initialize session
            self.session_manager.start_session(access_token, user_data)
            return user_data

        except ApiHttpError as e:
            # Parse HTTP authentication failures (like 401 Unauthorized)
            if e.status_code in (400, 401):
                error_msg = "Incorrect username/email or password."
                try:
                    # Attempt to extract precise details if returned by backend
                    body_json = json.loads(e.response_body)
                    detail = body_json.get("detail", "")
                    if isinstance(detail, dict):
                        error_msg = detail.get("message", error_msg)
                    elif isinstance(detail, str):
                        error_msg = detail
                except Exception:
                    pass
                raise ApiError(error_msg)
            else:
                raise ApiError(f"Server error during authentication (HTTP {e.status_code}).")

        except ApiConnectionError as e:
            raise ApiError("Network connection failure. Could not reach the authentication server.")

        except ApiError as e:
            # Re-raise known API exceptions
            raise e

        except Exception as e:
            # Fallback for unexpected system errors
            raise ApiError(f"An unexpected authentication error occurred: {str(e)}")

    def logout(self) -> None:
        """Clear active user sessions and discard stored authentication tokens."""
        self.session_manager.clear()
        self.api_client.access_token = None
