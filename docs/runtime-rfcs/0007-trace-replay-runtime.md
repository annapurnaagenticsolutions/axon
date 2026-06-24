# AXON Runtime RFC #007 — Trace Replay Runtime

**Status:** Draft
**Created:** 2026-06-09
**Owner:** axon-dev

> Runtime work must be proposed before implementation. This template is intentionally strict because runtime behavior can call providers, dispatch tools, mutate memory, index RAG data, execute flows, or replay traces.

---

## SUMMARY

Propose a trace replay runtime that reads an AEL trace JSONL file and deterministically replays recorded tool dispatches, model calls, and RAG retrievals. Instead of executing live tools or calling real providers, the runtime uses the trace as a "mock tape": each `act`, `model.complete()`, or `delegate()` call looks up the next matching event in the trace and returns the exact recorded result.

The intended output is a working `axon run hello.ax --replay hello_trace.jsonl` that:
1. Loads `hello_trace.jsonl`
2. Evaluates the agent's `run()` method body
3. Intercepts `act Greet(name: "World")` and returns the recorded `tool_return` result
4. Intercepts `model.complete(...)` and returns the recorded `model_return` result
5. Returns the exact same output as the original run, without any network calls

This RFC enables deterministic regression testing and debugging by making traces executable replay artifacts.

## PROBLEM / MOTIVATION

