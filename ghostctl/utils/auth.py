"""Authentication utilities for Ghost CMS API.

This module provides JWT token generation and management for the Ghost Admin API,
including token caching, validation, and automatic refresh capabilities.
"""

import time
import jwt
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import requests
from requests.exceptions import RequestException

from ..exceptions import AuthenticationError, TokenExpiredError


class JWTAuth:
    """JWT authentication handler for Ghost Admin API."""

    def __init__(self, admin_key: str) -> None:
        """Initialize JWT authentication.

        Args:
            admin_key: Ghost admin API key in format "id:secret"

        Raises:
            AuthenticationError: If admin key format is invalid
        """
        if ":" not in admin_key:
            raise AuthenticationError("Invalid admin key format. Expected format: id:secret")

        parts = admin_key.split(":", 1)
        if len(parts) != 2 or not all(parts):
            raise AuthenticationError("Invalid admin key format. Expected format: id:secret")

        self.key_id, self.secret = parts
        # Decode the secret from hex as required by Ghost API
        self.secret_bytes = bytes.fromhex(self.secret)
        self._token_cache: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        self._cache_stats = {"hits": 0, "misses": 0}

    def generate_token(self, expires_in: int = 300) -> str:
        """Generate a new JWT token.

        Args:
            expires_in: Token expiration time in seconds (default: 5 minutes)

        Returns:
            JWT token string

        Raises:
            AuthenticationError: If token generation fails
        """
        try:
            now = int(time.time())
            header = {
                "alg": "HS256",
                "typ": "JWT",
                "kid": self.key_id
            }
            payload = {
                "iss": self.key_id,
                "aud": "/admin/",
                "iat": now,
                "exp": now + expires_in,
            }

            token = jwt.encode(payload, self.secret_bytes, algorithm="HS256", headers=header)
            return token

        except Exception as e:
            raise AuthenticationError(f"Failed to generate JWT token: {e}")

    def get_valid_token(self, min_remaining: int = 60) -> str:
        """Get a valid JWT token, using cache if available.

        Args:
            min_remaining: Minimum remaining time in seconds before refresh

        Returns:
            Valid JWT token

        Raises:
            AuthenticationError: If token generation fails
        """
        now = time.time()

        # Check if cached token is still valid
        if (
            self._token_cache
            and self._token_expires_at
            and self._token_expires_at - now > min_remaining
        ):
            self._cache_stats["hits"] += 1
            return self._token_cache

        # Generate new token
        self._cache_stats["misses"] += 1
        expires_in = 300  # 5 minutes
        token = self.generate_token(expires_in)

        # Cache the token
        self._token_cache = token
        self._token_expires_at = now + expires_in

        return token

    def validate_token(self, token: Optional[str] = None) -> bool:
        """Validate a JWT token.

        Args:
            token: Token to validate. If None, uses cached token.

        Returns:
            True if token is valid, False otherwise
        """
        if token is None:
            token = self._token_cache

        if not token:
            return False

        try:
            payload = jwt.decode(
                token,
                self.secret_bytes,
                algorithms=["HS256"],
                audience="/admin/",
                issuer=self.key_id
            )

            # Check if token is expired (jwt.decode already checks this, but let's be explicit)
            exp = payload.get("exp", 0)
            if exp < time.time():
                return False

            return True

        except jwt.InvalidTokenError:
            return False

    def invalidate_cache(self) -> None:
        """Invalidate the token cache."""
        self._token_cache = None
        self._token_expires_at = None

    def get_cache_stats(self) -> Dict[str, int]:
        """Get token cache statistics.

        Returns:
            Dictionary with cache hit and miss counts
        """
        return self._cache_stats.copy()


