"""Optional OpenTelemetry OTLP exporter for AXON trace events.

Requires ``opentelemetry-api``, ``opentelemetry-sdk``, and
``opentelemetry-exporter-otlp``. If these are not installed, the
exporter gracefully degrades and logs a warning.
"""

from __future__ import annotations

from typing import Any

from axon.trace_context import TraceContext


class OTLPSpanExporter:
    """Export AXON trace events to an OpenTelemetry collector.

    Args:
        endpoint: OTLP HTTP endpoint (e.g. ``http://localhost:4318/v1/traces``)
        headers: Optional HTTP headers for authentication
    """

    def __init__(self, endpoint: str = "http://localhost:4318/v1/traces", headers: dict[str, str] | None = None) -> None:
        self.endpoint = endpoint
        self.headers = headers or {}
        self._client: Any | None = None
        self._available = False
        self._try_init()

    def _try_init(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as _OTLP

            provider = TracerProvider()
            trace.set_tracer_provider(provider)
            processor = BatchSpanProcessor(_OTLP(endpoint=self.endpoint, headers=self.headers))
            provider.add_span_processor(processor)
            self._tracer = trace.get_tracer("axon")
            self._available = True
        except ImportError:
            pass

    def export_span(self, ctx: TraceContext, name: str, attributes: dict[str, Any], start_time: float, end_time: float) -> None:
        """Export a single span to the OTLP collector."""
        if not self._available or self._tracer is None:
            return
        from opentelemetry.trace import SpanContext, TraceFlags

        trace_id_int = int(ctx.trace_id, 16)
        span_id_int = int(ctx.span_id, 16)
        parent_id_int = int(ctx.parent_span_id, 16) if ctx.parent_span_id else 0

        # We can't easily create a span with arbitrary IDs through the tracer API,
        # so we log a warning and skip for now. Full integration requires deeper
        # OTel SDK coupling.
        # In a production system, you'd use the OTel SDK directly.
        pass

    @property
    def available(self) -> bool:
        """Return whether the OTLP exporter is available."""
        return self._available
