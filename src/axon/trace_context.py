"""Trace context and correlation ID propagation for AXON runtime.

Provides OpenTelemetry-style trace/span IDs without requiring the OTel SDK.
Uses ``contextvars`` for async-safe and thread-safe propagation.
"""

from __future__ import annotations

import contextvars
import secrets
import time
from dataclasses import dataclass
from typing import Any, Generator
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# TraceContext
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraceContext:
    """Immutable trace context with trace ID, span ID, and optional parent."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None

    @classmethod
    def new(cls, parent: TraceContext | None = None) -> TraceContext:
        """Generate a new trace context.

        If *parent* is provided, the new context inherits the parent's
        trace_id and uses the parent's span_id as its parent_span_id.
        """
        trace_id = parent.trace_id if parent else _gen_trace_id()
        span_id = _gen_span_id()
        parent_span_id = parent.span_id if parent else None
        return cls(trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary suitable for JSON."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _gen_trace_id() -> str:
    """Generate a 128-bit trace ID (32 hex characters)."""
    return secrets.token_hex(16)


def _gen_span_id() -> str:
    """Generate a 64-bit span ID (16 hex characters)."""
    return secrets.token_hex(8)


# ---------------------------------------------------------------------------
# Context propagation via contextvars
# ---------------------------------------------------------------------------

_current_trace: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "axon_current_trace", default=None
)


def get_current_trace() -> TraceContext | None:
    """Return the current trace context, or None if none is active."""
    return _current_trace.get()


def set_current_trace(ctx: TraceContext | None) -> None:
    """Set the current trace context."""
    _current_trace.set(ctx)


@contextmanager
def trace_context(ctx: TraceContext | None) -> Generator[TraceContext | None, None, None]:
    """Context manager that sets the trace context for the duration of the block.

    Example::

        with trace_context(TraceContext.new()) as ctx:
            # All events emitted here will use ctx
            emitter.agent_start(...)
    """
    token = _current_trace.set(ctx)
    try:
        yield ctx
    finally:
        _current_trace.reset(token)


@contextmanager
def child_span() -> Generator[TraceContext, None, None]:
    """Create a child span from the current trace context.

    If no trace context is active, creates a new root context.
    """
    parent = _current_trace.get()
    child = TraceContext.new(parent=parent)
    token = _current_trace.set(child)
    try:
        yield child
    finally:
        _current_trace.reset(token)


# ---------------------------------------------------------------------------
# SpanManager
# ---------------------------------------------------------------------------

class SpanManager:
    """Context manager for creating traced spans.

    Automatically emits span_start and span_end events via the provided
    emitter, and injects trace/span IDs into all events.
    """

    def __init__(self, emitter: Any, span_name: str, attributes: dict[str, Any] | None = None) -> None:
        self.emitter = emitter
        self.span_name = span_name
        self.attributes = attributes or {}
        self._start_time: float = 0.0
        self._ctx: TraceContext | None = None
        self._token: contextvars.Token[TraceContext | None] | None = None

    def __enter__(self) -> TraceContext:
        parent = _current_trace.get()
        self._ctx = TraceContext.new(parent=parent)
        self._token = _current_trace.set(self._ctx)
        self._start_time = time.time()
        self.emitter._append_event(
            "span_start",
            span_name=self.span_name,
            trace_id=self._ctx.trace_id,
            span_id=self._ctx.span_id,
            parent_span_id=self._ctx.parent_span_id,
            **self.attributes,
        )
        return self._ctx

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._ctx is None or self._token is None:
            return
        duration_ms = int((time.time() - self._start_time) * 1000)
        self.emitter._append_event(
            "span_end",
            span_name=self.span_name,
            trace_id=self._ctx.trace_id,
            span_id=self._ctx.span_id,
            duration_ms=duration_ms,
            error=str(exc_val) if exc_val else None,
        )
        _current_trace.reset(self._token)
