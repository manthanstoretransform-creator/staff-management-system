from typing import Optional, Dict, Any

class SessionManager:
    """Manages the current user authentication session and profile metadata.
    
    Supports optional persistence via LocalCache for crash recovery.
    When a LocalCache instance is provided, session data is persisted to SQLite
    and can be restored on startup without requiring re-authentication.
    """

    def __init__(self, local_cache=None) -> None:
        """
        Initialize SessionManager.
        
        :param local_cache: Optional LocalCache instance for persistence.
        """
        self._access_token: Optional[str] = None
        self._user_info: Optional[Dict[str, Any]] = None
        self._local_cache = local_cache

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
        Also persists to SQLite cache if available.
        
        :param token: JWT Access Token.
        :param user_info: User profile dictionary.
        """
        self._access_token = token
        self._user_info = user_info
        # Persist for crash recovery
        if self._local_cache:
            try:
                self._local_cache.save_session(token, user_info)
            except Exception:
                pass  # Persistence failure should not break login flow

    def restore_session(self) -> bool:
        """
        Attempt to restore a session from the local cache.
        
        :return: True if a session was successfully restored, False otherwise.
        """
        if not self._local_cache:
            return False
        try:
            session_data = self._local_cache.load_session()
            if session_data:
                self._access_token = session_data["access_token"]
                self._user_info = session_data["user_info"]
                return True
        except Exception:
            pass
        return False

    def clear(self) -> None:
        """Clear session parameters (logout). Also clears persisted session."""
        self._access_token = None
        self._user_info = None
        if self._local_cache:
            try:
                self._local_cache.clear_session()
                self._local_cache.clear_app_state()
            except Exception:
                pass
