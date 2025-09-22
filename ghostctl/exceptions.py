"""Exception classes for Ghost CMS CLI.

This module defines custom exception classes used throughout the application
for proper error handling and user feedback.
"""

from typing import Optional, Dict, Any


class GhostCtlError(Exception):
    """Base exception class for all Ghost CMS CLI errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigError(GhostCtlError):
    """Exception raised for configuration-related errors."""
    pass


class AuthenticationError(GhostCtlError):
    """Exception raised for authentication-related errors."""
    pass


class TokenExpiredError(AuthenticationError):
    """Exception raised when JWT token has expired."""
    pass


class MaxRetriesExceededError(GhostCtlError):
    """Exception raised when maximum retry attempts are exceeded."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            attempts: Number of attempts made
            last_exception: The last exception that caused the failure
        """
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


class CircuitBreakerOpenError(GhostCtlError):
    """Exception raised when circuit breaker is open."""
    pass


class ValidationError(GhostCtlError):
    """Exception raised for data validation errors."""
    pass


class APIError(GhostCtlError):
    """Base exception for API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            response_data: Raw response data from API
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class BadRequestError(APIError):
    """Exception raised for 400 Bad Request errors."""
    pass


class UnauthorizedError(APIError):
    """Exception raised for 401 Unauthorized errors."""
    pass


class ForbiddenError(APIError):
    """Exception raised for 403 Forbidden errors."""
    pass


class NotFoundError(APIError):
    """Exception raised for 404 Not Found errors."""
    pass


class ServerError(APIError):
    """Exception raised for 5xx server errors."""
    pass


class RateLimitError(APIError):
    """Exception raised for 429 Rate Limit errors."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            retry_after: Seconds to wait before retrying
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(message, **kwargs)
        self.retry_after = retry_after