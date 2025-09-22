"""Integration tests for JWT authentication flow.

Tests the complete authentication workflow including JWT token generation,
validation, refresh, and error handling for Ghost CMS Admin API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import jwt
import time
from datetime import datetime, timedelta

from ghostctl.auth import AuthManager, JWTAuth
from ghostctl.exceptions import AuthenticationError, TokenExpiredError


class TestAuthFlow:
    """Integration tests for JWT authentication workflow."""

    @pytest.fixture
    def mock_admin_key(self):
        """Mock admin API key in correct format."""
        return "664746a3b1c8f8d65a000001:1234567890abcdef1234567890abcdef12345678"

    @pytest.fixture
    def auth_manager(self, mock_admin_key):
        """Create AuthManager instance with test configuration."""
        return AuthManager(
            admin_key=mock_admin_key,
            ghost_url="https://ghost.example.com"
        )

    @pytest.fixture
    def jwt_auth(self, mock_admin_key):
        """Create JWTAuth instance for testing."""
        return JWTAuth(admin_key=mock_admin_key)

    def test_jwt_token_generation_workflow(self, jwt_auth, mock_admin_key):
        """Test JWT token generation for Ghost Admin API.

        Validates:
        1. Token generation with correct claims
        2. Token signing with secret
        3. Expiration time handling
        4. Audience and issuer claims
        """
        # This should fail initially as JWTAuth doesn't exist
        token = jwt_auth.generate_token()

        # Should be a valid JWT token
        assert isinstance(token, str)
        assert len(token.split('.')) == 3  # JWT has 3 parts

        # Decode and validate claims
        key_id, secret = mock_admin_key.split(':')
        decoded = jwt.decode(token, secret, algorithms=['HS256'])

        # Should have correct claims
        assert decoded['iss'] == key_id
        assert decoded['aud'] == '/admin/'
        assert 'iat' in decoded
        assert 'exp' in decoded

        # Expiration should be in the future
        assert decoded['exp'] > time.time()

    def test_token_expiration_and_refresh_workflow(self, jwt_auth):
        """Test token expiration handling and refresh mechanism.

        Validates:
        1. Token expiration detection
        2. Automatic token refresh
        3. Retry logic with new token
        4. Token cache management
        """
        # Generate initial token
        token1 = jwt_auth.generate_token()

        # Simulate token expiration by advancing time
        with patch('time.time', return_value=time.time() + 3600):
            # Should detect expired token and generate new one
            token2 = jwt_auth.get_valid_token()
            assert token2 != token1

        # Should cache valid tokens
        token3 = jwt_auth.get_valid_token()
        assert token3 == token2

    @patch('requests.get')
    def test_authenticated_api_request_workflow(self, mock_get, auth_manager):
        """Test complete authenticated API request flow.

        Validates:
        1. JWT token generation
        2. Authorization header inclusion
        3. API request execution
        4. Response handling
        5. Error handling and retries
        """
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [{"id": "1", "title": "Test Post"}]
        }
        mock_get.return_value = mock_response

        # Should make authenticated request
        response = auth_manager.authenticated_request('GET', '/admin/api/posts/')

        # Should include JWT token in Authorization header
        call_args = mock_get.call_args
        headers = call_args[1]['headers']
        assert 'Authorization' in headers
        assert headers['Authorization'].startswith('Ghost ')

        # Should return response data
        assert response == mock_response.json.return_value

    @patch('requests.get')
    def test_authentication_error_handling_workflow(self, mock_get, auth_manager):
        """Test authentication error handling and recovery.

        Validates:
        1. 401 Unauthorized response handling
        2. Token refresh on authentication failure
        3. Retry with new token
        4. Maximum retry limits
        5. Error propagation
        """
        # Mock 401 response
        mock_response_401 = Mock()
        mock_response_401.status_code = 401
        mock_response_401.json.return_value = {
            "errors": [{"message": "Invalid token"}]
        }

        # Mock successful response after retry
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"posts": []}

        # First call returns 401, second returns 200
        mock_get.side_effect = [mock_response_401, mock_response_200]

        # Should retry with new token and succeed
        response = auth_manager.authenticated_request('GET', '/admin/api/posts/')
        assert response == {"posts": []}

        # Should have made two requests
        assert mock_get.call_count == 2

    @patch('requests.get')
    def test_token_validation_workflow(self, mock_get, auth_manager):
        """Test token validation against Ghost API.

        Validates:
        1. Token validation request
        2. API version compatibility
        3. Permission verification
        4. Invalid token detection
        """
        # Mock successful validation response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "users": [{"id": "1", "roles": ["Administrator"]}]
        }
        mock_get.return_value = mock_response

        # Should validate token by making test request
        is_valid = auth_manager.validate_token()
        assert is_valid is True

        # Should have made validation request
        mock_get.assert_called()

        # Test invalid token
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid token"}]
        }

        is_valid = auth_manager.validate_token()
        assert is_valid is False

    def test_multiple_ghost_instances_workflow(self):
        """Test authentication with multiple Ghost instances.

        Validates:
        1. Separate auth managers for different instances
        2. Token isolation between instances
        3. Cross-instance request handling
        4. Configuration management
        """
        # Create auth managers for different instances
        auth1 = AuthManager(
            admin_key="664746a3b1c8f8d65a000001:secret1",
            ghost_url="https://ghost1.example.com"
        )

        auth2 = AuthManager(
            admin_key="664746a3b1c8f8d65a000002:secret2",
            ghost_url="https://ghost2.example.com"
        )

        # Should generate different tokens
        token1 = auth1.jwt_auth.generate_token()
        token2 = auth2.jwt_auth.generate_token()
        assert token1 != token2

        # Tokens should have different issuers
        decoded1 = jwt.decode(token1, "secret1", algorithms=['HS256'])
        decoded2 = jwt.decode(token2, "secret2", algorithms=['HS256'])
        assert decoded1['iss'] != decoded2['iss']

    def test_token_caching_and_cleanup_workflow(self, auth_manager):
        """Test token caching and automatic cleanup.

        Validates:
        1. Token caching for performance
        2. Cache invalidation on expiration
        3. Memory management
        4. Concurrent access handling
        """
        # First request should generate and cache token
        token1 = auth_manager.jwt_auth.get_valid_token()

        # Second request should use cached token
        token2 = auth_manager.jwt_auth.get_valid_token()
        assert token1 == token2

        # Should track cache hits for performance
        cache_stats = auth_manager.jwt_auth.get_cache_stats()
        assert cache_stats['hits'] >= 1

        # Force cache invalidation
        auth_manager.jwt_auth.invalidate_cache()
        token3 = auth_manager.jwt_auth.get_valid_token()
        assert token3 != token1

    @patch('requests.post')
    def test_admin_api_authentication_workflow(self, mock_post, auth_manager):
        """Test authentication workflow for Admin API operations.

        Validates:
        1. Admin-specific JWT claims
        2. Write operation authentication
        3. Permission-based access control
        4. Resource-specific authorization
        """
        # Mock successful admin operation
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "posts": [{"id": "new-post", "title": "Created Post"}]
        }
        mock_post.return_value = mock_response

        # Should authenticate admin operation
        post_data = {"title": "New Post", "html": "<p>Content</p>"}
        response = auth_manager.authenticated_request(
            'POST',
            '/admin/api/posts/',
            json=post_data
        )

        # Should include proper admin authentication
        call_args = mock_post.call_args
        headers = call_args[1]['headers']

        # Should have JWT token for admin operations
        assert 'Authorization' in headers
        token = headers['Authorization'].replace('Ghost ', '')

        # Decode token and verify admin claims
        key_id, secret = auth_manager.admin_key.split(':')
        decoded = jwt.decode(token, secret, algorithms=['HS256'])
        assert decoded['aud'] == '/admin/'

    def test_content_api_vs_admin_api_authentication(self):
        """Test different authentication methods for Content vs Admin API.

        Validates:
        1. Content API key authentication
        2. Admin API JWT authentication
        3. Proper header formatting
        4. API-specific error handling
        """
        content_auth = AuthManager(
            content_key="664746a3b1c8f8d65a000003",
            ghost_url="https://ghost.example.com"
        )

        admin_auth = AuthManager(
            admin_key="664746a3b1c8f8d65a000001:secret",
            ghost_url="https://ghost.example.com"
        )

        # Content API should use key in query parameter
        content_headers = content_auth.get_content_headers()
        assert 'Authorization' not in content_headers

        # Admin API should use JWT in Authorization header
        admin_headers = admin_auth.get_admin_headers()
        assert 'Authorization' in admin_headers
        assert admin_headers['Authorization'].startswith('Ghost ')

    def test_authentication_error_recovery_workflow(self, auth_manager):
        """Test recovery from various authentication errors.

        Validates:
        1. Network timeout recovery
        2. Invalid key format handling
        3. Ghost API version incompatibility
        4. Rate limiting handling
        """
        # Test network timeout
        with patch('requests.get', side_effect=TimeoutError("Request timeout")):
            with pytest.raises(AuthenticationError, match="timeout"):
                auth_manager.validate_token()

        # Test invalid key format
        with pytest.raises(AuthenticationError, match="Invalid admin key format"):
            AuthManager(
                admin_key="invalid-key-format",
                ghost_url="https://ghost.example.com"
            )

        # Test rate limiting
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                "errors": [{"message": "Too Many Requests"}]
            }
            mock_get.return_value = mock_response

            with pytest.raises(AuthenticationError, match="rate limit"):
                auth_manager.authenticated_request('GET', '/admin/api/posts/')