class AuthManager:
    """High-level authentication manager for Ghost CMS API."""

    def __init__(
        self,
        admin_key: Optional[str] = None,
        content_key: Optional[str] = None,
        ghost_url: str = "",
        timeout: int = 30,
    ) -> None:
        """Initialize authentication manager.

        Args:
            admin_key: Ghost admin API key
            content_key: Ghost content API key
            ghost_url: Ghost CMS instance URL
            timeout: Request timeout in seconds

        Raises:
            AuthenticationError: If no valid authentication method is provided
        """
        if not admin_key and not content_key:
            raise AuthenticationError("Either admin_key or content_key must be provided")

        self.admin_key = admin_key
        self.content_key = content_key
        self.ghost_url = ghost_url.rstrip("/")
        self.timeout = timeout

        # Initialize JWT auth if admin key is provided
        self.jwt_auth: Optional[JWTAuth] = None
        if admin_key:
            self.jwt_auth = JWTAuth(admin_key)

    def get_admin_headers(self) -> Dict[str, str]:
        """Get headers for Admin API requests.

        Returns:
            Dictionary of HTTP headers

        Raises:
            AuthenticationError: If admin key is not configured
        """
        if not self.jwt_auth:
            raise AuthenticationError("Admin key not configured")

        token = self.jwt_auth.get_valid_token()
        return {
            "Authorization": f"Ghost {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_content_headers(self) -> Dict[str, str]:
        """Get headers for Content API requests.

        Returns:
            Dictionary of HTTP headers

        Raises:
            AuthenticationError: If content key is not configured
        """
        if not self.content_key:
            raise AuthenticationError("Content key not configured")

        return {
            "Accept": "application/json",
        }

    def get_content_params(self) -> Dict[str, str]:
        """Get query parameters for Content API requests.

        Returns:
            Dictionary of query parameters

        Raises:
            AuthenticationError: If content key is not configured
        """
        if not self.content_key:
            raise AuthenticationError("Content key not configured")

        return {"key": self.content_key}

    def authenticated_request(
        self,
        method: str,
        endpoint: str,
        use_admin_api: bool = True,
        session: Optional[requests.Session] = None,
        debug: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make an authenticated request to Ghost API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/admin/api/posts/')
            use_admin_api: Whether to use Admin API (True) or Content API (False)
            **kwargs: Additional arguments passed to requests

        Returns:
            Response JSON data

        Raises:
            AuthenticationError: If authentication fails
        """
        url = f"{self.ghost_url}{endpoint}"

        # Set up authentication
        if use_admin_api:
            headers = self.get_admin_headers()
            params = kwargs.pop("params", {})
        else:
            headers = self.get_content_headers()
            params = self.get_content_params()
            params.update(kwargs.pop("params", {}))

        # Merge headers
        headers.update(kwargs.pop("headers", {}))

        # Extract timeout from kwargs if provided, otherwise use default
        timeout = kwargs.pop("timeout", self.timeout)

        if debug:
            print(f"[DEBUG AUTH] Making {method} request to {url}")
            print(f"[DEBUG AUTH] Headers: {headers}")
            if params:
                print(f"[DEBUG AUTH] Params: {params}")

        try:
            # Use provided session or create a new request
            if session:
                response = session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                    **kwargs,
                )
            else:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                    **kwargs,
                )

            if debug:
                print(f"[DEBUG AUTH] Response status: {response.status_code}")
                print(f"[DEBUG AUTH] Response headers: {dict(response.headers)}")

            # Handle authentication errors with retry
            if response.status_code == 401 and use_admin_api and self.jwt_auth:
                if debug:
                    print("[DEBUG AUTH] Token expired, invalidating cache and retrying")

                # Token might be expired, invalidate cache and retry once
                self.jwt_auth.invalidate_cache()
                headers = self.get_admin_headers()

                if session:
                    response = session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        timeout=timeout,
                        **kwargs,
                    )
                else:
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        timeout=timeout,
                        **kwargs,
                    )

                if debug:
                    print(f"[DEBUG AUTH] Retry response status: {response.status_code}")

            # Handle rate limiting
            if response.status_code == 429:
                raise AuthenticationError(
                    "Rate limit exceeded. Please wait before making more requests.",
                    details={"status_code": 429, "retry_after": response.headers.get("Retry-After")},
                )

            # Handle authentication errors
            if response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed. Please check your API keys.",
                    details={"status_code": 401},
                )

            # Handle other client errors
            if 400 <= response.status_code < 500:
                error_data = {}
                try:
                    error_data = response.json()
                except Exception:
                    pass

                raise AuthenticationError(
                    f"Client error: {response.status_code}",
                    details={"status_code": response.status_code, "response": error_data},
                )

            # Handle server errors
            if response.status_code >= 500:
                raise AuthenticationError(
                    f"Server error: {response.status_code}",
                    details={"status_code": response.status_code},
                )

            # Return JSON response
            response.raise_for_status()
            result = response.json()

            if debug:
                print(f"[DEBUG AUTH] Response data keys: {list(result.keys()) if isinstance(result, dict) else 'non-dict response'}")

            return result

        except RequestException as e:
            if "timeout" in str(e).lower():
                raise AuthenticationError(f"Request timeout: {e}")
            raise AuthenticationError(f"Request failed: {e}")

    def validate_token(self) -> bool:
        """Validate the current authentication.

        Returns:
            True if authentication is valid, False otherwise
        """
        if not self.jwt_auth:
            return False

        try:
            # Make a simple request to validate the token
            self.authenticated_request("GET", "/ghost/api/admin/users/me/")
            return True

        except AuthenticationError:
            return False