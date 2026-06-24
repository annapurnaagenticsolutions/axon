# AXON Runtime RFC #005 — Flow Execution Engine

**Status:** Draft
**Created:** 2026-06-09
**Owner:** axon-dev

> Runtime work must be proposed before implementation. This template is intentionally strict because runtime behavior can call providers, dispatch tools, mutate memory, index RAG data, execute flows, or replay traces.

---

## SUMMARY

Propose a minimal flow execution engine that interprets AXON `flow` declarations with `stage` and arrow syntax, executing them as a deterministic DAG. A flow defines typed pipeline stages and data-flow arrows; the runtime resolves each stage to a tool or agent method, passes outputs between stages by type/name matching, and returns the final result.

The intended output is a working `axon run examples/flow.ax --flow AnswerFlow --arg question="What is AI?"` that:
1. Parses `flow.ax` into `FlowDecl` with `StageDecl`s and arrow body
2. Builds a DAG from arrows (`Retrieve -> Answer`)
3. Executes `Retrieve(question="What is AI?")` → returns `List<Chunk>`
4. Executes `Answer(chunks=retrieve_result, question="What is AI?")` → returns `Str`
5. Returns the final answer string

This RFC also supports parallel branches `[Pro, Con] -> Synthesize`.

## PROBLEM / MOTIVATION

