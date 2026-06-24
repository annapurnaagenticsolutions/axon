"""Provider registry for AXON Phase 2 runtime.

This module manages registration and discovery of provider plugins.
"""

from __future__ import annotations

from typing import Dict, Optional
from result import Result, Err, Ok

from axon.provider_plugin import ProviderPlugin, ProviderError, ProviderErrorKind, ProviderConfig


class ProviderRegistry:
    """Registry for provider plugins."""
    
    def __init__(self):
        self._providers: Dict[str, ProviderPlugin] = {}
    
    def register(self, provider: ProviderPlugin) -> None:
        """Register a provider plugin."""
        self._providers[provider.name()] = provider
    
    def get(self, name: str) -> Optional[ProviderPlugin]:
        """Get a provider plugin by name."""
        return self._providers.get(name)
    
    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())
    
    def resolve_provider_reference(self, reference: str) -> Result[ProviderPlugin, ProviderError]:
        """Resolve a provider reference (e.g., '@anthropic/claude-4') to a plugin.
        
        Args:
            reference: Provider reference in format '@provider/model'
        
        Returns:
            Result with the provider plugin or a ProviderError
        """
        if not reference.startswith("@"):
            return Err(ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                message=f"Invalid provider reference: {reference} (must start with @)",
                retryable=False,
            ))
        
        parts = reference[1:].split("/", 1)
        if len(parts) < 1:
            return Err(ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                message=f"Invalid provider reference: {reference} (missing provider name)",
                retryable=False,
            ))
        
        provider_name = parts[0]
        provider = self.get(provider_name)
        
        if not provider:
            return Err(ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                message=f"Provider not found: {provider_name}",
                retryable=False,
            ))
        
        return Ok(provider)


# Global registry instance
_global_registry = ProviderRegistry()


def register_provider(provider: ProviderPlugin) -> None:
    """Register a provider plugin in the global registry."""
    _global_registry.register(provider)


def get_provider(name: str) -> Optional[ProviderPlugin]:
    """Get a provider plugin from the global registry."""
    return _global_registry.get(name)


def resolve_provider_reference(reference: str) -> Result[ProviderPlugin, ProviderError]:
    """Resolve a provider reference using the global registry."""
    return _global_registry.resolve_provider_reference(reference)


def list_providers() -> list[str]:
    """List all registered provider names from the global registry."""
    return _global_registry.list_providers()
