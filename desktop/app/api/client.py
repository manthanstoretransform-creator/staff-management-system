import httpx
import logging
import sys
import uuid
import threading
from typing import Any, Callable, Dict, Optional
from app.config import settings
from app.api.exceptions import ApiConnectionError, ApiError, ApiTimeoutError, ApiHttpError
from version import user_agent

log = logging.getLogger(__name__)

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

        # Silent re-authentication. The hook is installed by the runtime and
        # renews the access token from the stored refresh token; the lock makes
        # it single-flight, so a burst of 401s from several service threads
        # produces one refresh rather than one per caller.
        self._refresh_hook: Optional[Callable[[], bool]] = None
        self._refresh_lock = threading.Lock()

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
            # Identify this build on every call. `version.py` is the single
            # source of truth for the string, and the backend reads it to know
            # which desktop version each user is running -- which is what makes
            # "did everyone move off the bad build?" answerable rather than a
            # question support has to ask each person individually.
            "User-Agent": user_agent(),
            # Windows and macOS ship as separate artifacts, so a rollout can be
            # complete on one platform and not the other. Sent alongside the
            # version so the fleet view can tell them apart.
            "X-Monitra-Platform": sys.platform,
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def set_refresh_hook(self, hook: Optional[Callable[[], bool]]) -> None:
        """Install the callable that renews an expired access token.

        Wired by the runtime rather than constructed here: the client must not
        know what a session is, and AuthService already owns that. The hook
        returns True when a new token is in place, and raises
        SessionExpiredError when the session is genuinely over -- which
        propagates to the caller unchanged, so the UI still sees one clear
        signal to return to the login screen.
        """
        self._refresh_hook = hook

    def request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        skip_auth_refresh: bool = False,
    ) -> httpx.Response:
        """
        Execute an HTTP request using the persistent connection pool.

        A 401 is retried exactly once, after a silent token refresh. The retry
        is deliberately capped at one attempt: if the renewed token is also
        rejected, the session is over and hammering the endpoint would only
        delay telling the user so.

        When the refresh does not succeed, the caller sees the original
        ApiHttpError(401) -- not a new exception type. Every 401 handler in the
        app (SyncService's auth_required, the dashboard's unauthorized_error,
        startup verification) was already written against that, and the domain
        services in between catch broadly enough that a new type would be
        flattened into a generic message and lose the status code entirely.

        :param method: HTTP Verb (GET, POST, PUT, PATCH, DELETE).
        :param path: Relative endpoint path.
        :param json_data: JSON request body payload.
        :param params: Query string parameters.
        :param headers: Custom request headers.
        :param timeout: Override timeout for this specific request.
        :param skip_auth_refresh: Do not attempt a refresh on 401. Set by the
            auth endpoints themselves, which would otherwise recurse.
        :raises ApiTimeoutError: On connection/read timeouts.
        :raises ApiConnectionError: On network or dns failures.
        :raises ApiHttpError: On non-2xx status responses.
        :raises SessionExpiredError: When the session could not be renewed.
        :return: httpx.Response object.
        """
        token_used = self._access_token
        try:
            return self._execute(method, path, json_data, params, headers, timeout)
        except ApiHttpError as e:
            if e.status_code != 401 or skip_auth_refresh or self._refresh_hook is None:
                raise
            if not self._refresh_once(token_used):
                raise
        # One retry, now carrying the renewed token.
        return self._execute(method, path, json_data, params, headers, timeout)

    def _refresh_once(self, token_used: Optional[str]) -> bool:
        """Renew the access token, at most one refresh at a time.

        Threads that arrive while a refresh is in flight wait for it and then
        reuse its result: whoever gets the lock second finds the token already
        changed and retries with it instead of refreshing again. Several
        services hit 401 within the same second when a token expires, and a
        refresh per caller would rotate the refresh token out from under the
        others -- each rotation invalidating the token the next one is about to
        present, turning one expiry into a cascade of false sign-outs.
        """
        with self._refresh_lock:
            if self._access_token != token_used:
                return True  # another thread already renewed it
            hook = self._refresh_hook
            if hook is None:
                return False
            log.info("access token rejected; attempting silent refresh")
            try:
                return bool(hook())
            except ApiError as exc:
                # Includes SessionExpiredError. Reported as "could not refresh"
                # so the caller re-raises the 401 it already has; the session
                # itself is torn down by whoever handles that 401.
                log.info("silent refresh did not succeed (%s)", exc)
                return False

    def _execute(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Perform one HTTP round trip. No retry, no auth handling."""
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

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, skip_auth_refresh: bool = False) -> httpx.Response:
        """Execute a GET request."""
        return self.request("GET", path, params=params, headers=headers, timeout=timeout, skip_auth_refresh=skip_auth_refresh)

    def post(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, skip_auth_refresh: bool = False) -> httpx.Response:
        """Execute a POST request."""
        return self.request("POST", path, json_data=json_data, params=params, headers=headers, timeout=timeout, skip_auth_refresh=skip_auth_refresh)

    def put(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, skip_auth_refresh: bool = False) -> httpx.Response:
        """Execute a PUT request."""
        return self.request("PUT", path, json_data=json_data, params=params, headers=headers, timeout=timeout, skip_auth_refresh=skip_auth_refresh)

    def patch(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, skip_auth_refresh: bool = False) -> httpx.Response:
        """Execute a PATCH request."""
        return self.request("PATCH", path, json_data=json_data, params=params, headers=headers, timeout=timeout, skip_auth_refresh=skip_auth_refresh)

    def delete(self, path: str, json_data: Optional[Any] = None, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, skip_auth_refresh: bool = False) -> httpx.Response:
        """Execute a DELETE request."""
        return self.request("DELETE", path, json_data=json_data, params=params, headers=headers, timeout=timeout, skip_auth_refresh=skip_auth_refresh)

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
