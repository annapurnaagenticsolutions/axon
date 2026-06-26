"""Provider plugin protocol for AXON Phase 2 runtime.

This module defines the standard interface for provider plugins that enable
AXON agents to call model providers (e.g., Anthropic, OpenAI) with proper
mocking, security, and trace guarantees.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Iterator, Optional
from result import Result, Err, Ok

from axon.secret_manager import SecretManager, get_default_secret_manager


class ProviderErrorKind(Enum):
    """Categories of provider errors."""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderError:
    """Error type for provider failures."""
    kind: ProviderErrorKind
    message: str
    status_code: Optional[int] = None
    retryable: bool = False
    
    def __str__(self) -> str:
        status = f" (status {self.status_code})" if self.status_code else ""
        return f"{self.kind.value}: {self.message}{status}"


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a provider plugin."""
    name: str  # e.g., "anthropic", "openai"
    api_key_env_var: str  # e.g., "ANTHROPIC_API_KEY"
    base_url: Optional[str] = None  # Optional custom base URL
    timeout_seconds: int = 120
    max_retries: int = 3
    secret_manager: SecretManager = field(default_factory=get_default_secret_manager)

    def get_api_key(self) -> Result[str, ProviderError]:
        """Load API key from the configured SecretManager."""
        api_key = self.secret_manager.get(
            self.api_key_env_var,
            caller=f"{self.name}_provider",
        )
        if not api_key:
            return Err(ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                message=f"API key not found for provider '{self.name}' (key: {self.api_key_env_var})",
                retryable=False,
            ))
        return Ok(api_key)


class ProviderPlugin(ABC):
    """Standard interface for provider plugins."""
    
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'anthropic', 'openai')."""
        pass
    
    @abstractmethod
    def config(self) -> ProviderConfig:
        """Get provider configuration."""
        pass
    
    @abstractmethod
    def call(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
        stream: bool = False,
        response_format: Optional[str] = None,
    ) -> Result[str, ProviderError]:
        """Invoke the provider with a prompt.
        
        Args:
            prompt: The prompt to send to the provider
            model: The model identifier (e.g., "claude-4", "gpt-4")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            stream: Whether to stream the response (not supported in call())
            response_format: Optional AXON type string for structured output (JSON mode)
        
        Returns:
            Result with the response text or a ProviderError
        """
        pass
    
    @abstractmethod
    def call_stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> Iterator[Result[str, ProviderError]]:
        """Invoke the provider with streaming.
        
        Yields:
            Result with each chunk of the response or a ProviderError
        """
        pass
    
    async def call_async(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> Result[str, ProviderError]:
        """Invoke the provider asynchronously.
        
        Default implementation delegates to sync call().
        Providers should override for true async behavior.
        """
        return self.call(prompt, model, max_tokens, temperature, stream=False)
    
    async def call_stream_async(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> AsyncIterator[Result[str, ProviderError]]:
        """Invoke the provider with async streaming.
        
        Default implementation delegates to sync call_stream().
        Providers should override for true async behavior.
        
        Yields:
            Result with each chunk of the response or a ProviderError
        """
        for chunk in self.call_stream(prompt, model, max_tokens, temperature):
            yield chunk
    
    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming."""
        return True
