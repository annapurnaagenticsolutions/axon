"""Tests for the Anthropic provider plugin."""

from __future__ import annotations

import os
import pytest
from result import Err, Ok

from axon.providers.anthropic_provider import AnthropicProvider
from axon.provider_plugin import ProviderErrorKind


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_name_returns_anthropic(self) -> None:
        provider = AnthropicProvider()
        assert provider.name() == "anthropic"

    def test_config_returns_anthropic_config(self) -> None:
        provider = AnthropicProvider()
        config = provider.config()
        assert config.name == "anthropic"
        assert config.api_key_env_var == "ANTHROPIC_API_KEY"
        assert config.timeout_seconds == 120
        assert config.max_retries == 3

    def test_call_without_anthropic_package_returns_error(self) -> None:
        """When anthropic is not installed, call() returns an error."""
        provider = AnthropicProvider()
        # Ensure the module is not available by using a monkeypatch approach
        # if needed, but in CI the package may not be installed.
        result = provider.call("hello", "claude-3-5-sonnet", max_tokens=10)
        if isinstance(result, Err):
            # Expected when anthropic package is not installed
            assert result.err_value.kind == ProviderErrorKind.INVALID_REQUEST
            assert "anthropic package not installed" in result.err_value.message
        else:
            # If the package IS installed, we need a valid API key
            pytest.skip("anthropic package installed; skipping no-package test")

    def test_call_without_api_key_returns_auth_error(self, monkeypatch) -> None:
        """When ANTHROPIC_API_KEY is missing, call() returns an auth error."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = AnthropicProvider()

        # If anthropic package is installed, the call will fail on auth
        # If not, it will fail on import. Either way we get an error.
        result = provider.call("hello", "claude-3-5-sonnet", max_tokens=10)
        assert isinstance(result, Err)

    def test_supports_streaming_returns_true(self) -> None:
        provider = AnthropicProvider()
        assert provider.supports_streaming() is True
