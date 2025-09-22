"""Unit tests for retry.py module.

Tests the RetryManager and CircuitBreaker classes for retry logic
including exponential backoff, jitter, circuit breaker patterns, and decorators.
"""

import time
import threading
import pytest
from unittest.mock import Mock, patch, call

from requests.exceptions import ConnectionError, Timeout, HTTPError

from ghostctl.utils.retry import (
    RetryManager,
    CircuitBreaker,
    CircuitBreakerState,
    retry,
    circuit_breaker,
)
from ghostctl.exceptions import MaxRetriesExceededError, CircuitBreakerOpenError


class TestRetryManager:
    """Test cases for the RetryManager class."""

    def test_retry_manager_initialization_defaults(self):
        """Test RetryManager initialization with default values."""
        manager = RetryManager()

        assert manager.max_retries == 3
        assert manager.base_delay == 1.0
        assert manager.max_delay == 60.0
        assert manager.backoff_factor == 2.0
        assert manager.jitter is True

        # Check metrics initialization
        metrics = manager.get_metrics()
        assert metrics["total_operations"] == 0
        assert metrics["successful_operations"] == 0
        assert metrics["failed_operations"] == 0
        assert metrics["total_retry_attempts"] == 0

    def test_retry_manager_initialization_custom(self):
        """Test RetryManager initialization with custom values."""
        manager = RetryManager(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            backoff_factor=3.0,
            jitter=False,
        )

        assert manager.max_retries == 5
        assert manager.base_delay == 2.0
        assert manager.max_delay == 120.0
        assert manager.backoff_factor == 3.0
        assert manager.jitter is False

    def test_add_retry_condition(self):
        """Test adding custom retry conditions."""
        manager = RetryManager()

        # Add custom condition
        def custom_condition(exc):
            return isinstance(exc, ValueError)

        manager.add_retry_condition(custom_condition)

        # Test the condition
        assert manager.should_retry(ValueError("test")) is True
        assert manager.should_retry(TypeError("test")) is False  # Default conditions

    def test_should_retry_default_conditions(self):
        """Test default retry conditions."""
        manager = RetryManager()

        # Should retry on network errors
        assert manager.should_retry(ConnectionError("Network error")) is True
        assert manager.should_retry(Timeout("Request timeout")) is True

        # Should retry on 5xx HTTP errors
        response_500 = Mock()
        response_500.status_code = 500
        http_error_500 = HTTPError()
        http_error_500.response = response_500
        assert manager.should_retry(http_error_500) is True

        # Should not retry on 4xx HTTP errors
        response_400 = Mock()
        response_400.status_code = 400
        http_error_400 = HTTPError()
        http_error_400.response = response_400
        assert manager.should_retry(http_error_400) is False

        # Should not retry on other exceptions
        assert manager.should_retry(ValueError("Not retryable")) is False

    def test_should_retry_http_error_no_response(self):
        """Test should_retry with HTTPError that has no response."""
        manager = RetryManager()

        http_error = HTTPError()
        http_error.response = None
        assert manager.should_retry(http_error) is False

    def test_calculate_delay_without_jitter(self):
        """Test delay calculation without jitter."""
        manager = RetryManager(
            base_delay=2.0,
            max_delay=30.0,
            backoff_factor=3.0,
            jitter=False,
        )

        # Test exponential backoff
        assert manager.calculate_delay(0) == 2.0  # 2.0 * 3^0
        assert manager.calculate_delay(1) == 6.0  # 2.0 * 3^1
        assert manager.calculate_delay(2) == 18.0  # 2.0 * 3^2

        # Test max delay limit
        assert manager.calculate_delay(3) == 30.0  # Should be capped at max_delay

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        manager = RetryManager(base_delay=1.0, jitter=True)

        with patch("random.random", return_value=0.5):
            delay = manager.calculate_delay(0)
            # Base delay (1.0) + jitter (1.0 * 0.5) = 1.5
            assert delay == 1.5

        with patch("random.random", return_value=0.0):
            delay = manager.calculate_delay(0)
            # Base delay (1.0) + jitter (1.0 * 0.0) = 1.0
            assert delay == 1.0

        with patch("random.random", return_value=1.0):
            delay = manager.calculate_delay(0)
            # Base delay (1.0) + jitter (1.0 * 1.0) = 2.0
            assert delay == 2.0

    def test_execute_with_retry_success_first_attempt(self):
        """Test successful operation on first attempt."""
        manager = RetryManager()
        operation = Mock(return_value="success")

        result = manager.execute_with_retry(operation)

        assert result == "success"
        operation.assert_called_once()

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics["total_operations"] == 1
        assert metrics["successful_operations"] == 1
        assert metrics["failed_operations"] == 0
        assert metrics["total_retry_attempts"] == 0

    def test_execute_with_retry_success_after_retries(self):
        """Test successful operation after some retries."""
        manager = RetryManager(max_retries=3, base_delay=0.01)  # Small delay for tests

        # Fail twice, then succeed
        operation = Mock(side_effect=[ConnectionError(), ConnectionError(), "success"])

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = manager.execute_with_retry(operation)

        assert result == "success"
        assert operation.call_count == 3

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics["total_operations"] == 1
        assert metrics["successful_operations"] == 1
        assert metrics["failed_operations"] == 0
        assert metrics["total_retry_attempts"] == 2

    def test_execute_with_retry_max_retries_exceeded(self):
        """Test operation failing after max retries."""
        manager = RetryManager(max_retries=2, base_delay=0.01)

        # Always fail
        operation = Mock(side_effect=ConnectionError("Always fails"))

        with patch("time.sleep"):
            with pytest.raises(MaxRetriesExceededError) as exc_info:
                manager.execute_with_retry(operation)

        assert exc_info.value.attempts == 3  # max_retries + 1
        assert isinstance(exc_info.value.last_exception, ConnectionError)
        assert operation.call_count == 3

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics["total_operations"] == 1
        assert metrics["successful_operations"] == 0
        assert metrics["failed_operations"] == 1
        assert metrics["total_retry_attempts"] == 2

    def test_execute_with_retry_non_retryable_exception(self):
        """Test operation failing with non-retryable exception."""
        manager = RetryManager()

        # Non-retryable exception
        operation = Mock(side_effect=ValueError("Not retryable"))

        with pytest.raises(MaxRetriesExceededError) as exc_info:
            manager.execute_with_retry(operation)

        assert isinstance(exc_info.value.last_exception, ValueError)
        operation.assert_called_once()  # No retries

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics["total_operations"] == 1
        assert metrics["successful_operations"] == 0
        assert metrics["failed_operations"] == 1
        assert metrics["total_retry_attempts"] == 0

    def test_execute_with_retry_delay_calculation(self):
        """Test that delays are calculated and applied correctly."""
        manager = RetryManager(max_retries=2, base_delay=1.0, jitter=False)

        operation = Mock(side_effect=[ConnectionError(), ConnectionError(), "success"])

        with patch("time.sleep") as mock_sleep:
            with patch.object(manager, "calculate_delay", side_effect=[1.0, 2.0]) as mock_calc:
                result = manager.execute_with_retry(operation)

        assert result == "success"
        mock_calc.assert_has_calls([call(0), call(1)])
        mock_sleep.assert_has_calls([call(1.0), call(2.0)])

    def test_get_metrics_with_calculations(self):
        """Test metrics with calculated fields."""
        manager = RetryManager()

        # Simulate some operations
        manager._metrics.update({
            "total_operations": 10,
            "successful_operations": 7,
            "failed_operations": 3,
            "total_retry_attempts": 15,
            "total_delay_time": 45.0,
        })

        metrics = manager.get_metrics()

        assert metrics["success_rate"] == 0.7
        assert metrics["failure_rate"] == 0.3
        assert metrics["average_retry_delay"] == 3.0  # 45.0 / 15

    def test_get_metrics_zero_operations(self):
        """Test metrics when no operations have been performed."""
        manager = RetryManager()

        metrics = manager.get_metrics()

        assert metrics["success_rate"] == 0.0
        assert metrics["failure_rate"] == 0.0
        assert metrics["average_retry_delay"] == 0.0

    def test_reset_metrics(self):
        """Test resetting metrics."""
        manager = RetryManager()

        # Set some metrics
        manager._metrics.update({
            "total_operations": 5,
            "successful_operations": 3,
            "failed_operations": 2,
            "total_retry_attempts": 8,
            "total_delay_time": 20.0,
        })

        manager.reset_metrics()

        # All should be reset to 0
        for value in manager._metrics.values():
            assert value == 0


