import httpx
import uuid
import threading
from typing import Any, Dict, Optional
from app.config import settings
from app.api.exceptions import ApiConnectionError, ApiTimeoutError, ApiHttpError

# Timeout tiers for different operation types
TIMEOUT_FAST = 5.0      # Start/Stop timer
TIMEOUT_NORMAL = 10.0   # Data loading
TIMEOUT_SLOW = 30.0     # Uploads, large queries


class ApiClient:
    """Reusable synchronous HTTP client for interacting with the SMS backend API.
    
    Uses a persistent httpx.Client with connection pooling to avoid
    TCP handshake overhead on every request.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = TIMEOUT_NORMAL) -> None:
        """
        Initialize the API client.
        
        :param base_url: Override base URL. If None, loaded from app configuration.
        :param timeout: Default connection/read timeout limit in seconds.
        """
        # Load from configuration if not explicitly provided
        configured_url = base_url or settings.SMS_API_BASE_URL
        # Strip trailing slashes to prevent double-slashes during path joining
        self.base_url: str = configured_url.rstrip("/")
        self.timeout: float = timeout
        self._access_token: Optional[str] = None
        # Guards only token mutation and client construction — never a request.
        self._lock = threading.Lock()
        self._closed = False

        # Persistent connection pool — reuses TCP connections across requests
        self._client: Optional[httpx.Client] = None
        self._ensure_client()

    def _ensure_client(self) -> None:
        """Create the persistent HTTP client if it does not exist."""
        with self._lock:
            if self._closed or self._client is not None:
                return
            self._client = httpx.Client(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30.0,
                ),
            )

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
            "Accept": "application/json",
            "X-Request-ID": str(uuid.uuid4()),
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
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """
        Execute an HTTP request using the persistent connection pool.
        
        :param method: HTTP Verb (GET, POST, PUT, PATCH, DELETE).
        :param path: Relative endpoint path.
        :param json_data: JSON request body payload.
        :param params: Query string parameters.
        :param headers: Custom request headers.
        :param timeout: Override timeout for this specific request.
        :raises ApiTimeoutError: On connection/read timeouts.
        :raises ApiConnectionError: On network or dns failures.
        :raises ApiHttpError: On non-2xx status responses.
        :return: httpx.Response object.
        """
        url = self._build_url(path)
        req_headers = self._prepare_headers(headers)
        req_timeout = timeout or self.timeout

        if self._closed:
            raise ApiConnectionError(f"Client is closed; refusing request to {url}.")

        client = self._client
        if client is None:
            self._ensure_client()
            client = self._client
        if client is None:
            raise ApiConnectionError(f"Client is closed; refusing request to {url}.")

        try:
            # NOTE: deliberately NOT holding a lock here. httpx.Client is
            # thread-safe and pools connections internally. The previous
            # implementation serialised every HTTP call in the process behind
            # one mutex, so a single slow request blocked the GUI thread, the
            # sync consumer and the network monitor simultaneously — the direct
            # cause of the "loader never resolves" hang.
            response = client.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                headers=req_headers,
                timeout=req_timeout,
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

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> httpx.Response:
        """Execute a GET request."""
        return self.request("GET", path, params=params, headers=headers, timeout=timeout)

    def post(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> httpx.Response:
        """Execute a POST request."""
        return self.request("POST", path, json_data=json_data, params=params, headers=headers, timeout=timeout)

    def put(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> httpx.Response:
        """Execute a PUT request."""
        return self.request("PUT", path, json_data=json_data, params=params, headers=headers, timeout=timeout)

    def patch(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> httpx.Response:
        """Execute a PATCH request."""
        return self.request("PATCH", path, json_data=json_data, params=params, headers=headers, timeout=timeout)

    def delete(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> httpx.Response:
        """Execute a DELETE request."""
        return self.request("DELETE", path, json_data=json_data, params=params, headers=headers, timeout=timeout)

    def close(self) -> None:
        """
        Close the persistent HTTP client and release connection pool resources.

        Idempotent, and one-way: once closed the client refuses further
        requests rather than transparently re-opening a pool during shutdown.
        The runtime calls this only after every service thread has stopped, so
        no request can be in flight at this point.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
