# Contributing to AXON

AXON is being developed slowly and deliberately. The project currently prioritizes compiler correctness, deterministic tooling, clear diagnostics, and safe handoff over fast runtime expansion.

## Current contribution principles

1. Keep each change narrow.
2. Preserve compatibility with previous task bundles.
3. Do not execute AXON agent method bodies unless the task explicitly says runtime execution is in scope.
4. Do not call model providers, resolve API keys, or import provider SDKs in compiler-core code.
5. Keep compiler-core dependencies stdlib-only unless a task explicitly changes that boundary.
6. Add tests for every user-facing behavior change.
7. Update documentation when the CLI surface, workflow, or contributor expectations change.
8. State validation evidence honestly. Do not claim a full test-suite pass unless it actually completed.

## Recommended development loop

```bash
python -m compileall -q src tests
python -m axon syntax examples/hello.ax
python -m axon validate examples/hello.ax
python -m axon deps .
python -m axon hygiene .
python -m axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke
python -m pytest
```

Use `axon precommit run` for the local quality gate and `axon handoff .` when preparing a bundle for review.

## Task-ticket workflow

Every implementation task should be self-contained. The person or LLM receiving the task should not need hidden chat history to implement it.

Generate a starter ticket with:

```bash
axon task-template --number 36 --title "Contributor Guide + Task Ticket Template"
axon task-template --number 37 --title "Next Focused Task" --module src/axon/example.py --output axon_task_37.md
```

A strong task ticket includes:

- background and motivation
- exact files/functions/classes to build
- copy-ready interfaces
- AXON syntax patterns in scope
- input/output examples
- rules and constraints
- dependency boundaries
- required tests
- deliverables
- validation commands

## Review checklist

Before marking a task complete, verify:

- the implementation stayed within scope
- parser/validator behavior did not drift accidentally
- docs and CLI help are aligned when user-facing commands changed
- generated outputs still compile
- examples still parse and validate
- secrets are not printed or resolved unexpectedly
- optional runtime dependencies remain optional

## Current runtime boundary

The Phase 1 prototype parses, validates, formats, snapshots, generates FastMCP stubs, inspects traces, and checks project quality. It does not yet execute AXON expressions, dispatch real tools, run provider calls, execute RAG indexing, or run flow orchestration.

## Runtime boundary

Before proposing any execution, provider, memory, RAG, flow, or replay task, read `docs/RUNTIME_BOUNDARY.md`. Current compiler-core work must remain non-executing unless a task explicitly designs and tests the runtime boundary.

## Runtime RFC workflow

Use `axon runtime-rfc-template` before proposing runtime execution behavior. Runtime proposals must reference `docs/RUNTIME_BOUNDARY.md` and must not call model providers, dispatch real tools, mutate memory, execute flows, or resolve secrets until the RFC is accepted and tests are defined.