AXON now has a minimal executing runtime (RFC #004) that runs single-agent `fn run()` bodies with mock tool dispatch. But the language also defines `flow` declarations — typed DAGs of pipeline stages that compose agents and tools into larger workflows. Without flow execution, `flow` remains a static declaration with no runtime behavior.

The `examples/flow.ax` and `examples/debate.ax` files in the example corpus declare flows with stages and arrows. These examples should be executable, not just parseable. Flow execution is the natural next step after single-agent execution: it composes existing tools and agents into multi-stage pipelines.

This RFC keeps the scope narrow: linear and parallel-branch pipelines only. No loops, no conditionals inside flows, no dynamic stage discovery.

## CURRENT BOUNDARY CHECK

Confirm the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md` and state exactly what this RFC proposes to change.

Required confirmations:

- [x] This RFC explicitly permits executing AXON flow bodies and stage calls.
- [x] This RFC uses existing mock tool dispatch and agent delegation from RFC #004.
- [x] Do not call real model providers unless `--no-mock` is passed (RFC #003 boundary).
- [x] Do not resolve, print, or snapshot API keys.
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.
- [x] Deterministic test doubles (mock provider, mock tool registry) already defined.
- [x] Document exactly which AXON syntax subset the runtime will execute — listed below.
- [x] Trace emission guarantees defined below.

## PROPOSED RUNTIME SCOPE

Add a minimal flow execution engine that:

1. **Flow DAG builder** (`src/axon/flow_executor.py`)
   - Parse arrow syntax: `A -> B`, `[A, B] -> C`
   - Build a DAG of stages with topological ordering
   - Map flow parameters to stage inputs by name and type
   - Collect parallel branch outputs into lists for the merge stage

2. **Stage resolution**
   - Resolve a stage name to a `ToolDecl` (same source file)
   - Resolve a stage name to an `AgentDecl` + `run()` method
   - Error if no matching tool/agent found

3. **Flow execution**
   - Execute stages in topological order
   - Linear chains: output of stage N → input of stage N+1 (by param name or type)
   - Parallel branches: collect outputs into a list, pass to merge stage
   - Each stage evaluation uses the existing evaluator + tool registry

4. **CLI integration**
   - `axon run <file.ax> --flow <FlowName> --arg key=value`
   - If `--flow` is omitted and no agent has `run()`, auto-select the first flow
   - Otherwise fall back to existing agent `run()` behavior

5. **Trace emission**
   - `flow_start` — flow name, args
   - `stage_start` — stage name, inputs
   - `stage_end` — stage result summary
   - `flow_end` — final result

## NON-GOALS

- Do not implement unrelated runtime subsystems.
- Do not broaden provider/tool/memory behavior beyond this RFC.

## AXON SYNTAX EXECUTED

This RFC executes the following AXON constructs inside flow declarations:

```axon
// Flow declaration (executed)
flow AnswerFlow(question: Str) -> Str {
    stage Retrieve(query: Str) -> List<Chunk>
    stage Answer(chunks: List<Chunk>, question: Str) -> Str
    Retrieve -> Answer
}

// Tool used by a stage (existing RFC #004 behavior)
tool WebSearch(query: Str) -> Result<List<Chunk>, ToolError> {
    act SomeSearchAPI(query: query)?
}

// Agent used by a stage (existing RFC #004 behavior)
agent Researcher {
    model: @mock/gpt
    fn run(question: Str) -> Str { ... }
}
```

Specifically:
- `flow` declarations with `stage` sub-declarations and arrow syntax
- Arrow patterns: `A -> B` (linear), `[A, B] -> C` (parallel merge)
- Stage calls resolved to `tool` bodies or `agent fn run()` bodies
- All existing expression syntax inside tool/agent bodies (from RFC #004)

## PROVIDER PLUGIN IMPACT

No changes to the provider plugin protocol. Flow execution delegates stage calls to tools/agents, which in turn may call providers through the existing `model.complete()` mechanism (RFC #003/#004). The flow executor itself never calls providers directly.

- Mock provider (default, `--mock`) continues to return deterministic responses
- Real providers ( `--no-mock`) are available if the stage's agent uses a real model reference
- No timeout or cost tracking in this RFC — defer to future work

## TOOL DISPATCH IMPACT

Flow execution reuses the existing mock tool registry from RFC #004. Stage names are resolved to `ToolDecl` objects in the same source file; if not found, the runtime falls back to looking up an `AgentDecl` with a matching `run()` method.

- Stage dispatch is identical to `act ToolName(args)` dispatch
- Error if stage name does not match any tool or agent
- Error if stage parameters cannot be satisfied from flow args or previous outputs
- Trace events emitted for each stage dispatch and return

## MEMORY / RAG / FLOW IMPACT

- **Flow DAGs: EXECUTED** — This is the primary change of this RFC.
- **Memory:** No new memory behavior. Individual agents inside stages may mutate memory (existing RFC #004 behavior).
- **RAG:** No RAG indexing or retrieval in this RFC.

## TRACE AND OBSERVABILITY GUARANTEES

The following AEL trace events are emitted during flow execution:

1. `flow_start` — `flow_name`, `args` (redacted)
2. `stage_start` — `stage_name`, `input_keys` (names only, not values)
3. `tool_dispatch` / `model_call` — inherited from stage execution (RFC #004)
4. `tool_return` / `model_return` — inherited from stage execution
5. `stage_end` — `stage_name`, `result_type`, `result_summary`
6. `flow_end` — `result_type`, `result_summary`, `duration_ms`

Ordering: stages are logged in the order they are executed (topological order). Parallel branches may interleave `stage_start`/`stage_end` pairs.

Intentionally not recorded: intermediate data values between stages (only result summaries).

## SECURITY AND SECRET HANDLING

No new secret handling introduced by this RFC. Flow execution delegates all external calls to existing tool/agent execution (RFC #004), which already:
- Uses mock providers by default (no API keys needed)
- Redacts values in trace events via `_redact_value`
- Never snapshots traces with real API responses in tests

## TESTING STRATEGY

- [x] unit tests for flow DAG builder (arrow parsing, topological sort, param mapping)
- [x] unit tests for stage resolution (tool lookup, agent lookup, missing stage)
- [x] unit tests for linear flow execution (single chain)
- [x] unit tests for parallel-branch flow execution ([A, B] -> C)
- [x] trace emission tests (flow_start, stage_start, stage_end, flow_end)
- [x] failure-path tests (missing stage, param mismatch, cyclic arrows)
- [x] CLI integration test (`--flow` flag)
- [x] existing agent `run()` tests remain passing (no regression)
- [x] no accidental network calls in compiler-core tests

## ROLLBACK PLAN

Flow execution is entirely additive:
1. Delete `src/axon/flow_executor.py` to remove flow execution
2. Remove `--flow` CLI flag from `src/axon/cli.py`
3. Parser, validator, formatter, codegen, and docs workflows are unaffected — they already parse and format `flow` declarations statically
4. `axon run` without `--flow` continues to use existing agent `run()` behavior

## ACCEPTANCE CRITERIA

- [x] RFC #005 document accepted.
- [x] `axon run` supports `--flow <FlowName>` flag.
- [x] Linear flows execute end-to-end (`A -> B -> C`).
- [x] Parallel-branch flows execute end-to-end (`[A, B] -> C`).
- [x] Stage outputs correctly map to next-stage inputs by name and type.
- [x] Trace events emitted for flow start, stage start/end, flow end.
- [x] All existing tests pass (no regression).
- [x] `examples/flow.ax` executes with `axon run`.
- [x] `examples/debate.ax` executes with `axon run`.
- [x] CLI reference updated with `--flow` option.

## OPEN QUESTIONS

- **Deferred:** Conditional flows (if/else inside flow body), loops, dynamic stage discovery, stage retry logic, stage timeout.
- **Future RFC #006:** RAG indexing and retrieval runtime — make `examples/rag.ax` executable.
- **Future RFC #007:** Trace replay — replay emitted AEL traces as deterministic actions.
