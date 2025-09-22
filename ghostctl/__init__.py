"""Ghost CMS CLI package.

A command-line tool for managing Ghost CMS instances.
Provides functionality for content management, site administration,
and automation of Ghost CMS operations.
"""

__version__ = "0.1.0"
__author__ = "Mikkel Krogsholm"
__email__ = "mikkel@brokk-sindre.dk"
__description__ = "Command-line tool for managing Ghost CMS"

# Re-export main classes for convenience
from .client import GhostClient
from .config import ConfigManager, Profile
from .render import OutputFormatter
from .utils.auth import AuthManager, JWTAuth
from .utils.retry import RetryManager, CircuitBreaker
from .exceptions import (
    GhostCtlError,
    ConfigError,
    AuthenticationError,
    TokenExpiredError,
    MaxRetriesExceededError,
    CircuitBreakerOpenError,
    ValidationError,
    APIError,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ServerError,
    RateLimitError,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    "GhostClient",
    "ConfigManager",
    "Profile",
    "OutputFormatter",
    "AuthManager",
    "JWTAuth",
    "RetryManager",
    "CircuitBreaker",
    "GhostCtlError",
    "ConfigError",
    "AuthenticationError",
    "TokenExpiredError",
    "MaxRetriesExceededError",
    "CircuitBreakerOpenError",
    "ValidationError",
    "APIError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ServerError",
    "RateLimitError",
]