AXON now has a fully executing runtime (RFCs #004–#006) that dispatches tools, calls providers, indexes RAG, and executes flows. But there is no way to reproduce a previous run exactly. If a user reports a bug with a trace file, we cannot "replay" that trace to reproduce the behavior without re-running the same tools and models.

Trace replay solves this by treating traces as deterministic mock tapes:
- **Regression testing:** Record a trace once, replay it in CI indefinitely
- **Debugging:** Replay a user's trace locally without needing their API keys or data
- **Reproducibility:** Guarantee identical output for identical input + trace

This is the final piece of the Phase 1 runtime: from "execute" (RFC #004) to "compose" (RFC #005) to "retrieve" (RFC #006) to "replay" (RFC #007).

## CURRENT BOUNDARY CHECK

Confirm the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md` and state exactly what this RFC proposes to change.

Required confirmations:

- [x] This RFC explicitly permits trace replay of recorded runtime actions.
- [x] This RFC does not call real model providers — replay returns recorded responses.
- [x] This RFC does not dispatch real tools — replay returns recorded tool results.
- [x] Do not resolve, print, or snapshot API keys.
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.
- [x] Deterministic test doubles (trace replayer) defined.
- [x] Document exactly which AXON syntax subset the runtime will execute — listed below.
- [x] Trace emission guarantees defined below.

## PROPOSED RUNTIME SCOPE

Add a trace replay runtime that:

1. **Trace reader** (`src/axon/trace_replayer.py`)
   - Read JSONL trace file into a sequence of event objects
   - Build an index of replayable events by type and name
   - Support sequential replay (events consumed in order)

2. **Replay interceptors**
   - `tool_dispatch` replay: when `act ToolName(args)` is encountered, find the next `tool_dispatch` event for `ToolName` and return the recorded `tool_return` result
   - `model_call` replay: when `model.complete(...)` is encountered, find the next `model_call` event and return the recorded `model_return` result
   - `rag_retrieve` replay: when `act RagName.retrieve(...)` is encountered, find the next `rag_retrieve_start` event and return the recorded `rag_retrieve_end` result
   - Non-replayable events (think, observe, store) are ignored during replay

3. **Runtime integration**
   - `RuntimeConfig` gains `replay_path: Optional[Path]` field
   - When `replay_path` is set, the runtime wraps the normal dispatch/model functions with replay interceptors
   - If a requested action has no matching recorded event, raise a replay mismatch error

4. **CLI integration**
   - `axon run <source.ax> --replay <trace.jsonl>` replays the trace
   - `--mock` and `--no-mock` are ignored when `--replay` is active
   - Trace replay is mutually exclusive with `--flow` (raise error if both specified)

5. **Trace emission during replay**
   - New trace events are NOT emitted during replay (to avoid trace-in-trace recursion)
   - The replayer itself writes a single `replay_start` and `replay_end` event if a new trace output is requested

## NON-GOALS

- Do not implement unrelated runtime subsystems.
- Do not broaden provider/tool/memory behavior beyond this RFC.

## AXON SYNTAX EXECUTED

This RFC does not add new AXON syntax execution. It changes the *behavior* of existing syntax by intercepting:

```axon
// Tool dispatch (intercepted during replay)
let result = act Greet(name: "World")?

// Model call (intercepted during replay)
let answer = model.complete("Hello")

// RAG retrieval (intercepted during replay)
let chunks = act ProductDocs.retrieve(query: q)?

// Flow stage (intercepted during replay)
stage Retrieve(query: Str) -> List<Chunk>

// All other syntax executes normally (think, observe, store, let, if, etc.)
```

Specifically, replay intercepts:
- `act ToolName(args)` → returns recorded `tool_return` result
- `model.complete(prompt)` → returns recorded `model_return` result
- `act RagName.method(args)` → returns recorded `rag_retrieve_end` result
- `delegate AgentName(args)` → returns recorded `delegate_return` result

## PROVIDER PLUGIN IMPACT

No provider calls during replay. The trace replayer returns recorded provider responses without touching any provider plugin. This means:

- No API keys needed for replay
- No network calls
- No cost tracking needed
- Provider plugin protocol unchanged

## TOOL DISPATCH IMPACT

Tools are NOT dispatched during replay. The trace replayer returns recorded tool results from `tool_return` events. This means:

- No real tool execution
- No side effects from tools
- Error if a tool call in the source has no matching recorded event
- Tool registry is bypassed during replay

## MEMORY / RAG / FLOW IMPACT

- **Trace replay: EXECUTED** — This is the primary change of this RFC.
- **Memory:** Memory stores are NOT mutated during replay. `store` events in the trace are ignored.
- **RAG:** RAG stores are NOT indexed during replay. `rag_retrieve` events return recorded results directly.
- **Flow:** Flow stages are NOT executed during replay. `stage_start`/`stage_end` events in the trace are ignored.

## TRACE AND OBSERVABILITY GUARANTEES

During replay, minimal trace events are emitted:

1. `replay_start` — `trace_file`, `source_file`
2. `agent_start` — (inherited from normal execution, but no sub-events)
3. `method_start` — (inherited)
4. `replay_end` — `result_type`, `result_summary`, `duration_ms`

Intentionally NOT emitted during replay: `tool_dispatch`, `tool_return`, `model_call`, `model_return`, `rag_retrieve_start`, `rag_retrieve_end`, `think`, `observe`, `store`, `flow_start`, `flow_end`, `stage_start`, `stage_end`.

Reason: emitting these would create a trace-of-a-trace, which is confusing and unnecessary. The replay should be "silent" except for the replay envelope events.

## SECURITY AND SECRET HANDLING

No new secret handling introduced. Replay:
- Does not call providers (no API keys needed)
- Does not read environment variables
- Does not make network calls
- Does not execute tools (no tool-side effects)
- Reads only the trace JSONL file (which should already be redacted)

## TESTING STRATEGY

- [x] unit tests for trace replayer (read JSONL, index events, sequential replay)
- [x] unit tests for replay interceptor (tool dispatch, model call, RAG retrieval)
- [x] unit tests for replay mismatch errors (missing event, wrong order)
- [x] end-to-end test: run agent, record trace, replay trace, compare outputs
- [x] CLI integration test (`--replay` flag)
- [x] existing tests remain passing (no regression)
- [x] no accidental network calls in compiler-core tests

## ROLLBACK PLAN

Trace replay is additive:
1. Delete `src/axon/trace_replayer.py` to remove replay
2. Remove `--replay` CLI flag from `src/axon/cli.py`
3. Remove `replay_path` from `RuntimeConfig`
4. Parser, validator, formatter, codegen, and docs workflows unaffected
5. Normal execution without `--replay` continues unchanged

## ACCEPTANCE CRITERIA

- [x] RFC #007 document accepted.
- [x] `axon run` supports `--replay <trace.jsonl>` flag.
- [x] Tool dispatch replay returns exact recorded result.
- [x] Model call replay returns exact recorded result.
- [x] RAG retrieval replay returns exact recorded result.
- [x] Replay mismatch errors are clear and actionable.
- [x] End-to-end test: original run output == replay output.
- [x] All existing tests pass (no regression).
- [x] CLI reference updated with `--replay` option.

## OPEN QUESTIONS

- **Deferred:** Partial replay (replay some events, execute others), trace merging, trace diffing, replay with modified arguments, conditional replay breakpoints.
- **Future RFC #008:** Multi-agent runtime — orchestrate multiple agents with message passing.
