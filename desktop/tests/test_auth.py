import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Inject current desktop directory to sys.path so app module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.client import ApiClient
from app.api.exceptions import ApiHttpError, ApiConnectionError, ApiError
from app.auth.session import SessionManager
from app.auth.service import AuthService

class TestAuthService(unittest.TestCase):
    """Unit test suite for the authentication service and session manager."""

    def setUp(self) -> None:
        # Mock ApiClient to isolate service tests from real HTTP calls
        self.api_client = MagicMock(spec=ApiClient)
        self.api_client.access_token = None
        self.session_manager = SessionManager()
        self.auth_service = AuthService(self.api_client, self.session_manager)

    def test_successful_login(self) -> None:
        # 1. Setup mock response for credentials verification
        login_response = MagicMock()
        login_response.json.return_value = {
            "access_token": "mocked_jwt_token_123",
            "refresh_token": "mocked_refresh_123",
            "token_type": "bearer",
            "user": {
                "id": 36,
                "name": "Hardik Raval",
                "email": "hardik@example.com",
                "role_name": "employee",
                "organization_id": 1
            }
        }
        self.api_client.post.return_value = login_response

        # 2. Setup mock response for /auth/me user verification
        me_response = MagicMock()
        me_response.json.return_value = {
            "id": 36,
            "name": "Hardik Raval",
            "email": "hardik@example.com",
            "role_name": "employee",
            "organization_id": 1,
            "username": "hardik",
            "designation": "Developer",
            "permissions": {"projects:view": True},
            "capture_frequency": 600,
            "is_active": True
        }
        self.api_client.get.return_value = me_response

        # Act
        user_info = self.auth_service.login("hardik@example.com", "developer_st_performance")

        # Assertions
        # Verify ApiClient was invoked with correct arguments
        self.api_client.post.assert_called_once_with(
            "/auth/login",
            json_data={"username": "hardik@example.com", "password": "developer_st_performance"}
        )
        self.api_client.get.assert_called_once_with("/auth/me")
        
        # Verify the access token is attached to the API client for subsequent queries
        self.assertEqual(self.api_client.access_token, "mocked_jwt_token_123")
        
        # Verify the session manager is populated correctly
        self.assertTrue(self.session_manager.is_authenticated)
        self.assertEqual(self.session_manager.access_token, "mocked_jwt_token_123")
        self.assertEqual(self.session_manager.user_info, me_response.json.return_value)
        self.assertEqual(user_info, me_response.json.return_value)

    def test_invalid_credentials_throwing_http_error(self) -> None:
        # Mock bad credential response (401 Unauthorized)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"detail": "Incorrect username/email or password."}'
        
        self.api_client.post.side_effect = ApiHttpError(
            status_code=401,
            response_body=mock_response.text,
            message="Unauthorized"
        )

        # Act & Assert
        with self.assertRaises(ApiError) as context:
            self.auth_service.login("bad_user@example.com", "bad_password")

        # Ensure correct error message mapping and session clearance
        self.assertIn("Incorrect username/email or password", str(context.exception))
        self.assertFalse(self.session_manager.is_authenticated)
        self.assertIsNone(self.api_client.access_token)

    def test_api_connection_failure_throws_clean_error(self) -> None:
        # Mock connection drop during request
        self.api_client.post.side_effect = ApiConnectionError("Connection refused")

        with self.assertRaises(ApiError) as context:
            self.auth_service.login("developer", "developer_st_performance")

        self.assertIn("Network connection failure", str(context.exception))
        self.assertFalse(self.session_manager.is_authenticated)

    def test_logout_clears_local_state(self) -> None:
        # Pre-seed authenticated state in session and ApiClient
        self.session_manager.start_session("jwt_access_token_abc", {"id": 36, "name": "Hardik"})
        self.api_client.access_token = "jwt_access_token_abc"

        # Act
        self.auth_service.logout()

        # Assert session state is fully flushed
        self.assertFalse(self.session_manager.is_authenticated)
        self.assertIsNone(self.session_manager.access_token)
        self.assertIsNone(self.session_manager.user_info)
        self.assertIsNone(self.api_client.access_token)

    def test_password_is_not_stored_in_session(self) -> None:
        # Setup mock login success
        login_response = MagicMock()
        login_response.json.return_value = {"access_token": "token", "user": {"id": 36}}
        self.api_client.post.return_value = login_response
        self.api_client.get.return_value = MagicMock()

        # Log in using a secret password
        secret_pass = "extremely_secure_personal_password"
        self.auth_service.login("hardik@example.com", secret_pass)

        # Confirm the password string is not saved or exposed inside session manager memory
        self.assertNotIn("password", self.session_manager.user_info)
        self.assertIsNone(getattr(self.session_manager, "password", None))
        self.assertIsNone(getattr(self.auth_service, "password", None))

if __name__ == "__main__":
    unittest.main()