class TestCircuitBreaker:
    """Test cases for the CircuitBreaker class."""

    def test_circuit_breaker_initialization_defaults(self):
        """Test CircuitBreaker initialization with defaults."""
        breaker = CircuitBreaker()

        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 30.0
        assert breaker.expected_exception == Exception
        assert breaker.state == "closed"

    def test_circuit_breaker_initialization_custom(self):
        """Test CircuitBreaker initialization with custom values."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            expected_exception=ConnectionError,
        )

        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 60.0
        assert breaker.expected_exception == ConnectionError

    def test_circuit_breaker_successful_call(self):
        """Test successful call through circuit breaker."""
        breaker = CircuitBreaker()
        operation = Mock(return_value="success")

        result = breaker.call(operation)

        assert result == "success"
        operation.assert_called_once()
        assert breaker.state == "closed"

    def test_circuit_breaker_failure_under_threshold(self):
        """Test failures under threshold keep circuit closed."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Fail twice (under threshold)
        for _ in range(2):
            operation = Mock(side_effect=Exception("Test error"))
            with pytest.raises(Exception):
                breaker.call(operation)

        # Should still be closed
        assert breaker.state == "closed"
        state_info = breaker.get_state_info()
        assert state_info["failure_count"] == 2

    def test_circuit_breaker_failure_at_threshold(self):
        """Test circuit opens when failure threshold is reached."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Fail exactly at threshold
        for _ in range(3):
            operation = Mock(side_effect=Exception("Test error"))
            with pytest.raises(Exception):
                breaker.call(operation)

        # Should be open now
        assert breaker.state == "open"
        state_info = breaker.get_state_info()
        assert state_info["failure_count"] == 3

    def test_circuit_breaker_open_rejects_calls(self):
        """Test open circuit breaker rejects calls."""
        breaker = CircuitBreaker(failure_threshold=1)

        # Trigger circuit to open
        operation = Mock(side_effect=Exception("Test error"))
        with pytest.raises(Exception):
            breaker.call(operation)

        assert breaker.state == "open"

        # Next call should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(Mock(return_value="success"))

    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker transitions to half-open after timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        # Trigger circuit to open
        operation = Mock(side_effect=Exception("Test error"))
        with pytest.raises(Exception):
            breaker.call(operation)

        assert breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(0.2)

        # Next call should transition to half-open
        operation = Mock(return_value="success")
        result = breaker.call(operation)

        assert result == "success"
        assert breaker.state == "closed"  # Should reset on success

    def test_circuit_breaker_half_open_success_resets(self):
        """Test half-open circuit resets to closed on success."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(Mock(side_effect=Exception("Error")))

        # Wait and try again
        time.sleep(0.2)

        # Successful call should reset circuit
        result = breaker.call(Mock(return_value="success"))
        assert result == "success"
        assert breaker.state == "closed"

        state_info = breaker.get_state_info()
        assert state_info["failure_count"] == 0

    def test_circuit_breaker_half_open_failure_reopens(self):
        """Test half-open circuit goes back to open on failure."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(Mock(side_effect=Exception("Error")))

        # Wait and try again with failure
        time.sleep(0.2)

        with pytest.raises(Exception):
            breaker.call(Mock(side_effect=Exception("Still failing")))

        # Should be open again
        assert breaker.state == "open"

    def test_circuit_breaker_non_expected_exception(self):
        """Test circuit breaker doesn't trigger on unexpected exceptions."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception=ConnectionError,
        )

        # Raise different exception type
        operation = Mock(side_effect=ValueError("Not network error"))

        with pytest.raises(ValueError):
            breaker.call(operation)

        # Should still be closed (failure not counted)
        assert breaker.state == "closed"
        state_info = breaker.get_state_info()
        assert state_info["failure_count"] == 0

    def test_circuit_breaker_expected_exception(self):
        """Test circuit breaker triggers on expected exceptions."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            expected_exception=ConnectionError,
        )

        # Raise expected exception type
        operation = Mock(side_effect=ConnectionError("Network error"))

        with pytest.raises(ConnectionError):
            breaker.call(operation)

        # Should be open (failure counted)
        assert breaker.state == "open"
        state_info = breaker.get_state_info()
        assert state_info["failure_count"] == 1

    def test_circuit_breaker_thread_safety(self):
        """Test circuit breaker thread safety."""
        breaker = CircuitBreaker(failure_threshold=10)
        results = []
        exceptions = []

        def worker():
            try:
                result = breaker.call(lambda: "success")
                results.append(result)
            except Exception as e:
                exceptions.append(e)

        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed
        assert len(results) == 5
        assert len(exceptions) == 0
        assert all(r == "success" for r in results)

    def test_get_state_info(self):
        """Test getting circuit breaker state information."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
        )

        state_info = breaker.get_state_info()

        assert state_info["state"] == "closed"
        assert state_info["failure_count"] == 0
        assert state_info["failure_threshold"] == 3
        assert state_info["last_failure_time"] is None
        assert state_info["recovery_timeout"] == 60.0


