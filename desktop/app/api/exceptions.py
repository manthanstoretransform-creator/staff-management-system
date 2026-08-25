from typing import Optional

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
