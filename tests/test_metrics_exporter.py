"""Tests for MetricsExporter."""

import json
from pathlib import Path

from axon.metrics import MetricsCollector, ProviderCallMetrics, ToolDispatchMetrics
from axon.metrics_exporter import MetricsExporter


def test_exporter_to_json() -> None:
    collector = MetricsCollector()
    collector.record_provider_call(
        ProviderCallMetrics(provider_name="MockProvider", model="gpt", latency_ms=42.0, success=True)
    )
    collector.record_tool_dispatch(
        ToolDispatchMetrics(tool_name="NoOp", latency_ms=12.0, success=True)
    )

    exporter = MetricsExporter(collector)
    data = json.loads(exporter.to_json())
    assert "counters" in data
    assert "provider_calls" in data
    assert len(data["provider_calls"]) == 1
    assert data["provider_calls"][0]["model"] == "gpt"


def test_exporter_to_text() -> None:
    collector = MetricsCollector()
    collector.record_provider_call(
        ProviderCallMetrics(provider_name="MockProvider", model="gpt", latency_ms=42.0, success=True)
    )
    exporter = MetricsExporter(collector)
    text = exporter.to_text()
    assert "AXON Runtime Metrics" in text
    assert "Provider Calls:" in text
    assert "MockProvider" in text


def test_exporter_export_to_file_json(tmp_path: Path) -> None:
    collector = MetricsCollector()
    collector.increment_counter("test_counter", value=5)
    exporter = MetricsExporter(collector)
    path = tmp_path / "metrics.json"
    exporter.export_to_file(path, format="json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["counters"]["test_counter"] == 5


def test_exporter_export_to_file_text(tmp_path: Path) -> None:
    collector = MetricsCollector()
    collector.increment_counter("test_counter", value=3)
    exporter = MetricsExporter(collector)
    path = tmp_path / "metrics.txt"
    exporter.export_to_file(path, format="text")
    text = path.read_text(encoding="utf-8")
    assert "AXON Runtime Metrics" in text
    assert "test_counter: 3" in text


def test_exporter_histogram_stats_in_output() -> None:
    collector = MetricsCollector()
    for i in range(1, 6):
        collector.record_histogram("latency", value=float(i * 10))
    exporter = MetricsExporter(collector)
    data = json.loads(exporter.to_json())
    assert "histograms" in data
    stats = data["histograms"]["latency"]
    assert stats["count"] == 5
    assert stats["avg"] == 30.0
    assert stats["min"] == 10.0
    assert stats["max"] == 50.0
