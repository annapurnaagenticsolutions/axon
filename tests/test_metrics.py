"""Tests for metrics collection."""

from __future__ import annotations

import time

from axon.metrics import (
    MetricsCollector,
    MetricType,
    ProviderCallMetrics,
    RuntimeMetrics,
    ToolDispatchMetrics,
    get_metrics_collector,
    reset_metrics,
)


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_counter(self) -> None:
        collector = MetricsCollector()
        collector.increment_counter("provider_calls", 1)
        collector.increment_counter("provider_calls", 1)
        assert collector.get_counter("provider_calls") == 2

    def test_counter_with_labels(self) -> None:
        collector = MetricsCollector()
        collector.increment_counter("provider_calls", 1, {"provider": "openai"})
        collector.increment_counter("provider_calls", 1, {"provider": "anthropic"})
        collector.increment_counter("provider_calls", 1, {"provider": "openai"})
        assert collector.get_counter("provider_calls", {"provider": "openai"}) == 2
        assert collector.get_counter("provider_calls", {"provider": "anthropic"}) == 1

    def test_gauge(self) -> None:
        collector = MetricsCollector()
        collector.set_gauge("active_agents", 5.0)
        assert collector.get_gauge("active_agents") == 5.0
        collector.set_gauge("active_agents", 3.0)
        assert collector.get_gauge("active_agents") == 3.0

    def test_histogram(self) -> None:
        collector = MetricsCollector()
        collector.record_histogram("latency_ms", 10.0)
        collector.record_histogram("latency_ms", 20.0)
        collector.record_histogram("latency_ms", 30.0)
        stats = collector.get_histogram_stats("latency_ms")
        assert stats["count"] == 3.0
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0
        assert stats["avg"] == 20.0

    def test_histogram_empty(self) -> None:
        collector = MetricsCollector()
        stats = collector.get_histogram_stats("latency_ms")
        assert stats["count"] == 0.0

    def test_to_dict(self) -> None:
        collector = MetricsCollector()
        collector.increment_counter("calls", 5)
        collector.set_gauge("agents", 2.0)
        collector.record_histogram("latency", 100.0)
        data = collector.to_dict()
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data


class TestRuntimeMetrics:
    """Tests for RuntimeMetrics."""

    def test_record_provider_call(self) -> None:
        metrics = RuntimeMetrics()
        metrics.record_provider_call(
            ProviderCallMetrics(
                provider_name="openai",
                model="gpt-4",
                latency_ms=100.0,
                success=True,
            )
        )
        assert len(metrics.provider_calls) == 1
        assert metrics.provider_calls[0].provider_name == "openai"

    def test_record_tool_dispatch(self) -> None:
        metrics = RuntimeMetrics()
        metrics.record_tool_dispatch(
            ToolDispatchMetrics(
                tool_name="Search",
                latency_ms=50.0,
                success=True,
            )
        )
        assert len(metrics.tool_dispatches) == 1

    def test_to_dict(self) -> None:
        metrics = RuntimeMetrics()
        metrics.record_provider_call(
            ProviderCallMetrics(
                provider_name="openai",
                model="gpt-4",
                latency_ms=100.0,
                success=True,
            )
        )
        metrics.record_tool_dispatch(
            ToolDispatchMetrics(
                tool_name="Search",
                latency_ms=50.0,
                success=True,
            )
        )
        metrics.finish()
        data = metrics.to_dict()
        assert "total_runtime_ms" in data
        assert data["aggregates"]["total_provider_calls"] == 1
        assert data["aggregates"]["total_tool_dispatches"] == 1
        assert data["aggregates"]["successful_provider_calls"] == 1
        assert data["aggregates"]["avg_provider_latency_ms"] == 100.0

    def test_failed_calls(self) -> None:
        metrics = RuntimeMetrics()
        metrics.record_provider_call(
            ProviderCallMetrics(
                provider_name="openai",
                model="gpt-4",
                latency_ms=100.0,
                success=False,
                error_kind="rate_limit",
            )
        )
        data = metrics.to_dict()
        assert data["aggregates"]["successful_provider_calls"] == 0


class TestGlobalCollector:
    """Tests for global metrics collector."""

    def test_get_collector(self) -> None:
        reset_metrics()
        collector = get_metrics_collector()
        assert collector is not None
        collector.increment_counter("test", 1)
        assert get_metrics_collector().get_counter("test") == 1

    def test_reset(self) -> None:
        reset_metrics()
        collector = get_metrics_collector()
        collector.increment_counter("test", 1)
        reset_metrics()
        assert get_metrics_collector().get_counter("test") == 0
