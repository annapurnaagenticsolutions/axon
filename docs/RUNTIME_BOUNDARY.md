# AXON Runtime Boundary

Aligned with Runtime RFC #001 — Minimal Non-Executing Runtime Plan, and Runtime RFC #004 — Minimal Executing Agent Runtime.

AXON is a compiler/tooling prototype with a scoped executing runtime. This document defines the boundary between static compiler tooling, the non-executing runtime-plan workflow, and the deliberately scoped executing runtime available through `axon run`.

The goal is to prevent accidental runtime behavior from entering parser, validator, formatter, documentation, or generated-code milestones before the execution model is deliberately designed and reviewed.

## Current execution posture

### Non-executing compiler and inspection tooling

The AXON parser, validator, formatter, codegen, smoke harness, runtime-plan workflow, and project-quality gates remain intentionally non-executing.

They may:

- parse `.ax` source files into AST dataclasses
- validate declaration-level semantics
- generate FastMCP Python server stubs
- compile generated Python source for structural checks
- load generated Python with a fake FastMCP module during smoke tests
- inspect `axon.toml` with secrets redacted
- preview AEL-looking trace events by statically scanning method bodies
- read existing JSONL trace logs
- format source using the parsed AST
- produce project, handoff, release, hygiene, dependency, and info reports
- **type check expressions using the expression AST (static analysis only)**

They must not:

- dispatch `act` calls to real tools
- call model providers
- resolve or print API keys
- run RAG indexing, embedding, reranking, or vector search
- execute flow DAGs, channels, async fan-out, or worker pools
- replay traces as actions
- import provider SDKs in compiler-core modules
- require FastMCP for compiler tests or static tooling

### Executing runtime (`axon run`)

Runtime RFC #004 introduced a scoped executing runtime behind the `axon run` CLI command. It is intentionally separate from the compiler core and runtime-plan workflow.

It may:

- execute AXON agent `run()` method bodies with mock tool dispatch
- evaluate AXON expressions (literals, variables, string interpolation, let bindings, arithmetic, Ok/Error)
- dispatch `act` calls to the mock tool registry (tools defined in the same source file only)
- emit AEL trace events during execution
- load and checkpoint agent memory via `--memory` and `--checkpoint`

It must not:

- call real model providers (mock provider only)
- dispatch tools to external systems
- resolve or print API keys
- run RAG indexing, embedding, reranking, or vector search
- execute flow DAGs
- replay traces as actions
- import provider SDKs in compiler-core modules
- require FastMCP for the executing runtime

## Boundary by subsystem

### Parser

The parser converts source text into AST objects. It preserves method, tool, RAG, and flow bodies as raw text where appropriate.

Allowed:

- brace-aware parsing
- source line tracking
- raw body preservation
- syntax errors with helpful diagnostics

Forbidden:

- evaluating expressions
- normalizing provider references by calling external services
- inferring runtime behavior from method bodies

### Validator

The validator checks obvious semantic issues that can be determined from declarations.

Allowed:

- duplicate declaration checks
- unknown tool references
- missing tool docstrings
- invalid prompt budget annotations
- simple prompt-template variable checks
- simple flow-stage reference warnings

Forbidden:

- executing prompts
- estimating model quality
- making provider calls
- running retrieved documents through embeddings or rerankers

### Code generator

The FastMCP generator emits safe Python stubs.

Allowed:

- generate `@mcp.tool()` wrappers
- preserve AXON body text as comments
- emit metadata constants
- raise `NotImplementedError` in generated tool bodies

Forbidden:

- translating AXON expressions into executable Python
- embedding API keys
- importing provider SDKs
- implementing HTTP/tool behavior automatically

### Smoke harness

The smoke harness verifies generated servers structurally.

Allowed:

- compile generated Python
- import generated Python with a fake FastMCP module
- verify registered tool names and metadata constants
- verify `mcp.run()` is not called during import

Forbidden:

- starting a real MCP server
- requiring FastMCP installation
- invoking generated tool functions beyond safe registration inspection
- calling provider SDKs or external APIs

### Trace model and trace preview

The trace modules represent and inspect AEL events.

Allowed:

- create trace event dataclasses
- serialize and deserialize JSONL
- filter and summarize trace logs
- statically preview `think`, `act`, `observe`, and `store` statements from method text

Forbidden:

- replaying trace events as real actions
- dispatching `act` events to tools
- treating trace preview as proof of runtime correctness

### Config and secrets

`axon.toml` is configuration only. `.ax` files must not contain API keys.

Allowed:

- load provider names and defaults
- preserve `${ENV_VAR}` placeholders
- optionally resolve placeholders only when explicitly requested
- redact secret-looking values in output

Forbidden:

