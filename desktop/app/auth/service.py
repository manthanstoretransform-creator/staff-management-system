import json
from typing import Dict, Any, Optional
from app.api.client import ApiClient, TIMEOUT_FAST
from app.api.exceptions import (
    ApiError,
    ApiHttpError,
    ApiConnectionError,
    SessionExpiredError,
    SESSION_EXPIRED_MESSAGE,
)
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
            response = self.api_client.post("/auth/login", json_data=payload, skip_auth_refresh=True)
            token_data = response.json()
            
            access_token = token_data.get("access_token")
            if not access_token:
                raise ApiError("Authentication succeeded but no access token was returned.")

            # 2. Attach access token to the API client immediately so /auth/me is authorized
            self.api_client.access_token = access_token

            # 3. Query /auth/me to verify token works and fetch latest profile fields
            me_response = self.api_client.get("/auth/me")
            user_data = me_response.json()

            # 4. Initialize session, including the sign-in window the backend
            #    just opened. This is the only place a new window starts.
            self.session_manager.start_session(
                access_token,
                user_data,
                refresh_token=token_data.get("refresh_token"),
                session_created_at=token_data.get("session_created_at"),
                session_expires_at=token_data.get("session_expires_at"),
            )
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

    def refresh_session(self) -> bool:
        """Renew the access token from the stored refresh token.

        Returns True when a new access token is in place. Returns False without
        touching stored credentials when the session simply could not be renewed
        right now -- no refresh token held, or the backend unreachable. The
        caller must not read False as "log the user out": only
        `SessionExpiredError` means the session is genuinely over.

        :raises SessionExpiredError: the backend refused the refresh token, so
            the session is finished and local state must be cleared.
        """
        refresh_token = self.session_manager.refresh_token
        if not refresh_token:
            return False

        try:
            response = self.api_client.post(
                "/auth/refresh",
                json_data={"refresh_token": refresh_token},
                skip_auth_refresh=True,
            )
        except ApiHttpError as e:
            if e.status_code in (400, 401, 403):
                # A definite answer from the backend: expired, revoked, or the
                # account is gone. This is the one path that ends the session.
                raise SessionExpiredError(SESSION_EXPIRED_MESSAGE)
            # 5xx and everything else is the server having a bad time, not a
            # verdict on this session. Keep the credentials and try later.
            return False
        except ApiError:
            # Timeout, DNS failure, connection refused: offline, not signed out.
            return False

        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return False

        self.api_client.access_token = access_token
        # The window is carried through from the response; the backend refuses
        # to extend it past the original sign-in, so this cannot create an
        # endless session even though it runs on every renewal.
        self.session_manager.start_session(
            access_token,
            token_data.get("user") or self.session_manager.user_info or {},
            refresh_token=token_data.get("refresh_token"),
            session_created_at=token_data.get("session_created_at"),
            session_expires_at=token_data.get("session_expires_at"),
        )
        return True

    def logout(self) -> None:
        """Clear active user sessions and discard stored authentication tokens.

        The backend is told first, so the refresh token stops working for anyone
        who has a copy of it -- but a failure to reach it never blocks the local
        clear. Signing out must work offline; a session the user has ended is
        ended on this machine regardless of what the network says.
        """
        refresh_token = self.session_manager.refresh_token
        if refresh_token:
            try:
                self.api_client.post(
                    "/auth/logout",
                    json_data={"refresh_token": refresh_token},
                    timeout=TIMEOUT_FAST,
                    skip_auth_refresh=True,
                )
            except Exception:
                pass

        self.session_manager.clear()
        self.api_client.access_token = None
