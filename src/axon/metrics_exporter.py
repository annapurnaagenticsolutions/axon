"""Metrics exporter for AXON runtime observability.

Provides structured formatting and file export for collected
runtime metrics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from axon.metrics import MetricsCollector


class MetricsExporter:
    """Export and format AXON runtime metrics."""

    def __init__(self, collector: MetricsCollector) -> None:
        self._collector = collector

    def to_dict(self) -> dict[str, Any]:
        """Return metrics as a plain dictionary."""
        return self._collector.to_dict()

    def to_json(self) -> str:
        """Return metrics as a JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_text(self) -> str:
        """Return metrics as a human-readable text summary."""
        lines: list[str] = ["AXON Runtime Metrics", "=" * 40]
        data = self.to_dict()

        counters = data.get("counters", {})
        if counters:
            lines.append("\nCounters:")
            for key, value in sorted(counters.items()):
                lines.append(f"  {key}: {value}")

        gauges = data.get("gauges", {})
        if gauges:
            lines.append("\nGauges:")
            for key, value in sorted(gauges.items()):
                lines.append(f"  {key}: {value}")

        histograms = data.get("histograms", {})
        if histograms:
            lines.append("\nHistograms:")
            for key, stats in sorted(histograms.items()):
                lines.append(f"  {key}:")
                lines.append(f"    count: {stats.get('count', 0)}")
                lines.append(f"    avg:   {stats.get('avg', 0):.2f} ms")
                lines.append(f"    min:   {stats.get('min', 0):.2f} ms")
                lines.append(f"    max:   {stats.get('max', 0):.2f} ms")
                lines.append(f"    p50:   {stats.get('p50', 0):.2f} ms")
                lines.append(f"    p99:   {stats.get('p99', 0):.2f} ms")

        provider_calls = data.get("provider_calls", [])
        if provider_calls:
            lines.append("\nProvider Calls:")
            for call in provider_calls:
                status = "OK" if call.get("success") else "ERR"
                lines.append(
                    f"  {call.get('provider_name', '?')} ({call.get('model', '?')}) "
                    f"- {call.get('latency_ms', 0):.2f} ms [{status}]"
                )

        tool_dispatches = data.get("tool_dispatches", [])
        if tool_dispatches:
            lines.append("\nTool Dispatches:")
            for td in tool_dispatches:
                status = "OK" if td.get("success") else "ERR"
                lines.append(
                    f"  {td.get('tool_name', '?')} - {td.get('latency_ms', 0):.2f} ms [{status}]"
                )

        return "\n".join(lines)

    def export_to_file(self, path: Path, *, format: str = "json") -> None:
        """Write metrics to a file.

        Args:
            path: destination file path
            format: ``json`` or ``text``
        """
        if format == "json":
            path.write_text(self.to_json(), encoding="utf-8")
        else:
            path.write_text(self.to_text(), encoding="utf-8")
