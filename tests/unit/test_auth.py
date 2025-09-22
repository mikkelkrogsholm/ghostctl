"""Unit tests for auth.py module.

Tests the JWTAuth and AuthManager classes for authentication
including JWT token generation, caching, validation, and API requests.
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock

import jwt
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from ghostctl.utils.auth import JWTAuth, AuthManager
from ghostctl.exceptions import AuthenticationError, TokenExpiredError


class TestJWTAuth:
    """Test cases for the JWTAuth class."""

    def test_jwt_auth_initialization_valid_key(self):
        """Test JWTAuth initialization with valid admin key."""
        admin_key = "5f3d4a9b8c7e2f1a9b8c7e2f:my_secret_key"
        auth = JWTAuth(admin_key)

        assert auth.key_id == "5f3d4a9b8c7e2f1a9b8c7e2f"
        assert auth.secret == "my_secret_key"
        assert auth._token_cache is None
        assert auth._token_expires_at is None

    def test_jwt_auth_initialization_invalid_format_no_colon(self):
        """Test JWTAuth initialization with invalid format (no colon)."""
        with pytest.raises(AuthenticationError, match="Invalid admin key format"):
            JWTAuth("invalid_key_without_colon")

    def test_jwt_auth_initialization_valid_format_multiple_colons(self):
        """Test JWTAuth initialization with multiple colons (only first is used as delimiter)."""
        # The implementation uses split(":", 1) so this is actually valid
        auth = JWTAuth("key_id:secret:with:colons")
        assert auth.key_id == "key_id"
        assert auth.secret == "secret:with:colons"

    def test_jwt_auth_initialization_invalid_format_empty_parts(self):
        """Test JWTAuth initialization with empty parts."""
        invalid_keys = [
            ":empty_id",
            "empty_secret:",
            ":",
        ]

        for key in invalid_keys:
            with pytest.raises(AuthenticationError, match="Invalid admin key format"):
                JWTAuth(key)

    def test_generate_token_success(self):
        """Test successful JWT token generation."""
        auth = JWTAuth("5f3d4a9b8c7e2f1a9b8c7e2f:my_secret")

        with patch("time.time", return_value=1000):
            token = auth.generate_token(expires_in=300)

        # Decode without verifying expiration for testing
        payload = jwt.decode(
            token,
            "my_secret",
            algorithms=["HS256"],
            audience="/admin/",
            options={"verify_exp": False}
        )
        assert payload["iss"] == "5f3d4a9b8c7e2f1a9b8c7e2f"
        assert payload["aud"] == "/admin/"
        assert payload["iat"] == 1000
        assert payload["exp"] == 1300

    def test_generate_token_custom_expiry(self):
        """Test JWT token generation with custom expiry."""
        auth = JWTAuth("key_id:secret")

        with patch("time.time", return_value=2000):
            token = auth.generate_token(expires_in=600)

        payload = jwt.decode(
            token,
            "secret",
            algorithms=["HS256"],
            audience="/admin/",
            options={"verify_exp": False}
        )
        assert payload["exp"] == 2600  # 2000 + 600

    def test_generate_token_jwt_error(self):
        """Test JWT token generation with JWT encoding error."""
        auth = JWTAuth("key_id:secret")

        with patch("jwt.encode", side_effect=Exception("JWT error")):
            with pytest.raises(AuthenticationError, match="Failed to generate JWT token"):
                auth.generate_token()

    def test_get_valid_token_no_cache(self):
        """Test getting valid token when no token is cached."""
        auth = JWTAuth("key_id:secret")

        with patch.object(auth, "generate_token", return_value="new_token") as mock_gen:
            with patch("time.time", return_value=1000):
                token = auth.get_valid_token()

        assert token == "new_token"
        assert auth._token_cache == "new_token"
        assert auth._token_expires_at == 1300  # 1000 + 300
        assert auth._cache_stats["misses"] == 1
        assert auth._cache_stats["hits"] == 0
        mock_gen.assert_called_once_with(300)

    def test_get_valid_token_cache_hit(self):
        """Test getting valid token from cache."""
        auth = JWTAuth("key_id:secret")

        # Set up cached token
        auth._token_cache = "cached_token"
        auth._token_expires_at = 2000  # Far in the future

        with patch("time.time", return_value=1000):
            with patch.object(auth, "generate_token") as mock_gen:
                token = auth.get_valid_token(min_remaining=60)

        assert token == "cached_token"
        assert auth._cache_stats["hits"] == 1
        assert auth._cache_stats["misses"] == 0
        mock_gen.assert_not_called()

    def test_get_valid_token_cache_miss_expired(self):
        """Test getting valid token when cached token is expired."""
        auth = JWTAuth("key_id:secret")

        # Set up expired token
        auth._token_cache = "expired_token"
        auth._token_expires_at = 1050  # Only 50 seconds left

        with patch("time.time", return_value=1000):
            with patch.object(auth, "generate_token", return_value="new_token") as mock_gen:
                token = auth.get_valid_token(min_remaining=60)

        assert token == "new_token"
        assert auth._cache_stats["misses"] == 1
        assert auth._cache_stats["hits"] == 0
        mock_gen.assert_called_once()

    def test_validate_token_valid(self):
        """Test validating a valid token."""
        auth = JWTAuth("key_id:secret")

        # Generate a valid token
        with patch("time.time", return_value=1000):
            token = auth.generate_token(expires_in=300)

            # Validate the token (keep time mocked)
            assert auth.validate_token(token) is True

    def test_validate_token_expired(self):
        """Test validating an expired token."""
        auth = JWTAuth("key_id:secret")

        # Generate a token that will be expired
        with patch("time.time", return_value=1000):
            token = auth.generate_token(expires_in=300)

        # Validate after expiration
        with patch("time.time", return_value=1400):  # Expired
            assert auth.validate_token(token) is False

    def test_validate_token_invalid_signature(self):
        """Test validating token with invalid signature."""
        auth = JWTAuth("key_id:secret")

        # Generate token with wrong secret
        token = jwt.encode(
            {"iss": "key_id", "aud": "/admin/", "iat": 1000, "exp": 1300},
            "wrong_secret",
            algorithm="HS256"
        )

        assert auth.validate_token(token) is False

    def test_validate_token_cached(self):
        """Test validating cached token."""
        auth = JWTAuth("key_id:secret")

        # Set up cached token and validate within same time context
        with patch("time.time", return_value=1000):
            auth._token_cache = auth.generate_token(expires_in=300)
            # Validate cached token within same time context
            assert auth.validate_token() is True

    def test_validate_token_no_token(self):
        """Test validating when no token is provided or cached."""
        auth = JWTAuth("key_id:secret")
        assert auth.validate_token() is False

    def test_invalidate_cache(self):
        """Test invalidating token cache."""
        auth = JWTAuth("key_id:secret")

        # Set up cache
        auth._token_cache = "token"
        auth._token_expires_at = 2000

        auth.invalidate_cache()

        assert auth._token_cache is None
        assert auth._token_expires_at is None

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        auth = JWTAuth("key_id:secret")

        # Trigger some cache operations
        auth._cache_stats["hits"] = 5
        auth._cache_stats["misses"] = 3

        stats = auth.get_cache_stats()
        assert stats["hits"] == 5
        assert stats["misses"] == 3

        # Should return a copy
        stats["hits"] = 10
        assert auth._cache_stats["hits"] == 5


class TestAuthManager:
    """Test cases for the AuthManager class."""

    def test_auth_manager_initialization_admin_key(self):
        """Test AuthManager initialization with admin key."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
            timeout=60,
        )

        assert manager.admin_key == "key_id:secret"
        assert manager.content_key is None
        assert manager.ghost_url == "https://blog.example.com"
        assert manager.timeout == 60
        assert manager.jwt_auth is not None

    def test_auth_manager_initialization_content_key(self):
        """Test AuthManager initialization with content key."""
        manager = AuthManager(
            content_key="content_key_123",
            ghost_url="https://blog.example.com/",  # With trailing slash
        )

        assert manager.admin_key is None
        assert manager.content_key == "content_key_123"
        assert manager.ghost_url == "https://blog.example.com"  # Trailing slash removed
        assert manager.jwt_auth is None

    def test_auth_manager_initialization_both_keys(self):
        """Test AuthManager initialization with both keys."""
        manager = AuthManager(
            admin_key="key_id:secret",
            content_key="content_key_123",
            ghost_url="https://blog.example.com",
        )

        assert manager.admin_key == "key_id:secret"
        assert manager.content_key == "content_key_123"
        assert manager.jwt_auth is not None

    def test_auth_manager_initialization_no_keys(self):
        """Test AuthManager initialization without any keys."""
        with pytest.raises(AuthenticationError, match="Either admin_key or content_key must be provided"):
            AuthManager(ghost_url="https://blog.example.com")

    def test_get_admin_headers(self):
        """Test getting admin API headers."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        with patch.object(manager.jwt_auth, "get_valid_token", return_value="test_token"):
            headers = manager.get_admin_headers()

        expected_headers = {
            "Authorization": "Ghost test_token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        assert headers == expected_headers

    def test_get_admin_headers_no_admin_key(self):
        """Test getting admin headers when no admin key is configured."""
        manager = AuthManager(
            content_key="content_key_123",
            ghost_url="https://blog.example.com",
        )

        with pytest.raises(AuthenticationError, match="Admin key not configured"):
            manager.get_admin_headers()

    def test_get_content_headers(self):
        """Test getting content API headers."""
        manager = AuthManager(
            content_key="content_key_123",
            ghost_url="https://blog.example.com",
        )

        headers = manager.get_content_headers()
        expected_headers = {"Accept": "application/json"}
        assert headers == expected_headers

    def test_get_content_headers_no_content_key(self):
        """Test getting content headers when no content key is configured."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        with pytest.raises(AuthenticationError, match="Content key not configured"):
            manager.get_content_headers()

    def test_get_content_params(self):
        """Test getting content API parameters."""
        manager = AuthManager(
            content_key="content_key_123",
            ghost_url="https://blog.example.com",
        )

        params = manager.get_content_params()
        assert params == {"key": "content_key_123"}

    def test_get_content_params_no_content_key(self):
        """Test getting content params when no content key is configured."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        with pytest.raises(AuthenticationError, match="Content key not configured"):
            manager.get_content_params()

    @patch("requests.request")
    def test_authenticated_request_admin_api_success(self, mock_request):
        """Test successful admin API request."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            result = manager.authenticated_request("GET", "/ghost/api/admin/posts/")

        assert result == {"posts": []}
        mock_request.assert_called_once()

    @patch("requests.request")
    def test_authenticated_request_content_api_success(self, mock_request):
        """Test successful content API request."""
        manager = AuthManager(
            content_key="content_key_123",
            ghost_url="https://blog.example.com",
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = manager.authenticated_request(
            "GET", "/ghost/api/content/posts/", use_admin_api=False
        )

        assert result == {"posts": []}
        mock_request.assert_called_once()

        # Verify content API parameters were included
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"]["key"] == "content_key_123"

    @patch("requests.request")
    def test_authenticated_request_with_session(self, mock_request):
        """Test authenticated request using session."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            result = manager.authenticated_request(
                "POST", "/ghost/api/admin/posts/", session=mock_session
            )

        assert result == {"data": "test"}
        mock_session.request.assert_called_once()
        mock_request.assert_not_called()

    @patch("requests.request")
    def test_authenticated_request_401_retry_success(self, mock_request):
        """Test 401 error with successful retry."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        # First call returns 401, second call succeeds
        response_401 = Mock()
        response_401.status_code = 401

        response_200 = Mock()
        response_200.status_code = 200
        response_200.json.return_value = {"success": True}
        response_200.raise_for_status.return_value = None

        mock_request.side_effect = [response_401, response_200]

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with patch.object(manager.jwt_auth, "invalidate_cache") as mock_invalidate:
                result = manager.authenticated_request("GET", "/ghost/api/admin/posts/")

        assert result == {"success": True}
        assert mock_request.call_count == 2
        mock_invalidate.assert_called_once()

    @patch("requests.request")
    def test_authenticated_request_401_retry_failure(self, mock_request):
        """Test 401 error with failed retry."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        # Both calls return 401
        response_401 = Mock()
        response_401.status_code = 401
        mock_request.return_value = response_401

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with pytest.raises(AuthenticationError, match="Authentication failed"):
                manager.authenticated_request("GET", "/ghost/api/admin/posts/")

    @patch("requests.request")
    def test_authenticated_request_429_rate_limit(self, mock_request):
        """Test 429 rate limit error."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        response_429 = Mock()
        response_429.status_code = 429
        response_429.headers = {"Retry-After": "60"}
        mock_request.return_value = response_429

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with pytest.raises(AuthenticationError, match="Rate limit exceeded") as exc_info:
                manager.authenticated_request("GET", "/ghost/api/admin/posts/")

        assert exc_info.value.details["status_code"] == 429
        assert exc_info.value.details["retry_after"] == "60"

    @patch("requests.request")
    def test_authenticated_request_400_client_error(self, mock_request):
        """Test 400 client error."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        response_400 = Mock()
        response_400.status_code = 400
        response_400.json.return_value = {"error": "Bad request"}
        mock_request.return_value = response_400

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with pytest.raises(AuthenticationError, match="Client error: 400") as exc_info:
                manager.authenticated_request("GET", "/ghost/api/admin/posts/")

        assert exc_info.value.details["status_code"] == 400
        assert exc_info.value.details["response"] == {"error": "Bad request"}

    @patch("requests.request")
    def test_authenticated_request_500_server_error(self, mock_request):
        """Test 500 server error."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        response_500 = Mock()
        response_500.status_code = 500
        mock_request.return_value = response_500

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with pytest.raises(AuthenticationError, match="Server error: 500") as exc_info:
                manager.authenticated_request("GET", "/ghost/api/admin/posts/")

        assert exc_info.value.details["status_code"] == 500

    @patch("requests.request")
    def test_authenticated_request_timeout_error(self, mock_request):
        """Test request timeout error."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        mock_request.side_effect = Timeout("Request timeout")

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with pytest.raises(AuthenticationError, match="Request timeout"):
                manager.authenticated_request("GET", "/ghost/api/admin/posts/")

    @patch("requests.request")
    def test_authenticated_request_connection_error(self, mock_request):
        """Test connection error."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        mock_request.side_effect = ConnectionError("Connection failed")

        with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
            with pytest.raises(AuthenticationError, match="Request failed"):
                manager.authenticated_request("GET", "/ghost/api/admin/posts/")

    def test_authenticated_request_debug_mode(self, capsys):
        """Test authenticated request with debug output."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        with patch("requests.request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.json.return_value = {"test": "data"}
            mock_response.raise_for_status.return_value = None
            mock_request.return_value = mock_response

            with patch.object(manager, "get_admin_headers", return_value={"Authorization": "Ghost token"}):
                manager.authenticated_request("GET", "/ghost/api/admin/posts/", debug=True)

        captured = capsys.readouterr()
        assert "[DEBUG AUTH] Making GET request" in captured.out
        assert "[DEBUG AUTH] Headers:" in captured.out
        assert "[DEBUG AUTH] Response status: 200" in captured.out

    def test_validate_token_success(self):
        """Test successful token validation."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        with patch.object(manager, "authenticated_request", return_value={"user": "test"}):
            assert manager.validate_token() is True

    def test_validate_token_failure(self):
        """Test failed token validation."""
        manager = AuthManager(
            admin_key="key_id:secret",
            ghost_url="https://blog.example.com",
        )

        with patch.object(manager, "authenticated_request", side_effect=AuthenticationError("Invalid")):
            assert manager.validate_token() is False

    def test_validate_token_no_jwt_auth(self):
        """Test token validation when no JWT auth is available."""
        manager = AuthManager(
            content_key="content_key_123",
            ghost_url="https://blog.example.com",
        )

        assert manager.validate_token() is False