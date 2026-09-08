"""
Opening the web client as the user who is signed in here.

The desktop client already holds a Monitra session, but a browser knows
nothing about it. Rather than asking the user to sign in a second time, the
"Profile" action asks the backend for a single-use handoff token and opens the
web client with it in the URL; the web client exchanges it for its own session
and lands on the dashboard.

Two things this deliberately does not do:

* It does not put the desktop's own access or refresh token in the URL. Those
  live for the whole session; a URL is written to browser history.
* It does not fabricate a signed-in state. If the handoff cannot be minted --
  offline, expired session, misconfigured build -- the caller opens the plain
  web URL and the user sees the login screen, which is the truth.
"""
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from app.api.client import ApiClient, TIMEOUT_NORMAL
from app.api.exceptions import (
    ApiConnectionError, ApiError, ApiHttpError, ApiTimeoutError, error_detail,
)
from app.config import settings
from core.logging_setup import get_logger

log = get_logger("portal.api")


def build_web_url(
    base_url: str,
    token: Optional[str] = None,
    route: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> str:
    """The web client URL, carrying `?token=` only when there is one.

    Kept a plain function so the URL shape can be asserted without a network,
    and so the no-token case is the same code path as the signed-in one.

    `route` deep-links into the web client — the Activity panel's "View in
    Profile" buttons send the user to the page for the tab and date they were
    looking at, rather than to the dashboard to find it themselves. It is
    appended to whatever path the configured base URL already has, so a build
    served from a sub-path still resolves.

    The route survives the handoff: the web client removes only the `token`
    parameter from the address bar and leaves the path and the remaining query
    untouched, so `?start=`/`?end=` arrive at the page intact.
    """
    scheme, netloc, path, query, fragment = urlsplit(base_url.rstrip("/"))
    if route:
        path = (path or "").rstrip("/") + "/" + route.lstrip("/")
    extra: Dict[str, Any] = dict(params or {})
    if token:
        # Last, so the credential is not buried in the middle of the query.
        extra["token"] = token
    if extra:
        query = "&".join(part for part in (query, urlencode(extra)) if part)
    return urlunsplit((scheme, netloc, path or "/", query, fragment))


class PortalService:
    """Client for the backend's desktop → web sign-in handoff."""

    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    @property
    def web_app_url(self) -> str:
        """The configured web client, or "" when this build has none."""
        return settings.WEB_APP_URL

    def create_handoff_token(self) -> str:
        """Mint a single-use token for the current session.

        Raises `ApiError` with a user-presentable message on every failure, so
        the caller can decide between "open signed in" and "open the login
        page" without reading HTTP status codes.
        """
        try:
            response = self.api_client.post(
                "/auth/sso/handoff",
                json_data={},
                timeout=TIMEOUT_NORMAL,
            )
            token = (response.json() or {}).get("token")
        except ApiHttpError as exc:
            if exc.status_code in (401, 403):
                raise ApiError(
                    "Your session has expired. Please sign in again.",
                    status_code=exc.status_code,
                )
            log.warning("handoff token request failed: HTTP %s", exc.status_code)
            raise ApiError(
                error_detail(
                    exc.response_body,
                    "Could not open the web dashboard. Please try again.",
                ),
                status_code=exc.status_code,
            )
        except ApiTimeoutError:
            raise ApiError("Opening the web dashboard timed out. Please try again.")
        except ApiConnectionError:
            raise ApiError(
                "Unable to reach the server. Please check your internet "
                "connection and try again."
            )
        except ApiError:
            raise
        except Exception:  # noqa: BLE001
            log.warning("handoff token request failed unexpectedly", exc_info=True)
            raise ApiError("Could not open the web dashboard. Please try again.")

        if not isinstance(token, str) or not token.strip():
            log.warning("handoff response carried no token")
            raise ApiError("Could not open the web dashboard. Please try again.")
        return token.strip()
