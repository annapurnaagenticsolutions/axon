"""Structured JSON logger for AXON runtime observability.

Emits structured log lines as JSON objects with consistent fields:
  timestamp, level, message, trace_id, span_id, extra fields.

When disabled, all methods are no-ops for zero overhead.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Optional


class StructuredLogger:
    """Structured JSON logger with trace context correlation."""

    def __init__(self, enabled: bool = False, output=None) -> None:
        self.enabled = enabled
        self._output = output or sys.stderr

    def _emit(self, level: str, message: str, **extra: Any) -> None:
        if not self.enabled:
            return
        record: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "level": level,
            "message": message,
        }
        record.update(extra)
        try:
            self._output.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._output.flush()
        except Exception:
            pass

    def debug(self, message: str, **extra: Any) -> None:
        self._emit("debug", message, **extra)

    def info(self, message: str, **extra: Any) -> None:
        self._emit("info", message, **extra)

    def warn(self, message: str, **extra: Any) -> None:
        self._emit("warn", message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self._emit("error", message, **extra)

    def span(self, name: str, trace_id: Optional[str] = None, span_id: Optional[str] = None, **attrs: Any) -> "SpanContext":
        """Start a traced span context."""
        return SpanContext(self, name, trace_id, span_id, attrs)


class SpanContext:
    """Context manager for a structured log span."""

    def __init__(
        self,
        logger: StructuredLogger,
        name: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.logger = logger
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.attributes = attributes or {}
        self._start_time = 0.0

    def __enter__(self) -> "SpanContext":
        self._start_time = time.time()
        self.logger.info(
            f"span_start: {self.name}",
            span_name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            **self.attributes,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = int((time.time() - self._start_time) * 1000)
        status = "error" if exc_val else "ok"
        self.logger.info(
            f"span_end: {self.name}",
            span_name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            duration_ms=duration_ms,
            status=status,
            error=str(exc_val) if exc_val else None,
        )
