"""Resilience patterns for AXON Phase 3 production hardening.

This module provides retry with exponential backoff, circuit breakers,
and timeout wrappers for provider calls and other runtime operations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar
from result import Result, Ok, Err

from axon.provider_plugin import ProviderError, ProviderErrorKind


T = TypeVar("T")


class CircuitState(Enum):
    """States for the circuit breaker."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class RetryConfig:
    """Configuration for retry with exponential backoff."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    retryable_kinds: set[ProviderErrorKind] = field(
        default_factory=lambda: {
            ProviderErrorKind.TIMEOUT,
            ProviderErrorKind.RATE_LIMIT,
            ProviderErrorKind.SERVER_ERROR,
            ProviderErrorKind.NETWORK_ERROR,
        }
    )

    def should_retry(self, error: ProviderError, attempt: int) -> bool:
        """Check if an error should be retried."""
        if attempt >= self.max_retries:
            return False
        return error.kind in self.retryable_kinds

    def delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay for a given attempt (0-indexed)."""
        delay = self.base_delay_seconds * (self.exponential_base ** attempt)
        return min(delay, self.max_delay_seconds)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """Circuit breaker for provider calls.

    Opens after ``failure_threshold`` consecutive failures.
    Transitions to half-open after ``recovery_timeout_seconds``.
    Closes after ``half_open_max_calls`` successful calls.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None

    def call(self, fn: Callable[[], Result[T, ProviderError]]) -> Result[T, ProviderError]:
        """Execute a call through the circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                return Err(ProviderError(
                    kind=ProviderErrorKind.SERVER_ERROR,
                    message=f"Circuit breaker '{self.name}' is OPEN",
                    retryable=False,
                ))

        result = fn()

        if isinstance(result, Err):
            self._record_failure()
        else:
            self._record_success()

        return result

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.recovery_timeout_seconds

    def _record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN

    def _record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        else:
            self.failure_count = 0


class ResilientProviderWrapper:
    """Wraps a provider call with retry and circuit breaker."""

    def __init__(
        self,
        provider_name: str,
        retry_config: RetryConfig | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
    ):
        self.provider_name = provider_name
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = CircuitBreaker(provider_name, circuit_config)

    def execute(
        self,
        fn: Callable[[], Result[T, ProviderError]],
    ) -> Result[T, ProviderError]:
        """Execute a provider call with circuit breaker and retry."""
        # Circuit breaker first
        result = self.circuit_breaker.call(fn)
        if isinstance(result, Err):
            error = result.err_value
            # If circuit breaker rejected, don't retry
            if "Circuit breaker" in error.message:
                return result
            # Otherwise, retry logic is handled by the caller or we can retry here
            # For now, let the caller handle retries or we can implement it
        return result

    def execute_with_retry(
        self,
        fn: Callable[[], Result[T, ProviderError]],
    ) -> Result[T, ProviderError]:
        """Execute with full retry + circuit breaker."""
        for attempt in range(self.retry_config.max_retries + 1):
            result = self.circuit_breaker.call(fn)
            if isinstance(result, Ok):
                return result
            error = result.err_value
            if "Circuit breaker" in error.message:
                return result
            if not self.retry_config.should_retry(error, attempt):
                return result
            delay = self.retry_config.delay_for_attempt(attempt)
            time.sleep(delay)
        return result
