"""Tests for resilience patterns (retry, circuit breaker)."""

from __future__ import annotations

from result import Ok, Err

from axon.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryConfig,
    ResilientProviderWrapper,
)
from axon.provider_plugin import ProviderError, ProviderErrorKind


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_should_retry_timeout(self) -> None:
        config = RetryConfig()
        error = ProviderError(kind=ProviderErrorKind.TIMEOUT, message="timeout")
        assert config.should_retry(error, 0) is True
        assert config.should_retry(error, 2) is True
        assert config.should_retry(error, 3) is False  # max_retries=3

    def test_should_not_retry_auth_error(self) -> None:
        config = RetryConfig()
        error = ProviderError(kind=ProviderErrorKind.AUTHENTICATION, message="bad key")
        assert config.should_retry(error, 0) is False

    def test_delay_increases_exponentially(self) -> None:
        config = RetryConfig(base_delay_seconds=1.0, exponential_base=2.0)
        assert config.delay_for_attempt(0) == 1.0
        assert config.delay_for_attempt(1) == 2.0
        assert config.delay_for_attempt(2) == 4.0

    def test_delay_respects_max(self) -> None:
        config = RetryConfig(base_delay_seconds=10.0, max_delay_seconds=15.0)
        assert config.delay_for_attempt(0) == 10.0
        assert config.delay_for_attempt(1) == 15.0  # capped
        assert config.delay_for_attempt(2) == 15.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_starts_closed(self) -> None:
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_success_keeps_closed(self) -> None:
        cb = CircuitBreaker("test")
        result = cb.call(lambda: Ok("success"))
        assert cb.state == CircuitState.CLOSED
        assert isinstance(result, Ok)

    def test_opens_after_threshold_failures(self) -> None:
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        error = ProviderError(kind=ProviderErrorKind.SERVER_ERROR, message="fail")
        for _ in range(3):
            cb.call(lambda: Err(error))
        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self) -> None:
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        error = ProviderError(kind=ProviderErrorKind.SERVER_ERROR, message="fail")
        cb.call(lambda: Err(error))
        assert cb.state == CircuitState.OPEN
        result = cb.call(lambda: Ok("should not reach"))
        assert isinstance(result, Err)
        assert "Circuit breaker" in result.err_value.message

    def test_half_open_then_closes(self) -> None:
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
            half_open_max_calls=2,
        ))
        error = ProviderError(kind=ProviderErrorKind.SERVER_ERROR, message="fail")
        cb.call(lambda: Err(error))  # OPEN
        # With recovery_timeout=0, next call attempts reset
        cb.call(lambda: Ok("ok"))  # HALF_OPEN, 1 success
        assert cb.state == CircuitState.HALF_OPEN
        cb.call(lambda: Ok("ok"))  # HALF_OPEN, 2 successes -> CLOSED
        assert cb.state == CircuitState.CLOSED

    def test_half_open_fails_back_to_open(self) -> None:
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
            half_open_max_calls=2,
        ))
        fail = ProviderError(kind=ProviderErrorKind.SERVER_ERROR, message="fail")
        cb.call(lambda: Err(fail))  # OPEN
        cb.call(lambda: Ok("ok"))  # HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN
        cb.call(lambda: Err(fail))  # back to OPEN
        assert cb.state == CircuitState.OPEN


class TestResilientProviderWrapper:
    """Tests for ResilientProviderWrapper."""

    def test_success_passes_through(self) -> None:
        wrapper = ResilientProviderWrapper("test")
        result = wrapper.execute(lambda: Ok("hello"))
        assert isinstance(result, Ok)
        assert result.ok_value == "hello"

    def test_non_retryable_error_fails_fast(self) -> None:
        wrapper = ResilientProviderWrapper("test")
        error = ProviderError(kind=ProviderErrorKind.AUTHENTICATION, message="bad key")
        result = wrapper.execute_with_retry(lambda: Err(error))
        assert isinstance(result, Err)
        assert result.err_value.kind == ProviderErrorKind.AUTHENTICATION

    def test_circuit_opens_after_failures(self) -> None:
        wrapper = ResilientProviderWrapper(
            "test",
            retry_config=RetryConfig(max_retries=0),
            circuit_config=CircuitBreakerConfig(failure_threshold=2),
        )
        error = ProviderError(kind=ProviderErrorKind.SERVER_ERROR, message="fail")
        wrapper.execute_with_retry(lambda: Err(error))
        wrapper.execute_with_retry(lambda: Err(error))
        # Circuit should be open now
        result = wrapper.execute_with_retry(lambda: Ok("should not reach"))
        assert isinstance(result, Err)
        assert "Circuit breaker" in result.err_value.message
