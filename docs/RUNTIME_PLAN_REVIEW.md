# AXON Runtime Plan Reviewer Checklist

This checklist enforces Runtime RFC #001 — Minimal Non-Executing Runtime Plan.

The runtime-plan reviewer checklist is the review gate for any change that touches:

- `src/axon/runtime_plan.py`
- `src/axon/runtime_plan_snapshot.py`
- `src/axon/runtime_plan_corpus.py`
- `docs/RUNTIME_PLAN.md`
- `docs/RUNTIME_BOUNDARY.md`
- `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`
- `tests/snapshots/runtime_plan/`

It is intentionally inspection-only. It does not execute agents, call providers, dispatch tools, resolve secrets, mutate memory, index RAG data, execute flows, replay traces, or import FastMCP.

## Command

```bash
axon runtime-plan-review
axon runtime-plan-review --change "runtime-plan schema update"
axon runtime-plan-review --json
axon runtime-plan-review --output RUNTIME_PLAN_REVIEW.md
axon runtime-plan-review-check .
axon runtime-plan-review-check . --json
```

The command prints a structured checklist that reviewers can paste into pull requests, handoff notes, or release evidence.

## Required evidence

Before accepting a runtime-plan-adjacent change, collect at least:

```bash
python -m compileall -q src tests
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root .
axon runtime-plan-review-check .
axon runtime-plan-corpus .
axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke
axon deps .
axon hygiene .
```

## Boundary rule

The only enabled runtime capability remains:

```text
declaration_inspection
```

These must remain disabled until a later accepted Runtime RFC explicitly enables them:

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

## Escalation rule

Any change that enables method execution, provider calls, tool dispatch, memory mutation, RAG indexing or retrieval, flow execution, trace replay, secret resolution, or FastMCP runtime import must stop and start with a dedicated Runtime RFC.

Use:

```bash
axon runtime-rfc-template --number <N> --title "<Runtime capability proposal>"
```

before implementation begins.

## Consistency check

Use `axon runtime-plan-review-check .` to confirm this checklist remains aligned with `docs/RUNTIME_PLAN.md`, `docs/RUNTIME_BOUNDARY.md`, Runtime RFC #001, `docs/HANDOFF.md`, `README.md`, `docs/CLI_REFERENCE.md`, and runtime-plan corpus snapshots.

```bash
axon runtime-plan-review-check .
axon runtime-plan-review-check . --json
```

See `docs/RUNTIME_PLAN_REVIEW_CONSISTENCY.md`.
