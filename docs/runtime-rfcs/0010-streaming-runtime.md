# AXON Runtime RFC #010 — Streaming Runtime

**Status:** Draft  
**Created:** 2026-06-17  
**Owner:** AXON Maintainers  

> This RFC proposes first-class streaming support for AXON model calls. It enables both async (`axon run --stream`) and sync-runtime (`RuntimeExecutor` with `stream=True`) streaming of provider responses, yielding `Stream<Str>` chunks that can be consumed by AEL `for` loops or collected into a final string.

---

## SUMMARY

Propose a streaming runtime that:

1. Exposes `Stream<Str>` as a first-class AXON type (already parsed by the type checker).
2. Enables sync-runtime model calls to use `provider.call_stream()` when `RuntimeConfig.stream=True`.
3. Keeps the existing async-runtime (`AsyncRuntimeExecutor.execute_stream`) path intact.
4. Emits per-chunk AEL trace events (`model_stream_start`, `model_stream_chunk`, `model_stream_end`) when tracing is enabled.
5. Falls back gracefully to `provider.call()` for providers that do not support streaming.

The intended output is:

```bash
axon run hello.ax --no-mock --provider openai --stream
```

streaming response chunks through the sync runtime path, with each chunk traced.

---

## PROBLEM / MOTIVATION

AXON currently has two disjoint execution paths:

- **Sync runtime** (`RuntimeExecutor`): Calls `provider.call()` and returns a complete string. No streaming.
- **Async runtime** (`AsyncRuntimeExecutor`): Supports `execute_stream()` via `provider.call_stream_async()`, but is isolated from the full sync-runtime feature set (traces, memory, RAG, tool registry, checkpoints).

Users who want streaming must use the async path, which lacks:
- Full AEL expression evaluation
- Sandboxed tool dispatch
- Memory checkpoint/restore
- Trace replay
- RAG integration

This RFC unifies streaming support so that the **sync runtime** can also stream, bringing all sync-runtime features to streaming use cases.

---

## CURRENT BOUNDARY CHECK

This RFC changes the execution boundary from `docs/RUNTIME_BOUNDARY.md`:

- [ ] **This RFC enables sync-runtime streaming of model provider responses** — The primary change
- [x] Do not call real model providers unless `--no-mock` is passed — Existing guard preserved
- [x] Do not dispatch `act` calls to real tools without permission — Existing sandbox preserved
- [x] Do not resolve, print, or snapshot API keys — Existing secret handling preserved
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary — Provider plugins are optional extras
- [x] Define deterministic test doubles before adding live provider behavior — Mock provider already defined
- [x] Document exactly which AXON syntax subset the runtime will execute — Listed below
- [x] State trace emission guarantees before runtime actions are implemented — Listed below

---

## PROPOSED RUNTIME SCOPE

Add streaming support to the sync `RuntimeExecutor`:

1. **RuntimeConfig** gains `stream: bool = False`.
2. **Provider resolution** remains unchanged; the same provider plugin is used.
3. **Model call dispatch** in `_evaluate_body` branches:
   - If `self.config.stream` and `provider.supports_streaming()`:
     - Call `provider.call_stream(prompt, model, max_tokens=1024)`
     - Yield each `Ok(chunk)` as it arrives
     - Emit `model_stream_chunk` trace events per chunk
   - Else:
     - Call `provider.call(prompt, model, max_tokens=1024)` as today
4. **Trace events** for streaming:
   - `model_stream_start(method_name, model_reference, prompt_summary)`
   - `model_stream_chunk(method_name, chunk_summary)`
   - `model_stream_end(method_name, result_type, result_summary)`
5. **Fallback**: If a provider returns `Err` mid-stream, abort and emit `model_stream_end(result_type="error", ...)`.

---

## NON-GOALS

- Do not add new AEL syntax for streaming (e.g., `@stream`). The `@` operator continues to return `Str`; streaming is a runtime configuration.
- Do not implement backpressure or flow control between chunks.
- Do not add SSE parsing utilities in this RFC (OpenAI/Anthropic SDKs handle SSE internally; generic SSE parsing is a future provider-sdk concern).
- Do not change the async runtime path.

---

## AXON SYNTAX EXECUTED

No new syntax. Streaming is controlled by `RuntimeConfig.stream` (set via CLI `--stream`). All existing AEL syntax (`@`, `act`, `think`, `observe`, `for`, `if`, `match`, `try`, `delegate`, `send`/`receive`) works unchanged.

The return type of `@model "prompt"` remains `Str` even when streaming; chunks are concatenated before returning.

---

## PROVIDER PLUGIN IMPACT

No breaking changes. `ProviderPlugin` already defines:

- `call_stream(...)` → `Iterator[Result[str, ProviderError]]`
- `call_stream_async(...)` → `AsyncIterator[Result[str, ProviderError]]`
- `supports_streaming()` → `bool`

All existing providers (`OpenAIProvider`, `AnthropicProvider`, `MockProviderPlugin`) already implement these methods.

---

## TOOL DISPATCH IMPACT

None. Tool dispatch is unchanged.

---

## MEMORY / RAG / FLOW IMPACT

None. Memory, RAG, and flow execution are unchanged.

---

## TRACE AND OBSERVABILITY GUARANTEES

When streaming is enabled and tracing is active:

1. `model_stream_start` is emitted before the first chunk.
2. `model_stream_chunk` is emitted for each chunk received.
3. `model_stream_end` is emitted after the last chunk or on error.
4. No chunks are lost if the provider yields them.
5. Error chunks (`Err`) abort the stream and are captured in `model_stream_end`.

---

## SECURITY AND SECRET HANDLING

No changes. API keys continue to be loaded from environment variables via `ProviderConfig.get_api_key()`. No secrets are logged in trace events (only chunk summaries, truncated to 50 chars).

---

## TESTING STRATEGY

- Unit test: `RuntimeExecutor` with `stream=True` uses `provider.call_stream()`
- Unit test: `RuntimeExecutor` with `stream=True` and `supports_streaming() == False` falls back to `provider.call()`
- Unit test: Trace emitter receives `model_stream_start`, `model_stream_chunk`, `model_stream_end`
- Unit test: Mid-stream error aborts and emits correct trace events
- Mock provider streaming test: `MockProviderPlugin.call_stream()` yields deterministic chunks
- CLI test: `axon run hello.ax --stream` routes correctly
- No live network calls in CI (mock provider only)

---

## ROLLBACK PLAN

If streaming causes instability:

1. Revert `stream` flag default to `False` (already the default).
2. Users can always fall back to `--mock` or omit `--stream`.
3. The async streaming path remains untouched.

---

## ACCEPTANCE CRITERIA

- [ ] `RuntimeConfig` has `stream: bool = False`
- [ ] `RuntimeExecutor.execute()` calls `provider.call_stream()` when `stream=True` and provider supports it
- [ ] Trace events `model_stream_start`, `model_stream_chunk`, `model_stream_end` are emitted
- [ ] CLI `axon run --stream` works with both `--mock` and `--no-mock --provider <name>`
- [ ] Fallback to `provider.call()` when provider does not support streaming
- [ ] All existing tests pass without modification
- [ ] New tests cover streaming path, fallback path, and trace emission

---

## OPEN QUESTIONS

1. Should we eventually add `@stream` AEL syntax so agents can explicitly request streaming within method bodies?
2. Should `Stream<Str>` become a runtime value type that `for` loops can consume, rather than concatenating chunks automatically?
3. Should we add a `--stream-chunk-timeout` CLI flag for slow providers?
