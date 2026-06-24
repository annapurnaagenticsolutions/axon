# AXON Runtime Plan Review Consistency Check

`axon runtime-plan-review-check` verifies that the runtime-plan reviewer checklist stays aligned with the runtime-plan docs, runtime-boundary docs, Runtime RFC #001, handoff docs, CLI reference, and runtime-plan corpus validation.

The command is inspection-only. It does not execute agents, call providers, dispatch tools, resolve secrets, mutate memory, index RAG data, execute flows, replay traces, or import FastMCP.

## Command

```bash
axon runtime-plan-review-check .
axon runtime-plan-review-check . --json
axon runtime-plan-review-check . --skip-corpus
axon runtime-plan-review-check . --examples-dir examples --snapshot-dir tests/snapshots/runtime_plan/examples
```

## What it checks

The consistency check verifies that:

- required runtime-plan documentation files exist
- `docs/RUNTIME_PLAN_REVIEW.md` includes the required reviewer commands
- `docs/RUNTIME_PLAN.md`, `docs/RUNTIME_BOUNDARY.md`, and Runtime RFC #001 agree on the current runtime boundary
- `README.md` and `docs/CLI_REFERENCE.md` document `axon runtime-plan-review` and `axon runtime-plan-corpus`
- the generated runtime-plan review checklist mentions `declaration_inspection`
- the generated checklist and runtime docs mention every disabled capability:
  - `method_execution`
  - `provider_calls`
  - `tool_dispatch`
  - `memory_mutation`
  - `rag_indexing`
  - `rag_retrieval`
  - `flow_execution`
  - `trace_replay`
  - `secret_resolution`
  - `fastmcp_runtime_import`
- `axon runtime-plan-corpus .` passes unless `--skip-corpus` is used

## Required release evidence

For runtime-plan-adjacent changes, collect:

```bash
axon runtime-plan-review
axon runtime-plan-review-check .
axon runtime-plan-corpus .
axon deps .
axon hygiene .
```

Use `--json` when machine-readable release evidence is needed.

## Boundary rule

The only enabled runtime capability remains:

```text
declaration_inspection
```

All execution capabilities remain disabled until a future accepted Runtime RFC explicitly changes the boundary.
