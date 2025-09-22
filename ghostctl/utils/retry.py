"""Retry logic and circuit breaker implementation.

This module provides robust retry mechanisms with exponential backoff,
jitter, and circuit breaker patterns for handling transient failures
and protecting against cascading failures.
"""

import time
import random
import threading
from typing import Callable, TypeVar, Any, Dict, Optional, List, Type
from functools import wraps
from enum import Enum

from requests.exceptions import ConnectionError, Timeout, HTTPError

from ..exceptions import MaxRetriesExceededError, CircuitBreakerOpenError

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryManager:
    """Manages retry logic with exponential backoff and jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """Initialize retry manager.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Multiplier for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        # Retry conditions
        self._retry_conditions: List[Callable[[Exception], bool]] = []
        self._default_retry_conditions()

        # Metrics
        self._metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_retry_attempts": 0,
            "total_delay_time": 0.0,
        }

    def _default_retry_conditions(self) -> None:
        """Set up default retry conditions."""
        # Retry on network errors
        self.add_retry_condition(lambda exc: isinstance(exc, (ConnectionError, Timeout)))

        # Retry on 5xx server errors
        self.add_retry_condition(
            lambda exc: isinstance(exc, HTTPError) and hasattr(exc, "response") and exc.response is not None and exc.response.status_code >= 500
        )

    def add_retry_condition(self, condition: Callable[[Exception], bool]) -> None:
        """Add a condition for when to retry.

        Args:
            condition: Function that takes an exception and returns True if should retry
        """
        self._retry_conditions.append(condition)

    def should_retry(self, exception: Exception) -> bool:
        """Check if an exception should trigger a retry.

        Args:
            exception: Exception to check

        Returns:
            True if should retry, False otherwise
        """
        return any(condition(exception) for condition in self._retry_conditions)

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a retry attempt.

        Args:
            attempt: Attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff delay
        delay = self.base_delay * (self.backoff_factor ** attempt)

        # Apply maximum delay limit
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            # Add random jitter between 0% and 100% of the delay
            jitter_range = delay * random.random()
            delay += jitter_range

        return delay

    def execute_with_retry(self, operation: Callable[[], T]) -> T:
        """Execute an operation with retry logic.

        Args:
            operation: Function to execute

        Returns:
            Result of the operation

        Raises:
            MaxRetriesExceededError: If maximum retries are exceeded
        """
        self._metrics["total_operations"] += 1
        last_exception: Optional[Exception] = None
        total_delay = 0.0

        for attempt in range(self.max_retries + 1):
            try:
                result = operation()
                self._metrics["successful_operations"] += 1
                self._metrics["total_delay_time"] += total_delay
                return result

            except Exception as e:
                last_exception = e

                # Don't retry if this is the last attempt
                if attempt == self.max_retries:
                    break

                # Check if we should retry this exception
                if not self.should_retry(e):
                    break

                # Calculate and apply delay
                delay = self.calculate_delay(attempt)
                total_delay += delay
                self._metrics["total_retry_attempts"] += 1

                time.sleep(delay)

        # All retries exhausted
        self._metrics["failed_operations"] += 1
        self._metrics["total_delay_time"] += total_delay

        raise MaxRetriesExceededError(
            f"Maximum retries ({self.max_retries}) exceeded",
            attempts=self.max_retries + 1,
            last_exception=last_exception,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics.

        Returns:
            Dictionary of metrics
        """
        metrics = self._metrics.copy()

        # Calculate derived metrics
        if metrics["total_operations"] > 0:
            metrics["success_rate"] = metrics["successful_operations"] / metrics["total_operations"]
            metrics["failure_rate"] = metrics["failed_operations"] / metrics["total_operations"]
        else:
            metrics["success_rate"] = 0.0
            metrics["failure_rate"] = 0.0

        if metrics["total_retry_attempts"] > 0:
            metrics["average_retry_delay"] = metrics["total_delay_time"] / metrics["total_retry_attempts"]
        else:
            metrics["average_retry_delay"] = 0.0

        return metrics

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        for key in self._metrics:
            self._metrics[key] = 0


class CircuitBreaker:
    """Circuit breaker implementation for protecting against cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: Type[Exception] = Exception,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state.value

    def _reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _record_failure(self) -> None:
        """Record a failure and update state if necessary."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN

    def _can_attempt_call(self) -> bool:
        """Check if a call can be attempted based on current state."""
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.HALF_OPEN:
            return True

        # State is OPEN
        if self._last_failure_time is None:
            return True

        # Check if recovery timeout has passed
        if time.time() - self._last_failure_time >= self.recovery_timeout:
            self._state = CircuitBreakerState.HALF_OPEN
            return True

        return False

    def call(self, operation: Callable[[], T]) -> T:
        """Execute an operation through the circuit breaker.

        Args:
            operation: Function to execute

        Returns:
            Result of the operation

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
        """
        with self._lock:
            if not self._can_attempt_call():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open. Last failure: {self._last_failure_time}"
                )

            # Store current state for failure handling
            current_state = self._state

        try:
            result = operation()

            # Success - reset if we were in half-open state
            with self._lock:
                if current_state == CircuitBreakerState.HALF_OPEN:
                    self._reset()

            return result

        except Exception as e:
            # Check if this exception should trigger the circuit breaker
            if isinstance(e, self.expected_exception):
                with self._lock:
                    if current_state == CircuitBreakerState.HALF_OPEN:
                        # Failed in half-open state, go back to open
                        self._state = CircuitBreakerState.OPEN
                        self._last_failure_time = time.time()
                    else:
                        # Record failure
                        self._record_failure()

            raise

    def get_state_info(self) -> Dict[str, Any]:
        """Get circuit breaker state information.

        Returns:
            Dictionary with state information
        """
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self._last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[[], T]], Callable[[], T]]:
    """Decorator for adding retry logic to functions.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for exponential backoff
        jitter: Whether to add random jitter to delays

    Returns:
        Decorator function
    """
    def decorator(func: Callable[[], T]) -> Callable[[], T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retry_manager = RetryManager(
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                jitter=jitter,
            )

            def operation() -> T:
                return func(*args, **kwargs)

            return retry_manager.execute_with_retry(operation)

        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    expected_exception: Type[Exception] = Exception,
) -> Callable[[Callable[[], T]], Callable[[], T]]:
    """Decorator for adding circuit breaker to functions.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time to wait before attempting recovery
        expected_exception: Exception type that triggers circuit breaker

    Returns:
        Decorator function
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
    )

    def decorator(func: Callable[[], T]) -> Callable[[], T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            def operation() -> T:
                return func(*args, **kwargs)

            return breaker.call(operation)

        return wrapper
    return decorator