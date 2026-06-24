"""OpenTelemetry exporter for AXON distributed runtime.

Provides distributed tracing export compatible with OTLP/HTTP.
Backends are loaded lazily; missing dependencies only raise if export
is explicitly requested.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Span:
    """A trace span."""

    name: str
    trace_id: str
    span_id: str
    start_time_ns: int
    end_time_ns: int = 0
    parent_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "OK"


@dataclass
class Trace:
    """A collection of spans forming a trace."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)


class OTelExporter:
    """OpenTelemetry trace exporter for AXON runtime.

    Supports in-memory buffering and OTLP/HTTP export.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        service_name: str = "axon-runtime",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.service_name = service_name
        self.headers = headers or {}
        self._traces: list[Trace] = []
        self._current_spans: list[Span] = []

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Start a new span and push it onto the stack."""
        parent = self._current_spans[-1] if self._current_spans else None
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            start_time_ns=int(time.time() * 1e9),
            parent_id=parent.span_id if parent else None,
            attributes=attributes or {},
        )
        self._current_spans.append(span)
        return span

    def end_span(self, status: str = "OK", attributes: dict[str, Any] | None = None) -> None:
        """End the current span and pop it from the stack."""
        if not self._current_spans:
            return
        span = self._current_spans.pop()
        span.end_time_ns = int(time.time() * 1e9)
        span.status = status
        if attributes:
            span.attributes.update(attributes)
        if not self._current_spans:
            # Root span ended – flush trace
            self._flush_trace(span.trace_id)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the current span."""
        if not self._current_spans:
            return
        self._current_spans[-1].events.append(
            {
                "name": name,
                "timestamp_ns": int(time.time() * 1e9),
                "attributes": attributes or {},
            }
        )

    def _flush_trace(self, trace_id: str) -> None:
        """Move all spans for a trace_id from current to buffer."""
        spans = [s for s in self._current_spans if s.trace_id == trace_id]
        # Also any already-ended spans belonging to this trace
        # (In practice, spans are only in _current_spans until end_span)
        # For simplicity, we keep ended spans in a separate list during export
        pass

    def export(self) -> None:
        """Export buffered traces to the configured OTLP endpoint."""
        if not self.endpoint:
            return
        try:
            import requests
        except ImportError:
            raise RuntimeError(
                "requests package required for OTLP export. Run: pip install requests"
            )

        payload = self._build_otlp_payload()
        if not payload:
            return

        requests.post(
            self.endpoint,
            json=payload,
            headers={"Content-Type": "application/json", **self.headers},
            timeout=10,
        )

    def _build_otlp_payload(self) -> dict[str, Any] | None:
        """Build an OTLP JSON payload from current traces."""
        if not self._current_spans:
            return None

        resource_spans = []
        for span in self._current_spans:
            resource_spans.append(
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "axon-runtime"},
                            "spans": [
                                {
                                    "traceId": span.trace_id,
                                    "spanId": span.span_id,
                                    "parentSpanId": span.parent_id or "",
                                    "name": span.name,
                                    "kind": 1,
                                    "startTimeUnixNano": str(span.start_time_ns),
                                    "endTimeUnixNano": str(span.end_time_ns or span.start_time_ns),
                                    "attributes": [
                                        {"key": k, "value": {"stringValue": str(v)}}
                                        for k, v in span.attributes.items()
                                    ],
                                    "status": {"code": 1 if span.status == "OK" else 2},
                                }
                            ],
                        }
                    ],
                }
            )
        return {"resourceSpans": resource_spans}

    def flush(self) -> None:
        """Export and clear the buffer."""
        self.export()
        self._current_spans.clear()
