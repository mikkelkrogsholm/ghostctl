"""Utility exception classes for Ghost CMS CLI.

This module provides additional utility exception classes that extend
the base exceptions for specific use cases and enhanced error handling.
"""

from typing import Optional, Dict, Any, List
from ..exceptions import GhostCtlError, APIError, RateLimitError


class BulkOperationError(GhostCtlError):
    """Exception raised when bulk operations partially fail."""

    def __init__(
        self,
        message: str,
        successful_operations: int = 0,
        failed_operations: int = 0,
        failures: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            successful_operations: Number of successful operations
            failed_operations: Number of failed operations
            failures: List of failure details
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.successful_operations = successful_operations
        self.failed_operations = failed_operations
        self.failures = failures or []

    def get_summary(self) -> str:
        """Get a summary of the bulk operation results."""
        total = self.successful_operations + self.failed_operations
        return (
            f"Bulk operation completed: {self.successful_operations}/{total} successful, "
            f"{self.failed_operations} failed"
        )


class ContentValidationError(GhostCtlError):
    """Exception raised for content validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_errors: Optional[List[str]] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            field: Field that failed validation
            value: Value that failed validation
            validation_errors: List of specific validation errors
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        self.validation_errors = validation_errors or []


class FileOperationError(GhostCtlError):
    """Exception raised for file operation errors."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            file_path: Path to the file that caused the error
            operation: Operation that failed (read, write, upload, etc.)
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.operation = operation


class ThemeOperationError(GhostCtlError):
    """Exception raised for theme-related operations."""

    def __init__(
        self,
        message: str,
        theme_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            theme_name: Name of the theme
            operation: Operation that failed (upload, activate, delete, etc.)
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.theme_name = theme_name
        self.operation = operation


class ExportError(GhostCtlError):
    """Exception raised for export operation errors."""

    def __init__(
        self,
        message: str,
        export_type: Optional[str] = None,
        partial_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            export_type: Type of export that failed
            partial_data: Partial data that was exported before failure
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.export_type = export_type
        self.partial_data = partial_data or {}


class ImportError(GhostCtlError):
    """Exception raised for import operation errors."""

    def __init__(
        self,
        message: str,
        import_type: Optional[str] = None,
        line_number: Optional[int] = None,
        processed_items: int = 0,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            import_type: Type of import that failed
            line_number: Line number where import failed
            processed_items: Number of items processed before failure
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.import_type = import_type
        self.line_number = line_number
        self.processed_items = processed_items


class ProfileSwitchError(GhostCtlError):
    """Exception raised when profile switching fails."""

    def __init__(
        self,
        message: str,
        from_profile: Optional[str] = None,
        to_profile: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            from_profile: Profile being switched from
            to_profile: Profile being switched to
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.from_profile = from_profile
        self.to_profile = to_profile


class ConnectionTimeoutError(APIError):
    """Exception raised when connection times out."""

    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            timeout_duration: Duration of timeout in seconds
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.timeout_duration = timeout_duration


class QuotaExceededError(APIError):
    """Exception raised when API quota is exceeded."""

    def __init__(
        self,
        message: str,
        quota_type: Optional[str] = None,
        quota_limit: Optional[int] = None,
        quota_used: Optional[int] = None,
        reset_time: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            quota_type: Type of quota exceeded (requests, storage, etc.)
            quota_limit: Quota limit
            quota_used: Current quota usage
            reset_time: When quota resets
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.quota_type = quota_type
        self.quota_limit = quota_limit
        self.quota_used = quota_used
        self.reset_time = reset_time


class ResourceConflictError(APIError):
    """Exception raised when resource conflicts occur."""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        conflict_field: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            resource_type: Type of resource that conflicts
            resource_id: ID of conflicting resource
            conflict_field: Field that causes conflict
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.conflict_field = conflict_field


class MaintenanceModeError(APIError):
    """Exception raised when Ghost is in maintenance mode."""

    def __init__(
        self,
        message: str = "Ghost CMS is currently in maintenance mode",
        estimated_end_time: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            estimated_end_time: Estimated end time of maintenance
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.estimated_end_time = estimated_end_time


def categorize_error(exception: Exception, context: Optional[Dict[str, Any]] = None) -> GhostCtlError:
    """Categorize a generic exception into a more specific Ghost CLI exception.

    Args:
        exception: The original exception
        context: Additional context about the operation

    Returns:
        A more specific GhostCtlError subclass
    """
    context = context or {}
    error_message = str(exception)

    # Handle common connection errors
    if "timeout" in error_message.lower():
        return ConnectionTimeoutError(
            f"Connection timed out: {error_message}",
            timeout_duration=context.get("timeout"),
        )

    # Handle file errors
    if "file" in error_message.lower() or "path" in error_message.lower():
        return FileOperationError(
            f"File operation failed: {error_message}",
            file_path=context.get("file_path"),
            operation=context.get("operation"),
        )

    # Handle validation errors
    if "validation" in error_message.lower() or "invalid" in error_message.lower():
        return ContentValidationError(
            f"Validation failed: {error_message}",
            field=context.get("field"),
            value=context.get("value"),
        )

    # Handle theme errors
    if "theme" in error_message.lower():
        return ThemeOperationError(
            f"Theme operation failed: {error_message}",
            theme_name=context.get("theme_name"),
            operation=context.get("operation"),
        )

    # Default to generic error
    return GhostCtlError(f"Operation failed: {error_message}")


def format_error_for_user(error: Exception, debug: bool = False) -> str:
    """Format an error message for user display.

    Args:
        error: The exception to format
        debug: Whether to include debug information

    Returns:
        Formatted error message
    """
    if isinstance(error, BulkOperationError):
        message = f"Bulk operation failed: {error.message}\n"
        message += error.get_summary()
        if error.failures and debug:
            message += "\nFailures:\n"
            for failure in error.failures[:5]:  # Show first 5 failures
                message += f"  - {failure}\n"
            if len(error.failures) > 5:
                message += f"  ... and {len(error.failures) - 5} more\n"
        return message

    if isinstance(error, ContentValidationError):
        message = f"Validation error: {error.message}"
        if error.field:
            message += f"\nField: {error.field}"
        if error.validation_errors and debug:
            message += f"\nDetails: {', '.join(error.validation_errors)}"
        return message

    if isinstance(error, FileOperationError):
        message = f"File error: {error.message}"
        if error.file_path:
            message += f"\nFile: {error.file_path}"
        if error.operation:
            message += f"\nOperation: {error.operation}"
        return message

    if isinstance(error, ConnectionTimeoutError):
        message = f"Connection timeout: {error.message}"
        if error.timeout_duration:
            message += f"\nTimeout duration: {error.timeout_duration}s"
        return message

    if isinstance(error, QuotaExceededError):
        message = f"Quota exceeded: {error.message}"
        if error.quota_type and error.quota_limit and error.quota_used:
            message += f"\nQuota: {error.quota_used}/{error.quota_limit} {error.quota_type}"
        if error.reset_time:
            message += f"\nResets at: {error.reset_time}"
        return message

    if isinstance(error, RateLimitError):
        message = f"Rate limit exceeded: {error.message}"
        if hasattr(error, 'retry_after') and error.retry_after:
            message += f"\nRetry after: {error.retry_after} seconds"
        return message

    if isinstance(error, MaintenanceModeError):
        message = f"Maintenance mode: {error.message}"
        if error.estimated_end_time:
            message += f"\nEstimated end time: {error.estimated_end_time}"
        return message

    # For API errors, show status code and response data if available
    if isinstance(error, APIError):
        message = f"API error: {error.message}"
        if error.status_code:
            message += f"\nStatus code: {error.status_code}"
        if error.response_data and debug:
            message += f"\nResponse: {error.response_data}"
        return message

    # Default formatting
    if debug:
        return f"Error: {str(error)}\nType: {type(error).__name__}"
    else:
        return f"Error: {str(error)}"