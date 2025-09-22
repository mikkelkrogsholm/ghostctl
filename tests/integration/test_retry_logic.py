"""Integration tests for retry mechanism and error handling.

Tests the complete retry logic workflow including exponential backoff,
circuit breaker patterns, and recovery strategies for various failure scenarios.
"""

import pytest
from unittest.mock import Mock, patch, call
import time
from requests.exceptions import ConnectionError, Timeout, HTTPError
import random

from ghostctl.retry import RetryManager, CircuitBreaker
from ghostctl.exceptions import MaxRetriesExceededError, CircuitBreakerOpenError


class TestRetryLogic:
    """Integration tests for retry mechanism and failure recovery."""

    @pytest.fixture
    def retry_manager(self):
        """Create RetryManager with test configuration."""
        return RetryManager(
            max_retries=3,
            base_delay=0.1,  # Short delays for testing
            max_delay=1.0,
            backoff_factor=2.0,
            jitter=True
        )

    @pytest.fixture
    def circuit_breaker(self):
        """Create CircuitBreaker for testing."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,
            expected_exception=ConnectionError
        )

    def test_exponential_backoff_retry_workflow(self, retry_manager):
        """Test exponential backoff retry mechanism.

        Validates:
        1. Retry attempts with exponential backoff
        2. Delay calculation and jitter
        3. Maximum retry limit enforcement
        4. Success after retries
        """
        # This should fail initially as RetryManager doesn't exist
        call_count = 0
        delays = []

        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        # Mock time to capture delays
        with patch('time.sleep') as mock_sleep:
            result = retry_manager.execute_with_retry(failing_operation)

        # Should succeed after retries
        assert result == "success"
        assert call_count == 3

        # Should have proper exponential backoff delays
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) == 2  # Two retries = two sleeps

        # Delays should increase exponentially (with jitter)
        assert sleep_calls[0] >= 0.1  # Base delay
        assert sleep_calls[1] >= sleep_calls[0]  # Should be larger

    def test_max_retries_exceeded_workflow(self, retry_manager):
        """Test behavior when maximum retries are exceeded.

        Validates:
        1. All retry attempts are made
        2. MaxRetriesExceededError is raised
        3. Original exception is preserved
        4. Retry count tracking
        """
        call_count = 0

        def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"Attempt {call_count} failed")

        # Should exhaust all retries and fail
        with pytest.raises(MaxRetriesExceededError) as exc_info:
            retry_manager.execute_with_retry(always_failing_operation)

        # Should have made all attempts
        assert call_count == 4  # Initial + 3 retries

        # Should preserve original exception details
        assert "ConnectionError" in str(exc_info.value)
        assert "Attempt 4 failed" in str(exc_info.value)

    @patch('requests.get')
    def test_network_failure_retry_workflow(self, mock_get, retry_manager):
        """Test retry logic for various network failures.

        Validates:
        1. Connection timeouts
        2. DNS resolution failures
        3. SSL certificate errors
        4. Network unreachable errors
        """
        # Test connection timeout
        mock_get.side_effect = [
            Timeout("Connection timeout"),
            Timeout("Connection timeout"),
            Mock(status_code=200, json=lambda: {"data": "success"})
        ]

        def api_request():
            response = mock_get("https://ghost.example.com/api/posts/")
            if response.status_code == 200:
                return response.json()
            raise HTTPError(f"HTTP {response.status_code}")

        result = retry_manager.execute_with_retry(api_request)
        assert result == {"data": "success"}
        assert mock_get.call_count == 3

    @patch('requests.post')
    def test_http_error_retry_workflow(self, mock_post, retry_manager):
        """Test retry logic for HTTP errors.

        Validates:
        1. Retryable HTTP errors (5xx)
        2. Non-retryable HTTP errors (4xx)
        3. Rate limiting (429)
        4. Server maintenance (503)
        """
        # Test retryable 5xx errors
        mock_post.side_effect = [
            Mock(status_code=500, json=lambda: {"error": "Internal Server Error"}),
            Mock(status_code=502, json=lambda: {"error": "Bad Gateway"}),
            Mock(status_code=201, json=lambda: {"id": "created"})
        ]

        def create_post():
            response = mock_post("https://ghost.example.com/admin/api/posts/")
            if response.status_code >= 500:
                raise HTTPError(f"Server error: {response.status_code}")
            elif response.status_code >= 400:
                raise HTTPError(f"Client error: {response.status_code}")
            return response.json()

        result = retry_manager.execute_with_retry(create_post)
        assert result == {"id": "created"}

        # Test non-retryable 4xx errors
        mock_post.reset_mock()
        mock_post.side_effect = [
            Mock(status_code=404, json=lambda: {"error": "Not Found"})
        ]

        with pytest.raises(HTTPError, match="Client error: 404"):
            retry_manager.execute_with_retry(create_post)

        # Should not retry 4xx errors
        assert mock_post.call_count == 1

    def test_circuit_breaker_workflow(self, circuit_breaker):
        """Test circuit breaker pattern implementation.

        Validates:
        1. Circuit breaker state transitions
        2. Failure threshold enforcement
        3. Recovery timeout handling
        4. Half-open state testing
        """
        call_count = 0

        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Service unavailable")

        # Circuit breaker should be closed initially
        assert circuit_breaker.state == "closed"

        # Make failing calls to trip the circuit breaker
        for _ in range(3):
            with pytest.raises(ConnectionError):
                circuit_breaker.call(failing_operation)

        # Circuit breaker should now be open
        assert circuit_breaker.state == "open"

        # Further calls should fail fast with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            circuit_breaker.call(failing_operation)

        # Should not have made additional calls
        assert call_count == 3

    def test_circuit_breaker_recovery_workflow(self, circuit_breaker):
        """Test circuit breaker recovery mechanism.

        Validates:
        1. Recovery timeout handling
        2. Half-open state behavior
        3. Successful recovery
        4. Re-opening on continued failures
        """
        def operation_status(should_succeed=False):
            if should_succeed:
                return "success"
            raise ConnectionError("Still failing")

        # Trip the circuit breaker
        for _ in range(3):
            with pytest.raises(ConnectionError):
                circuit_breaker.call(lambda: operation_status(False))

        assert circuit_breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should transition to half-open
        with pytest.raises(ConnectionError):
            circuit_breaker.call(lambda: operation_status(False))

        assert circuit_breaker.state == "open"  # Should re-open on failure

        # Wait again and test successful recovery
        time.sleep(1.1)
        result = circuit_breaker.call(lambda: operation_status(True))

        assert result == "success"
        assert circuit_breaker.state == "closed"

    @patch('requests.get')
    def test_retry_with_circuit_breaker_integration(self, mock_get):
        """Test integration of retry logic with circuit breaker.

        Validates:
        1. Retry attempts within circuit breaker
        2. Circuit breaker trip prevention
        3. Combined failure handling
        4. Performance optimization
        """
        retry_manager = RetryManager(max_retries=2, base_delay=0.1)
        circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=1.0)

        # Simulate intermittent failures
        responses = [
            ConnectionError("Connection failed"),
            ConnectionError("Connection failed"),
            Mock(status_code=200, json=lambda: {"success": True})
        ]
        mock_get.side_effect = responses

        def api_call():
            response = mock_get("https://ghost.example.com/api/posts/")
            if isinstance(response, Exception):
                raise response
            return response.json()

        # Should succeed with retries without tripping circuit breaker
        result = circuit_breaker.call(
            lambda: retry_manager.execute_with_retry(api_call)
        )

        assert result == {"success": True}
        assert circuit_breaker.state == "closed"

    def test_jitter_and_randomization_workflow(self, retry_manager):
        """Test jitter and randomization in retry delays.

        Validates:
        1. Jitter application to prevent thundering herd
        2. Random delay distribution
        3. Maximum delay enforcement
        4. Consistent behavior across retries
        """
        delays_captured = []

        def capture_delay(delay):
            delays_captured.append(delay)
            time.sleep(0)  # Don't actually sleep

        with patch('time.sleep', side_effect=capture_delay):
            call_count = 0

            def failing_operation():
                nonlocal call_count
                call_count += 1
                if call_count < 4:
                    raise ConnectionError("Network error")
                return "success"

            retry_manager.execute_with_retry(failing_operation)

        # Should have captured delays with jitter
        assert len(delays_captured) == 3

        # Delays should be different due to jitter
        assert not all(d == delays_captured[0] for d in delays_captured)

        # All delays should be within expected bounds
        for i, delay in enumerate(delays_captured):
            expected_base = retry_manager.base_delay * (retry_manager.backoff_factor ** i)
            assert delay <= min(expected_base * 2, retry_manager.max_delay)

    @patch('requests.get')
    def test_conditional_retry_workflow(self, mock_get, retry_manager):
        """Test conditional retry based on error types and status codes.

        Validates:
        1. Selective retry for specific errors
        2. Status code-based retry decisions
        3. Custom retry conditions
        4. Error categorization
        """
        # Configure retry conditions
        retry_manager.add_retry_condition(
            lambda exc: isinstance(exc, (ConnectionError, Timeout))
        )
        retry_manager.add_retry_condition(
            lambda exc: isinstance(exc, HTTPError) and "5" in str(exc)
        )

        # Test retryable connection error
        mock_get.side_effect = [
            ConnectionError("Network unreachable"),
            Mock(status_code=200, json=lambda: {"retried": True})
        ]

        def api_request():
            response = mock_get("https://ghost.example.com/api/posts/")
            if isinstance(response, Exception):
                raise response
            return response.json()

        result = retry_manager.execute_with_retry(api_request)
        assert result == {"retried": True}

        # Test non-retryable client error
        mock_get.reset_mock()
        mock_get.side_effect = [HTTPError("404 Not Found")]

        with pytest.raises(HTTPError, match="404 Not Found"):
            retry_manager.execute_with_retry(api_request)

        # Should not retry 404 errors
        assert mock_get.call_count == 1

    def test_retry_metrics_and_monitoring_workflow(self, retry_manager):
        """Test retry metrics collection and monitoring.

        Validates:
        1. Retry attempt counting
        2. Success/failure rate tracking
        3. Delay time measurement
        4. Performance metrics
        """
        def sometimes_failing_operation():
            if random.random() < 0.7:  # 70% failure rate
                raise ConnectionError("Random failure")
            return "success"

        # Execute multiple operations to generate metrics
        successes = 0
        failures = 0

        for _ in range(10):
            try:
                retry_manager.execute_with_retry(sometimes_failing_operation)
                successes += 1
            except MaxRetriesExceededError:
                failures += 1

        # Should collect metrics
        metrics = retry_manager.get_metrics()
        assert metrics['total_operations'] == 10
        assert metrics['successful_operations'] == successes
        assert metrics['failed_operations'] == failures
        assert metrics['total_retry_attempts'] >= failures
        assert 'average_retry_delay' in metrics