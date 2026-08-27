import unittest
from unittest.mock import patch, MagicMock
import httpx
import sys
import os

# Inject current desktop directory to sys.path so app module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.client import ApiClient
from app.api.exceptions import ApiConnectionError, ApiTimeoutError, ApiHttpError
from app.config import settings

class TestApiClient(unittest.TestCase):
    """Unit test suite for the desktop ApiClient."""

    def test_base_url_loading_and_normalization(self) -> None:
        # Verify base URL is loaded correctly from settings
        client = ApiClient()
        expected_base = settings.SMS_API_BASE_URL.rstrip("/")
        self.assertEqual(client.base_url, expected_base)

        # Verify base URL trailing slash normalization works
        client_custom = ApiClient(base_url="http://localhost:9000/")
        self.assertEqual(client_custom.base_url, "http://localhost:9000")

    def test_default_base_url_is_the_live_backend(self) -> None:
        """
        A shipped desktop client must point somewhere it can actually reach.

        The default used to be http://localhost:8000, so a fresh install on a
        staff machine -- where no local backend exists -- could never connect
        and reported the server unreachable despite working internet.
        """
        import os as _os
        from app.config import LIVE_API_BASE_URL

        self.assertTrue(LIVE_API_BASE_URL.startswith("https://"))
        if not _os.getenv("SMS_API_BASE_URL"):
            self.assertEqual(settings.SMS_API_BASE_URL, LIVE_API_BASE_URL)

    def test_desktop_base_url_has_no_api_v1_suffix(self) -> None:
        """
        The desktop calls bare paths (/auth/me, /projects). Appending /api/v1
        to the base would produce /api/v1/auth/me for some calls and double
        prefixes for others.
        """
        from app.config import LIVE_API_BASE_URL

        self.assertFalse(LIVE_API_BASE_URL.rstrip("/").endswith("/api/v1"))

    def test_url_construction_no_double_slashes(self) -> None:
        client = ApiClient(base_url="http://localhost:8000/")
        
        # Test paths with and without leading slash
        url_with_slash = client._build_url("/auth/me")
        url_without_slash = client._build_url("auth/me")
        
        self.assertEqual(url_with_slash, "http://localhost:8000/auth/me")
        self.assertEqual(url_without_slash, "http://localhost:8000/auth/me")

    def test_headers_and_authorization_token(self) -> None:
        client = ApiClient()
        
        # Test headers before token is configured
        headers_no_token = client._prepare_headers()
        self.assertNotIn("Authorization", headers_no_token)
        self.assertEqual(headers_no_token["Content-Type"], "application/json")

        # Test Bearer header injection when access token is set
        client.access_token = "mocked_jwt_token_xyz"
        headers_with_token = client._prepare_headers()
        self.assertEqual(headers_with_token["Authorization"], "Bearer mocked_jwt_token_xyz")

        # Test custom headers merging preserves token and appends new keys
        custom = {"X-Request-ID": "test-uuid"}
        headers_merged = client._prepare_headers(custom_headers=custom)
        self.assertEqual(headers_merged["Authorization"], "Bearer mocked_jwt_token_xyz")
        self.assertEqual(headers_merged["X-Request-ID"], "test-uuid")

    @patch("httpx.Client.request")
    def test_http_status_errors(self, mock_request: MagicMock) -> None:
        # Mock HTTP 404 response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        # Setup raise_for_status to trigger status error
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="404 Client Error",
            request=MagicMock(),
            response=mock_response
        )
        mock_request.return_value = mock_response

        client = ApiClient(base_url="http://localhost:8000")
        
        with self.assertRaises(ApiHttpError) as context:
            client.get("/invalid-endpoint")
        
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.response_body, "Not Found")

    @patch("httpx.Client.request")
    def test_timeout_error(self, mock_request: MagicMock) -> None:
        # Mock Timeout exception thrown by httpx client
        mock_request.side_effect = httpx.TimeoutException("Read timeout", request=MagicMock())

        client = ApiClient()
        with self.assertRaises(ApiTimeoutError):
            client.get("/timeout-trigger")

    @patch("httpx.Client.request")
    def test_connection_error(self, mock_request: MagicMock) -> None:
        # Mock Network connection error thrown by httpx client
        mock_request.side_effect = httpx.ConnectError("Connection refused", request=MagicMock())

        client = ApiClient()
        with self.assertRaises(ApiConnectionError):
            client.get("/connect-refused")

if __name__ == "__main__":
    unittest.main()
