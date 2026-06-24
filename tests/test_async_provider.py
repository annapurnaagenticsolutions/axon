"""Tests for async provider methods."""

from __future__ import annotations

import asyncio
import pytest
from result import Ok, Err

from axon.providers.mock_provider import MockProviderPlugin
from axon.provider_plugin import ProviderErrorKind


class TestMockProviderAsync:
    """Tests for MockProviderPlugin async methods."""

    @pytest.mark.asyncio
    async def test_call_async_returns_result(self) -> None:
        provider = MockProviderPlugin()
        result = await provider.call_async("hello", "mock-model", max_tokens=10)
        assert isinstance(result, Ok)
        assert "mock" in result.ok_value.lower()

    @pytest.mark.asyncio
    async def test_call_stream_async_yields_chunks(self) -> None:
        provider = MockProviderPlugin()
        chunks = []
        async for chunk in provider.call_stream_async("hello", "mock-model", max_tokens=10):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert all(isinstance(c, Ok) for c in chunks)

    @pytest.mark.asyncio
    async def test_call_async_with_different_prompts(self) -> None:
        provider = MockProviderPlugin()
        result1 = await provider.call_async("hello", "mock-model", max_tokens=10)
        result2 = await provider.call_async("world", "mock-model", max_tokens=10)
        assert isinstance(result1, Ok)
        assert isinstance(result2, Ok)
        # Deterministic mock should return same output for same model
        assert result1.ok_value == result2.ok_value


class TestOpenAIProviderAsync:
    """Tests for OpenAIProvider async methods."""

    @pytest.mark.asyncio
    async def test_call_async_without_package(self) -> None:
        from axon.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        # When openai package is not installed, returns error
        result = await provider.call_async("hello", "gpt-4", max_tokens=10)
        # If openai is installed but no API key, returns auth error
        assert isinstance(result, Err)

    @pytest.mark.asyncio
    async def test_call_stream_async_without_package(self) -> None:
        from axon.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        chunks = []
        async for chunk in provider.call_stream_async("hello", "gpt-4", max_tokens=10):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert isinstance(chunks[0], Err)


class TestAnthropicProviderAsync:
    """Tests for AnthropicProvider async methods."""

    @pytest.mark.asyncio
    async def test_call_async_without_package(self) -> None:
        from axon.providers.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider()
        result = await provider.call_async("hello", "claude-4", max_tokens=10)
        assert isinstance(result, Err)

    @pytest.mark.asyncio
    async def test_call_stream_async_without_package(self) -> None:
        from axon.providers.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider()
        chunks = []
        async for chunk in provider.call_stream_async("hello", "claude-4", max_tokens=10):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert isinstance(chunks[0], Err)
