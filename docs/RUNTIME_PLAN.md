# AXON Runtime Plan Workflow

AXON currently supports a **non-executing runtime-plan workflow**. This workflow is the bridge between static compiler tooling and future runtime execution, but it deliberately stays inside the current runtime boundary.

A runtime plan answers a safe question:

```text
Given a parsed and validated `.ax` file, what would a future runtime need to know?
```

It does **not** answer:

```text
What happens if this agent actually runs?
```

That distinction is central to AXON's current safety posture.

## Why runtime plans exist

AXON already parses declarations such as `agent`, `tool`, `prompt`, `rag`, and `flow`. Future versions will eventually execute some of those declarations. Runtime plans let us prepare for that future without crossing into live execution too early.

The runtime-plan workflow gives maintainers a stable, testable representation of:

- declared imports
- type aliases
- prompts
- tools
- agents and methods
- RAG blocks
- flow blocks
- capability flags
- disabled execution boundaries

The plan is deterministic and inspection-only. It can be rendered as human output or JSON, snapshotted, reviewed, and checked in CI.

## Commands

### Inspect one source file

```bash
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --json
```

### Write a golden runtime-plan snapshot

```bash
axon runtime-plan examples/hello.ax \
  --write tests/snapshots/runtime_plan/examples/hello.runtime-plan.json \
  --root .
```

### Check a runtime-plan snapshot

```bash
axon runtime-plan examples/hello.ax \
  --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json \
  --root .
```

### Check the full example corpus

```bash
axon runtime-plan-corpus .
axon runtime-plan-corpus . --json
axon runtime-plan-corpus . \
  --examples-dir examples \
  --snapshot-dir tests/snapshots/runtime_plan/examples
```

## What remains enabled

Only one runtime capability is currently enabled:

```text
declaration_inspection
```

That means AXON may inspect validated declarations and summarize their metadata.

## What remains disabled

The following capabilities must remain disabled until a later accepted runtime RFC explicitly enables them:

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

Runtime-plan snapshots and corpus checks verify this boundary repeatedly.

## Relationship to Runtime RFC #001

Runtime plans implement the safe inspection boundary proposed in:

```text
docs/runtime-rfcs/0001-minimal-non-executing-runtime.md
```

That RFC intentionally does not permit live AXON runtime execution. It defines a deterministic plan object that future RFCs can extend carefully.

## Relationship to runtime-plan snapshots

Runtime-plan snapshots live in:

```text
tests/snapshots/runtime_plan/examples/
```

They lock the JSON structure of runtime plans for the example corpus. If a future change modifies runtime-plan output, the snapshot diff makes that change explicit and reviewable.

Snapshot checks protect:

- source path normalization
- declaration summaries
- agent/tool/RAG/flow metadata
- capability flags
- disabled execution capabilities

## Relationship to `check-project`

`axon check-project` remains the broader project quality gate for syntax, validation, AST snapshots, and smoke tests.

`axon runtime-plan-corpus` is the narrower runtime-boundary quality gate. It specifically asks:

```text
Can every example produce a runtime plan, and are all live execution capabilities still disabled?
```

Use both before runtime-adjacent changes:

```bash
axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke
axon runtime-plan-corpus .
```

## Safe handoff workflow

For release or reviewer handoff, collect this evidence:

```bash
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root .
axon runtime-plan-corpus .
axon handoff .
```

This proves the runtime-planning layer is inspectable, snapshotted, corpus-checked, and still non-executing.

## Non-goals

Runtime plans are not an interpreter. They do not:

- execute `fn` method bodies
- interpret `act`, `think`, `observe`, or `store`
- call `@plan`, `@summarize`, `@classify`, or any model-backed operation
- call provider APIs
- run generated FastMCP servers
- dispatch tool bodies
- read or write memory stores
- index documents
- query vector databases
- execute flow DAGs
- replay JSONL traces
- resolve environment secrets

Any task that proposes one of these behaviors must start with `axon runtime-rfc-template` and be reviewed against `docs/RUNTIME_BOUNDARY.md`.

## Runtime plan review checklist

Use the reviewer checklist for any runtime-plan-adjacent change:

```bash
axon runtime-plan-review
axon runtime-plan-review --change "runtime-plan snapshot update"
axon runtime-plan-review --json
axon runtime-plan-review-check .
```

The checklist is documented in `docs/RUNTIME_PLAN_REVIEW.md`. It requires reviewers to verify runtime-plan snapshots, runtime-plan corpus checks, dependency boundaries, hygiene, and Runtime RFC escalation rules before accepting changes.

## Review consistency check

Use `axon runtime-plan-review-check .` when runtime-plan output, runtime-plan snapshots, runtime-plan corpus checks, or runtime-boundary documentation changes. It verifies that the reviewer checklist, runtime-plan documentation, Runtime RFC #001, handoff docs, CLI docs, and corpus validation commands stay aligned.
