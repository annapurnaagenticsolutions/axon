"""Structured metrics and observability for AXON Phase 4.

This module provides runtime metrics collection for monitoring
provider calls, tool dispatches, and execution performance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetricType(Enum):
    """Categories of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """A single metric data point."""
    name: str
    value: float
    metric_type: MetricType
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProviderCallMetrics:
    """Metrics for a single provider call."""
    provider_name: str
    model: str
    latency_ms: float
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    success: bool = True
    error_kind: str | None = None


@dataclass
class ToolDispatchMetrics:
    """Metrics for a single tool dispatch."""
    tool_name: str
    latency_ms: float
    success: bool = True
    error_message: str | None = None


@dataclass
class RuntimeMetrics:
    """Aggregate runtime metrics."""
    provider_calls: list[ProviderCallMetrics] = field(default_factory=list)
    tool_dispatches: list[ToolDispatchMetrics] = field(default_factory=list)
    total_runtime_ms: float = 0.0
    start_time: float = field(default_factory=time.time)
    
    def record_provider_call(self, metrics: ProviderCallMetrics) -> None:
        """Record a provider call metric."""
        self.provider_calls.append(metrics)
    
    def record_tool_dispatch(self, metrics: ToolDispatchMetrics) -> None:
        """Record a tool dispatch metric."""
        self.tool_dispatches.append(metrics)
    
    def finish(self) -> None:
        """Mark the runtime as finished."""
        self.total_runtime_ms = (time.time() - self.start_time) * 1000
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a dictionary for serialization."""
        return {
            "total_runtime_ms": self.total_runtime_ms,
            "provider_calls": [
                {
                    "provider_name": m.provider_name,
                    "model": m.model,
                    "latency_ms": m.latency_ms,
                    "tokens_prompt": m.tokens_prompt,
                    "tokens_completion": m.tokens_completion,
                    "success": m.success,
                    "error_kind": m.error_kind,
                }
                for m in self.provider_calls
            ],
            "tool_dispatches": [
                {
                    "tool_name": m.tool_name,
                    "latency_ms": m.latency_ms,
                    "success": m.success,
                    "error_message": m.error_message,
                }
                for m in self.tool_dispatches
            ],
            "aggregates": {
                "total_provider_calls": len(self.provider_calls),
                "successful_provider_calls": sum(1 for m in self.provider_calls if m.success),
                "total_tool_dispatches": len(self.tool_dispatches),
                "successful_tool_dispatches": sum(1 for m in self.tool_dispatches if m.success),
                "avg_provider_latency_ms": (
                    sum(m.latency_ms for m in self.provider_calls) / len(self.provider_calls)
                    if self.provider_calls else 0.0
                ),
                "avg_tool_latency_ms": (
                    sum(m.latency_ms for m in self.tool_dispatches) / len(self.tool_dispatches)
                    if self.tool_dispatches else 0.0
                ),
            },
        }


class MetricsCollector:
    """Global metrics collector for AXON runtime."""
    
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = {}
        self.provider_calls: list[ProviderCallMetrics] = []
        self.tool_dispatches: list[ToolDispatchMetrics] = []
    
    def increment_counter(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        key = self._key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        key = self._key(name, labels)
        self.gauges[key] = value
    
    def record_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a value in a histogram."""
        key = self._key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> int:
        """Get a counter value."""
        key = self._key(name, labels)
        return self.counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get a gauge value."""
        key = self._key(name, labels)
        return self.gauges.get(key, 0.0)
    
    def get_histogram_stats(self, name: str, labels: dict[str, str] | None = None) -> dict[str, float]:
        """Get histogram statistics."""
        key = self._key(name, labels)
        values = self.histograms.get(key, [])
        if not values:
            return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "p50": 0.0, "p99": 0.0}
        sorted_values = sorted(values)
        n = len(sorted_values)
        return {
            "count": float(n),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / n,
            "p50": sorted_values[n // 2],
            "p99": sorted_values[int(n * 0.99)] if n >= 100 else sorted_values[-1],
        }
    
    def record_provider_call(self, metrics: ProviderCallMetrics) -> None:
        """Record a provider call metric."""
        self.provider_calls.append(metrics)
        self.increment_counter("provider_calls_total", labels={"provider": metrics.provider_name, "model": metrics.model, "success": str(metrics.success)})
        self.record_histogram("provider_latency_ms", metrics.latency_ms, labels={"provider": metrics.provider_name})

    def record_tool_dispatch(self, metrics: ToolDispatchMetrics) -> None:
        """Record a tool dispatch metric."""
        self.tool_dispatches.append(metrics)
        self.increment_counter("tool_dispatches_total", labels={"tool": metrics.tool_name, "success": str(metrics.success)})
        self.record_histogram("tool_latency_ms", metrics.latency_ms, labels={"tool": metrics.tool_name})

    def to_dict(self) -> dict[str, Any]:
        """Export all metrics as a dictionary."""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                key: self.get_histogram_stats(key)
                for key in self.histograms
            },
            "provider_calls": [
                {
                    "provider_name": m.provider_name,
                    "model": m.model,
                    "latency_ms": m.latency_ms,
                    "success": m.success,
                }
                for m in self.provider_calls
            ],
            "tool_dispatches": [
                {
                    "tool_name": m.tool_name,
                    "latency_ms": m.latency_ms,
                    "success": m.success,
                }
                for m in self.tool_dispatches
            ],
        }
    
    @staticmethod
    def _key(name: str, labels: dict[str, str] | None = None) -> str:
        """Build a unique key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global metrics collector instance
_global_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector (lazily initialized)."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def reset_metrics() -> None:
    """Reset the global metrics collector."""
    global _global_collector
    _global_collector = MetricsCollector()
