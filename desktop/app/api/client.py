import httpx
from typing import Any, Dict, Optional
from app.config import settings
from app.api.exceptions import ApiConnectionError, ApiTimeoutError, ApiHttpError

class ApiClient:
    """Reusable synchronous HTTP client for interacting with the SMS backend API."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0) -> None:
        """
        Initialize the API client.
        
        :param base_url: Override base URL. If None, loaded from app configuration.
        :param timeout: Connection/read timeout limit in seconds.
        """
        # Load from configuration if not explicitly provided
        configured_url = base_url or settings.SMS_API_BASE_URL
        # Strip trailing slashes to prevent double-slashes during path joining
        self.base_url: str = configured_url.rstrip("/")
        self.timeout: float = timeout
        self._access_token: Optional[str] = None

    @property
    def access_token(self) -> Optional[str]:
        """Retrieve the currently set Bearer access token."""
        return self._access_token

    @access_token.setter
    def access_token(self, token: Optional[str]) -> None:
        """Set or update the Bearer access token used for requests."""
        self._access_token = token

    def _build_url(self, path: str) -> str:
        """Construct the absolute URL from the base URL and relative path."""
        # Prevent double slashes at the boundary
        clean_path = path.lstrip("/")
        return f"{self.base_url}/{clean_path}"

    def _prepare_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Construct request headers, injecting Authorization headers if an access token is set."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """
        Execute an HTTP request synchronously, mapping httpx errors to custom exceptions.
        
        :param method: HTTP Verb (GET, POST, PUT, PATCH, DELETE).
        :param path: Relative endpoint path.
        :param json_data: JSON request body payload.
        :param params: Query string parameters.
        :param headers: Custom request headers.
        :raises ApiTimeoutError: On connection/read timeouts.
        :raises ApiConnectionError: On network or dns failures.
        :raises ApiHttpError: On non-2xx status responses.
        :return: httpx.Response object.
        """
        url = self._build_url(path)
        req_headers = self._prepare_headers(headers)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    headers=req_headers
                )
                # Triggers httpx.HTTPStatusError if response is 4xx or 5xx
                response.raise_for_status()
                return response

        except httpx.TimeoutException as e:
            raise ApiTimeoutError(f"Request to {url} timed out.", original_exception=e)
            
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise ApiConnectionError(f"Network error trying to connect to {url}.", original_exception=e)
            
        except httpx.HTTPStatusError as e:
            raise ApiHttpError(
                status_code=e.response.status_code,
                response_body=e.response.text,
                message=f"API responded with status code {e.response.status_code}"
            )
            
        except Exception as e:
            # Fallback for unexpected failures (e.g. malformed responses)
            raise ApiConnectionError(f"Unexpected connection error occurred while querying {url}.", original_exception=e)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Execute a GET request."""
        return self.request("GET", path, params=params, headers=headers)

    def post(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Execute a POST request."""
        return self.request("POST", path, json_data=json_data, params=params, headers=headers)

    def put(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Execute a PUT request."""
        return self.request("PUT", path, json_data=json_data, params=params, headers=headers)

    def patch(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Execute a PATCH request."""
        return self.request("PATCH", path, json_data=json_data, params=params, headers=headers)

    def delete(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Execute a DELETE request."""
        return self.request("DELETE", path, json_data=json_data, params=params, headers=headers)