- printing API keys
- storing resolved secrets in generated source
- requiring cloud provider credentials for compiler-core commands

## Future runtime responsibilities

A future AXON runtime may eventually execute agent methods, dispatch tools, call model providers, operate memory, index RAG sources, execute flows, and produce live AEL traces.

Before that work starts, the runtime design should explicitly define:

1. provider plugin protocol
2. tool dispatch interface
3. runtime representation of `Result<T, E>` and `Option<T>`
4. memory backend contracts for ShortTerm, Semantic, and Episodic memory
5. trace emission guarantees
6. sandboxing and permissions model
7. secret loading and redaction rules
8. retry, timeout, and cancellation behavior
9. deterministic replay boundaries
10. generated code versus interpreter responsibilities

## Runtime milestone gate

No runtime execution task should be accepted unless it states:

- which AXON syntax it executes
- which capabilities remain static only
- whether external network access is possible
- whether secrets are required
- how provider calls are mocked in tests
- how traces are emitted
- how failures surface as `Result<T, E>` or diagnostics
- which tests prove no accidental provider calls occur

## Safe current mental model

For now, AXON is best understood as:

```text
.ax source
  -> parser
  -> validator
  -> AST snapshots / formatter / diagnostics
  -> generated FastMCP stubs
  -> smoke tests with fake FastMCP
  -> trace preview and trace-log inspection
  -> executing runtime (axon run) with mock tools and trace emission
```

Not yet:

```text
.ax source
  -> provider calls
  -> real tool dispatch
  -> memory mutation (runtime memory ops via store/recall)
  -> RAG indexing
  -> flow orchestration
```

This boundary protects AXON's language foundation while allowing the runtime to be designed slowly and precisely.

## Runtime RFC gate

Before implementing any runtime behavior that executes AXON method bodies, calls providers, dispatches tools, mutates memory, runs RAG indexing, executes flows, or replays traces, create a proposal using `axon runtime-rfc-template`. See `docs/RUNTIME_RFC_TEMPLATE.md` for the required sections.


## Runtime RFC #001 draft

The first runtime RFC draft is `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`. It does not permit live execution. It proposes only a future non-executing runtime-plan boundary for inspecting validated declarations and explicitly reporting disabled runtime capabilities.

Task #40 implements that boundary as `axon runtime-plan` and `src/axon/runtime_plan.py`. Task #41 adds runtime-plan golden snapshots via `src/axon/runtime_plan_snapshot.py` and `axon runtime-plan --write/--check`. The command parses and validates one `.ax` file, summarizes declarations, and reports disabled runtime capabilities. It remains non-executing: no method bodies run, no providers are called, no tools are dispatched, no memory is mutated, no RAG data is indexed or retrieved, no flows are executed, no traces are replayed, no secrets are resolved, and FastMCP is not imported by compiler core.


## Runtime-plan workflow

Runtime plans are documented in `docs/RUNTIME_PLAN.md`. They are the current approved non-executing bridge between static compiler tooling and future runtime work.

The runtime-plan workflow includes:

- `axon runtime-plan <source.ax>` for one source file
- `axon runtime-plan <source.ax> --write/--check` for golden snapshots
- `axon runtime-plan-corpus .` for corpus-level runtime-boundary checks

Runtime plans may inspect declarations and report capability flags. They must keep method execution, provider calls, tool dispatch, memory mutation, RAG indexing/retrieval, flow execution, trace replay, secret resolution, and FastMCP runtime import disabled until a later accepted runtime RFC changes that boundary.

## Runtime Capability Boundary

The only enabled runtime capability is:

```text
declaration_inspection
```

The following execution capabilities remain disabled by Runtime RFC #001:

```text
method_execution
provider_calls
tool_dispatch
memory_mutation
rag_indexing
rag_retrieval
flow_execution
trace_replay
secret_resolution
fastmcp_runtime_import
```

## Runtime RFC #004 — Minimal Executing Agent Runtime (Accepted)

`docs/runtime-rfcs/0004-minimal-executing-agent-runtime.md` defines the first end-to-end executing runtime. It is implemented and available through `axon run`.

**What RFC #004 enables:**

```text
method_execution    (mock only, no real providers)
tool_dispatch       (mock tool registry only, no external calls)
trace_replay        (AEL trace emission for execution events)
```

**What RFC #004 explicitly keeps disabled:**

```text
provider_calls      (real LLM APIs — still requires RFC #003 integration)
memory_mutation     (store/recall memory operations at runtime)
rag_indexing
rag_retrieval
flow_execution
secret_resolution
fastmcp_runtime_import
```

This RFC maintains the safety boundary by keeping all external calls mocked and deterministic. No network access, no API keys, no provider SDKs in compiler core.
