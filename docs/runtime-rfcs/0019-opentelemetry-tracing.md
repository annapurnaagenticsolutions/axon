# RFC #019 — OpenTelemetry Tracing & Correlation IDs

**Status:** Draft  
**Phase:** 8 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Add correlation IDs (trace ID / span ID) to all AXON runtime trace events so that agent executions, provider calls, tool dispatches, and agent delegations can be linked across the distributed execution graph. This enables end-to-end observability without requiring the OpenTelemetry SDK as a hard dependency.

## Motivation

Current trace events record what happened but not the causal relationship between events:
- Agent A delegates to Agent B — both emit events but there's no link
- A single HTTP API request spawns an agent, which calls a provider, which dispatches a tool — each step is isolated in traces
- Streaming chunks have no parent span linking them to the original model call

## Goals

- `TraceContext` dataclass: `trace_id`, `span_id`, `parent_span_id`
- `contextvars`-based propagation for async-safe context passing
- Every `TraceEmitter` event includes `trace_id` and `span_id`
- `SpanManager` context manager for creating nested spans around operations
- Optional `OTLPSpanExporter` (requires `opentelemetry-*` packages)
- No breaking changes to existing trace event structure

## Non-Goals

- Full OpenTelemetry SDK integration (metrics, baggage, logs)
- Distributed tracing across network boundaries (HTTP headers, gRPC metadata)
- Automatic instrumentation of Python standard library
- Trace sampling decisions

## Design

### TraceContext

```python
@dataclass(frozen=True)
class TraceContext:
    trace_id: str   # 32 hex chars (UUID-like)
    span_id: str    # 16 hex chars
    parent_span_id: str | None = None
```

### Context Propagation

Uses Python `contextvars` for thread-safe and async-safe propagation:

```python
_current_trace: contextvars.ContextVar[TraceContext | None]
```

### SpanManager

```python
with SpanManager(emitter, "model_call") as span:
    # All events emitted here have span.trace_id and span.span_id
    provider.call(...)
    # On exit, emits a span_end event
```

### TraceEmitter Integration

Every event emitted gets these fields injected automatically:
- `trace_id` — the root trace identifier
- `span_id` — the current span identifier
- `parent_span_id` — when inside a nested span

## Testing Strategy

- Unit test: `TraceContext` creation and uniqueness
- Unit test: `SpanManager` creates nested spans correctly
- Unit test: `TraceEmitter` events include trace/span IDs
- Unit test: Correlation IDs propagate across delegate calls
- Unit test: `OTLPSpanExporter` basic conversion

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| contextvars not available in Python <3.7 | AXON already requires >=3.11 |
| Performance overhead of generating IDs | Use `secrets.token_hex` (CSPRNG but fast) |
| Memory growth from storing IDs in every event | IDs are 48 bytes each; negligible |
