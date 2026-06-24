"""Mock provider plugin for AXON Phase 2 runtime testing.

This module provides a deterministic mock provider for testing without
real API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator
from result import Result, Ok

from axon.provider_plugin import (
    ProviderPlugin,
    ProviderConfig,
    ProviderError,
    ProviderErrorKind,
)


@dataclass
class MockResponse:
    """Configured response for the mock provider."""
    text: str
    delay_ms: int = 0  # Simulate latency


class MockProviderPlugin(ProviderPlugin):
    """Deterministic mock provider for testing."""
    
    def __init__(
        self,
        responses: Dict[str, MockResponse] | None = None,
        default_response: str = "Mock response for testing",
    ):
        self._responses = responses or {}
        self._default_response = default_response
        self._config = ProviderConfig(
            name="mock",
            api_key_env_var="MOCK_API_KEY",
            timeout_seconds=120,
            max_retries=3,
        )
    
    def name(self) -> str:
        """Provider name."""
        return "mock"
    
    def config(self) -> ProviderConfig:
        """Get provider configuration."""
        return self._config
    
    def call(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Result[str, ProviderError]:
        """Invoke the mock provider with a prompt."""
        # Generate a key for response lookup
        key = f"{model}:{prompt[:100]}"
        
        if key in self._responses:
            response = self._responses[key]
            return Ok(response.text)
        
        return Ok(self._default_response)
    
    def call_stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> Iterator[Result[str, ProviderError]]:
        """Invoke the mock provider with streaming."""
        key = f"{model}:{prompt[:100]}"
        
        if key in self._responses:
            response = self._responses[key]
            # Simulate streaming by yielding chunks
            chunks = response.text.split()
            for chunk in chunks:
                yield Ok(chunk + " ")
        else:
            # Stream the default response
            chunks = self._default_response.split()
            for chunk in chunks:
                yield Ok(chunk + " ")
    
    def set_response(self, model: str, prompt: str, response: str) -> None:
        """Set a specific response for a model/prompt combination."""
        key = f"{model}:{prompt[:100]}"
        self._responses[key] = MockResponse(text=response)
    
    def clear_responses(self) -> None:
        """Clear all configured responses."""
        self._responses.clear()
