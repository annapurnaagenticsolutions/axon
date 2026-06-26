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
        response_format: Optional[str] = None,
    ) -> Result[str, ProviderError]:
        """Invoke the mock provider with a prompt."""
        # Generate a key for response lookup
        key = f"{model}:{prompt[:100]}"
        
        if key in self._responses:
            response = self._responses[key]
            return Ok(response.text)

        # If response_format is set, return a JSON-structured mock response
        if response_format:
            return Ok(self._generate_structured_mock(response_format))

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

    def _generate_structured_mock(self, type_str: str) -> str:
        """Generate a JSON mock response based on an AXON type string."""
        import json
        import re

        # Parse the type string to generate appropriate mock JSON
        type_str = type_str.strip()

        # Primitive types
        if type_str == "Str":
            return json.dumps("mock string")
        if type_str == "Int":
            return json.dumps(42)
        if type_str == "Float":
            return json.dumps(3.14)
        if type_str == "Bool":
            return json.dumps(True)
        if type_str in ("None", "Null"):
            return json.dumps(None)

        # Option<T> — return Some(T)
        opt_match = re.match(r"Option<(.+)>", type_str)
        if opt_match:
            return self._generate_structured_mock(opt_match.group(1))

        # List<T> — return [T]
        list_match = re.match(r"List<(.+)>", type_str)
        if list_match:
            inner = self._generate_structured_mock(list_match.group(1))
            return f"[{inner}]"

        # Record types: { field1: Type1, field2: Type2 }
        if type_str.startswith("{") and type_str.endswith("}"):
            fields = {}
            inner = type_str[1:-1]
            for field_def in inner.split(","):
                field_def = field_def.strip()
                if ":" in field_def:
                    name, ftype = field_def.split(":", 1)
                    name = name.strip()
                    ftype = ftype.strip()
                    fields[name] = json.loads(self._generate_structured_mock(ftype))
            return json.dumps(fields)

        # Named type alias — return a dict with a "name" field
        return json.dumps({"name": type_str.lower(), "type": type_str})
