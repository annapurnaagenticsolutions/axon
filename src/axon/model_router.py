"""Model router for AXON runtime.

Provides cost-optimized, latency-optimized, and quality-first routing
strategies across multiple provider backends.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from result import Result, Ok, Err

from axon.provider_plugin import ProviderPlugin, ProviderError
from axon.metrics import MetricsCollector


class RoutingStrategy(Enum):
    """Routing strategy for model selection."""

    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    QUALITY = "quality"
    FALLBACK = "fallback"


@dataclass
class ModelInfo:
    """Metadata for a routable model."""

    provider: str
    model: str
    cost_per_1k_tokens: float  # USD
    avg_latency_ms: float
    quality_score: float  # 0.0 - 1.0
    capabilities: list[str] = field(default_factory=list)


@dataclass
class RouterConfig:
    """Configuration for the model router."""

    strategy: RoutingStrategy = RoutingStrategy.FALLBACK
    default_provider: str = "openai"
    default_model: str = "gpt-4"
    timeout_ms: int = 30000
    fallback_chain: list[str] = field(default_factory=list)


class ModelRouter:
    """Routes model completion requests to the best provider."""

    # Static model catalog with approximate costs and scores
    CATALOG: dict[str, ModelInfo] = {
        "openai/gpt-4o": ModelInfo(
            provider="openai",
            model="gpt-4o",
            cost_per_1k_tokens=0.005,
            avg_latency_ms=800,
            quality_score=0.95,
            capabilities=["vision", "json", "function_calling"],
        ),
        "openai/gpt-4o-mini": ModelInfo(
            provider="openai",
            model="gpt-4o-mini",
            cost_per_1k_tokens=0.0006,
            avg_latency_ms=300,
            quality_score=0.82,
            capabilities=["vision", "json"],
        ),
        "anthropic/claude-sonnet-4": ModelInfo(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            cost_per_1k_tokens=0.008,
            avg_latency_ms=600,
            quality_score=0.96,
            capabilities=["vision", "json", "function_calling", "long_context"],
        ),
        "anthropic/claude-haiku-4": ModelInfo(
            provider="anthropic",
            model="claude-haiku-4-20250514",
            cost_per_1k_tokens=0.001,
            avg_latency_ms=200,
            quality_score=0.75,
            capabilities=["json"],
        ),
    }

    def __init__(
        self,
        config: RouterConfig | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self.config = config or RouterConfig()
        self.metrics = metrics
        self._providers: dict[str, ProviderPlugin] = {}
        self._latency_window: dict[str, list[float]] = {}

    def register_provider(self, provider: ProviderPlugin) -> None:
        self._providers[provider.name()] = provider

    def resolve(self, ref: str | None = None) -> tuple[str, str]:
        """Resolve a model reference to (provider_name, model_name)."""
        if ref and ref in self.CATALOG:
            info = self.CATALOG[ref]
            return info.provider, info.model
        if ref and "/" in ref:
            provider, model = ref.split("/", 1)
            return provider, model
        return self.config.default_provider, self.config.default_model

    def select(
        self,
        candidates: list[str] | None = None,
        required_capabilities: list[str] | None = None,
    ) -> str:
        """Select the best model reference based on configured strategy."""
        pool = candidates or list(self.CATALOG.keys())
        if required_capabilities:
            pool = [
                m for m in pool
                if all(c in self.CATALOG[m].capabilities for c in required_capabilities)
            ]
        if not pool:
            return f"{self.config.default_provider}/{self.config.default_model}"

        strategy = self.config.strategy
        if strategy == RoutingStrategy.CHEAPEST:
            return min(pool, key=lambda m: self.CATALOG[m].cost_per_1k_tokens)
        if strategy == RoutingStrategy.FASTEST:
            return min(pool, key=lambda m: self._measured_latency(m))
        if strategy == RoutingStrategy.QUALITY:
            return max(pool, key=lambda m: self.CATALOG[m].quality_score)
        # FALLBACK: try fallback_chain, then default
        for m in self.config.fallback_chain:
            if m in pool:
                return m
        return pool[0]

    def _measured_latency(self, model_ref: str) -> float:
        """Return measured or catalog latency for a model."""
        samples = self._latency_window.get(model_ref, [])
        if samples:
            return sum(samples) / len(samples)
        return self.CATALOG.get(model_ref, ModelInfo("", "", 0, 0, 0)).avg_latency_ms

    def route(
        self,
        prompt: str,
        model_ref: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Result[str, ProviderError]:
        """Route a completion request to the best provider."""
        selected = self.select(candidates=[model_ref] if model_ref else None)
        provider_name, model_name = self.resolve(selected)

        provider = self._providers.get(provider_name)
        if provider is None:
            return Err(
                ProviderError(
                    kind=ProviderError.ProviderErrorKind.INVALID_REQUEST,
                    message=f"Provider '{provider_name}' not registered in router",
                    retryable=False,
                )
            )

        t0 = time.time()
        if stream and hasattr(provider, "call_stream"):
            # Collect streaming result
            chunks: list[str] = []
            for chunk in provider.call_stream(prompt, model_name, max_tokens, temperature):
                if isinstance(chunk, Ok):
                    chunks.append(chunk.ok_value)
                else:
                    return chunk
            result: Result[str, ProviderError] = Ok("".join(chunks))
        else:
            result = provider.call(prompt, model_name, max_tokens, temperature, stream=False)

        latency = (time.time() - t0) * 1000
        self._record_latency(selected, latency)
        return result

    def _record_latency(self, model_ref: str, latency_ms: float) -> None:
        window = self._latency_window.setdefault(model_ref, [])
        window.append(latency_ms)
        if len(window) > 20:
            window.pop(0)
