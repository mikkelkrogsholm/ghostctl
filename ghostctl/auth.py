"""Authentication utilities for Ghost CMS API.

This module re-exports authentication classes for backward compatibility
with test imports.
"""

# Re-export from utils.auth for backward compatibility
from .utils.auth import AuthManager, JWTAuth

__all__ = ["AuthManager", "JWTAuth"]