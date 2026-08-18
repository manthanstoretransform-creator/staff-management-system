from typing import Optional, Dict, Any

class SessionManager:
    """Manages the current user authentication session and profile metadata in memory."""

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._user_info: Optional[Dict[str, Any]] = None

    @property
    def is_authenticated(self) -> bool:
        """Check if a session is currently active (token is present)."""
        return self._access_token is not None

    @property
    def access_token(self) -> Optional[str]:
        """Retrieve the current session JWT access token."""
        return self._access_token

    @property
    def user_info(self) -> Optional[Dict[str, Any]]:
        """Retrieve the current logged-in user profile details."""
        return self._user_info

    def start_session(self, token: str, user_info: Dict[str, Any]) -> None:
        """
        Store token and profile information to initiate the session.
        
        :param token: JWT Access Token.
        :param user_info: User profile dictionary.
        """
        self._access_token = token
        self._user_info = user_info

    def clear(self) -> None:
        """Clear session parameters (logout)."""
        self._access_token = None
        self._user_info = None
