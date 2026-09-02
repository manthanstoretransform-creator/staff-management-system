import json
from typing import Optional


def error_detail(response_body: Optional[str], fallback: str = "") -> str:
    """
    Pull the backend's own explanation out of an error response body.

    FastAPI answers a rejected request with ``{"detail": ...}`` -- a string
    for an HTTPException, a list of field errors for a schema failure. Both
    say something the user can act on ("Task assignee must be assigned to
    this project"), and both were being thrown away in favour of "Server
    error (HTTP 400)", which told the user nothing and cost a production
    debugging session.

    Never raises: a body that is not JSON, or not shaped as expected, returns
    `fallback` rather than turning an error path into a second error.
    """
    if not response_body:
        return fallback
    try:
        payload = json.loads(response_body)
    except (ValueError, TypeError):
        text = str(response_body).strip()
        return text[:300] if text else fallback

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, list):
        # 422: one line per rejected field, e.g. "body.assignee_id: field required".
        messages = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            location = ".".join(str(part) for part in item.get("loc", []) if part != "body")
            message = str(item.get("msg", "")).strip()
            messages.append(f"{location}: {message}" if location else message)
        joined = "; ".join(m for m in messages if m)
        if joined:
            return joined[:300]
    return fallback


class ApiError(Exception):
    """Base exception class for all SMS Desktop API client errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ApiConnectionError(ApiError):
    """Raised when there is a connection failure or network error."""
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.original_exception = original_exception


class ApiTimeoutError(ApiError):
    """Raised when an API request times out."""
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.original_exception = original_exception


class ApiHttpError(ApiError):
    """Raised when the API returns an HTTP error response (status code >= 400)."""
    
    def __init__(self, status_code: int, response_body: str, message: str = "HTTP error response") -> None:
        formatted_message = f"{message} (Status: {status_code}): {response_body}"
        super().__init__(formatted_message, status_code=status_code)
        self.status_code = status_code
        self.response_body = response_body
