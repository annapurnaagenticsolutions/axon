"""Integration tests for real provider plugins against a fake OpenAI server.

No API keys required — a local HTTP server mimics the OpenAI chat completions
endpoint so the real ``OpenAIProvider`` code paths are exercised end-to-end.
"""

from __future__ import annotations

import pytest

from result import Ok, Err

from fake_openai_server import FakeOpenAIServer
from axon.providers.openai_provider import OpenAIProvider
from axon.provider_plugin import ProviderConfig, ProviderErrorKind


@pytest.fixture
def fake_server():
    with FakeOpenAIServer() as srv:
        yield srv


class TestOpenAIProviderAgainstFakeServer:
    """End-to-end tests without real API keys."""

    def _make_provider(self, fake_server, api_key: str = "sk-fake") -> OpenAIProvider:
        """Create an OpenAIProvider pointed at the fake server."""
        provider = OpenAIProvider()
        # Override config to point at fake server
        provider._config = provider._config.__class__(
            name="openai",
            api_key_env_var="OPENAI_API_KEY",
            base_url=fake_server.base_url,
            timeout_seconds=10,
            max_retries=0,
        )
        # Ensure the provider uses our fake key
        import os
        os.environ["OPENAI_API_KEY"] = api_key
        return provider

    def test_call_returns_ok(self, fake_server):
        provider = self._make_provider(fake_server)
        result = provider.call(prompt="Say hello", model="gpt-4", max_tokens=10)
        assert isinstance(result, Ok)
        assert "Fake response to:" in result.ok_value

    def test_call_stream_yields_chunks(self, fake_server):
        provider = self._make_provider(fake_server)
        chunks = list(provider.call_stream(prompt="Stream test", model="gpt-4", max_tokens=10))
        assert len(chunks) > 0
        assert all(isinstance(c, Ok) for c in chunks)
        full = "".join(c.ok_value for c in chunks)
        assert "Hello, this is a fake stream." in full

    def test_call_async_returns_ok(self, fake_server):
        provider = self._make_provider(fake_server)
        import asyncio
        result = asyncio.run(provider.call_async(prompt="Async hello", model="gpt-4", max_tokens=10))
        assert isinstance(result, Ok)
        assert "Fake response to:" in result.ok_value

    def test_call_stream_async_yields_chunks(self, fake_server):
        provider = self._make_provider(fake_server)
        import asyncio

        async def _collect():
            chunks = []
            async for chunk in provider.call_stream_async(prompt="Async stream", model="gpt-4", max_tokens=10):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(_collect())
        assert len(chunks) > 0
        assert all(isinstance(c, Ok) for c in chunks)

    def test_call_with_rate_limit_error(self, fake_server):
        from fake_openai_server import _Handler
        _Handler.rate_limit = True
        try:
            provider = self._make_provider(fake_server)
            result = provider.call(prompt="Rate limit test", model="gpt-4", max_tokens=10)
            assert isinstance(result, Err)
            assert result.err_value.kind == ProviderErrorKind.RATE_LIMIT
        finally:
            _Handler.rate_limit = False

    def test_call_with_server_error(self, fake_server):
        from fake_openai_server import _Handler
        _Handler.fail_next = 5  # high enough to exhaust openai client retries
        try:
            provider = self._make_provider(fake_server)
            result = provider.call(prompt="Server error test", model="gpt-4", max_tokens=10)
            assert isinstance(result, Err)
            assert result.err_value.kind == ProviderErrorKind.SERVER_ERROR
        finally:
            _Handler.fail_next = 0

    def test_stream_with_server_error(self, fake_server):
        from fake_openai_server import _Handler
        _Handler.fail_next = 5
        try:
            provider = self._make_provider(fake_server)
            chunks = list(provider.call_stream(prompt="Stream error", model="gpt-4", max_tokens=10))
            assert len(chunks) > 0
            assert isinstance(chunks[0], Err)
        finally:
            _Handler.fail_next = 0


class TestResilienceAgainstFakeServer:
    """Test ResilientProviderWrapper with fake provider failures."""

    def _make_provider(self, fake_server, api_key: str = "sk-fake") -> OpenAIProvider:
        provider = OpenAIProvider()
        provider._config = ProviderConfig(
            name="openai",
            api_key_env_var="OPENAI_API_KEY",
            base_url=fake_server.base_url,
            timeout_seconds=10,
            max_retries=0,
        )
        import os
        os.environ["OPENAI_API_KEY"] = api_key
        return provider

    def test_retry_succeeds_after_transient_failure(self, fake_server):
        from fake_openai_server import _Handler
        from axon.resilience import ResilientProviderWrapper, RetryConfig

        _Handler.fail_next = 2
        try:
            provider = self._make_provider(fake_server)
            wrapper = ResilientProviderWrapper("openai", retry_config=RetryConfig(max_retries=3, base_delay_seconds=0.01))

            def _do_call():
                return provider.call(prompt="retry test", model="gpt-4", max_tokens=10)

            result = wrapper.execute_with_retry(_do_call)
            assert isinstance(result, Ok)
            assert "Fake response to:" in result.ok_value
        finally:
            _Handler.fail_next = 0

    def test_retry_exhausted_returns_error(self, fake_server):
        from fake_openai_server import _Handler
        from axon.resilience import ResilientProviderWrapper, RetryConfig

        _Handler.fail_next = 10
        try:
            provider = self._make_provider(fake_server)
            wrapper = ResilientProviderWrapper("openai", retry_config=RetryConfig(max_retries=2, base_delay_seconds=0.01))

            def _do_call():
                return provider.call(prompt="retry exhausted", model="gpt-4", max_tokens=10)

            result = wrapper.execute_with_retry(_do_call)
            assert isinstance(result, Err)
            assert result.err_value.kind.value in ("server_error", "unknown")
        finally:
            _Handler.fail_next = 0

    def test_circuit_breaker_opens_after_failures(self, fake_server):
        from fake_openai_server import _Handler
        from axon.resilience import ResilientProviderWrapper, CircuitBreakerConfig, RetryConfig

        _Handler.fail_next = 10
        try:
            provider = self._make_provider(fake_server)
            wrapper = ResilientProviderWrapper(
                "openai",
                retry_config=RetryConfig(max_retries=1, base_delay_seconds=0.005),
                circuit_config=CircuitBreakerConfig(failure_threshold=2, recovery_timeout_seconds=5.0),
            )

            def _do_call():
                return provider.call(prompt="circuit test", model="gpt-4", max_tokens=10)

            # First call fails, retries once, circuit breaker counts 1 failure
            wrapper.execute_with_retry(_do_call)
            # Second call fails, retries once, circuit breaker opens
            wrapper.execute_with_retry(_do_call)
            # Third call should be rejected by circuit breaker
            result = wrapper.execute_with_retry(_do_call)
            assert isinstance(result, Err)
            assert "Circuit breaker" in result.err_value.message
        finally:
            _Handler.fail_next = 0