class TestRetryDecorator:
    """Test cases for the retry decorator."""

    def test_retry_decorator_success(self):
        """Test retry decorator with successful function."""
        @retry(max_retries=2, base_delay=0.01)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_retry_decorator_with_retries(self):
        """Test retry decorator with function that succeeds after retries."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        with patch("time.sleep"):
            result = flaky_function()

        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_max_retries_exceeded(self):
        """Test retry decorator when max retries are exceeded."""
        @retry(max_retries=2, base_delay=0.01)
        def always_failing_function():
            raise ConnectionError("Always fails")

        with patch("time.sleep"):
            with pytest.raises(MaxRetriesExceededError):
                always_failing_function()

    def test_retry_decorator_with_args_kwargs(self):
        """Test retry decorator with function arguments."""
        @retry(max_retries=1, base_delay=0.01)
        def function_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = function_with_args("x", "y", c="z")
        assert result == "x-y-z"


class TestCircuitBreakerDecorator:
    """Test cases for the circuit breaker decorator."""

    def test_circuit_breaker_decorator_success(self):
        """Test circuit breaker decorator with successful function."""
        @circuit_breaker(failure_threshold=2)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_circuit_breaker_decorator_with_failures(self):
        """Test circuit breaker decorator with failing function."""
        call_count = 0

        @circuit_breaker(failure_threshold=2, expected_exception=ValueError)
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        # First two calls should raise ValueError
        with pytest.raises(ValueError):
            failing_function()
        with pytest.raises(ValueError):
            failing_function()

        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            failing_function()

        assert call_count == 2  # Only called twice due to circuit breaker

    def test_circuit_breaker_decorator_with_args_kwargs(self):
        """Test circuit breaker decorator with function arguments."""
        @circuit_breaker(failure_threshold=1)
        def function_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = function_with_args("x", "y", c="z")
        assert result == "x-y-z"

    def test_circuit_breaker_decorator_recovery(self):
        """Test circuit breaker decorator recovery."""
        call_count = 0

        @circuit_breaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            expected_exception=ValueError
        )
        def function_that_recovers():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            return "recovered"

        # First call fails and opens circuit
        with pytest.raises(ValueError):
            function_that_recovers()

        # Immediate retry should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            function_that_recovers()

        # Wait for recovery and try again
        time.sleep(0.2)
        result = function_that_recovers()
        assert result == "recovered"
        assert call_count == 2