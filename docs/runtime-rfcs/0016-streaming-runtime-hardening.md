# RFC #016 — Streaming Runtime Hardening

**Status:** Draft  
**Phase:** 5 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

RFC #010 introduced streaming support in the sync runtime (`RuntimeExecutor` with `stream=True`, `provider.call_stream()`). This sprint hardens that implementation with a `StreamingCollector` for real-time CLI output buffering, integration with `AgentLifecycleManager` so spawned agents can stream, and comprehensive tests covering the streaming path, fallback path, and trace emission.

## Motivation

The streaming infrastructure exists but lacks:
- Real-time output display for lifecycle-managed agents
- Structured streaming event collection for downstream consumers
- Dedicated test coverage for `RuntimeExecutor` streaming, fallback, and trace events

This sprint closes those gaps and satisfies the acceptance criteria in RFC #010.

## Goals

- `StreamingCollector` class that buffers chunks and emits formatted output
- Integration with `AgentLifecycleManager` via optional `stream=True` on `spawn()`
- CLI `axon agent spawn --stream` and `axon run --stream` both verified
- Tests: streaming path, non-streaming fallback, mid-stream error, trace events
- No live network calls in CI (mock provider only)

## Non-Goals

- New AEL syntax for streaming (`@stream`)
- SSE/websocket server endpoints
- Backpressure or flow control
- Async runtime changes (already works independently)

## Design

### StreamingCollector

```python
class StreamingCollector:
    def __init__(self, emitter: TraceEmitter | None = None) -> None: ...
    def collect(self, chunk: str) -> None: ...
    def finish(self, result_type: str = "ok") -> None: ...
    def to_text(self) -> str: ...
    def to_list(self) -> list[str]: ...
```

- Buffers chunks into a list
- Emits trace events for each chunk (via optional `TraceEmitter`)
- Provides `to_text()` for final concatenated output
- Thread-safe for use from background agent threads

### Lifecycle Integration

`AgentLifecycleManager.spawn()` accepts `stream: bool = False`. When enabled:
- Sets `RuntimeConfig.stream = True`
- Wraps `_agent_loop` with a `StreamingCollector`
- Stores collected chunks in `AgentInstance.last_output`

### Trace Events

Already implemented in RFC #010; this sprint adds tests to verify:
- `model_stream_start` emitted before first chunk
- `model_stream_chunk` emitted per chunk
- `model_stream_end` emitted after last chunk or error

## Testing Strategy

- `test_streaming_collector_buffers_chunks` — collector accumulates chunks
- `test_streaming_runtime_emits_trace_events` — trace emitter receives stream events
- `test_streaming_fallback_when_provider_no_stream` — falls back to `provider.call()`
- `test_streaming_mid_stream_error` — error chunk aborts stream
- `test_agent_spawn_with_stream` — lifecycle spawn with streaming

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Thread-safety in StreamingCollector | Use `threading.Lock` |
| Large chunk memory growth | Document 10MB soft cap; future: ring buffer |
