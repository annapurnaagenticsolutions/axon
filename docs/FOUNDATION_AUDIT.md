# AXON Foundation Audit

`axon foundation-audit` is the Phase 1 foundation checkpoint. It inspects whether the parser, validator, formatter, snapshots, runtime-plan governance, release handoff, docs, examples, tests, dependency audit, and repository hygiene surfaces are present and aligned.

The command is intentionally inspection-only. It does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

## Why this exists

After many small implementation milestones, AXON needs a stable checkpoint before moving toward runtime design. The foundation audit helps answer:

- Do the core compiler modules exist?
- Do docs and CLI references describe the implemented surface?
- Do examples and snapshots exist for the current language subset?
- Is the runtime boundary still clear?
- Are release and handoff workflows discoverable?

## Usage

```bash
axon foundation-audit .
axon foundation-audit . --json
```

## What it checks

The audit covers these Phase 1 foundation areas:

- parser and AST foundation
- validation and syntax diagnostics
- code generation and smoke harness
- configuration and secret-safety boundaries
- formatting and snapshot stability
- trace tooling
- runtime-plan boundary
- runtime governance
- release handoff
- developer workflow

## Runtime boundary

The only enabled runtime capability at this stage is:

```text
declaration_inspection
```

The following capabilities remain disabled:

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

## Standard release use

Use this command during consolidation and handoff:

```bash
axon foundation-audit .
axon deps .
axon hygiene .
axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke
axon runtime-governance .
axon release-artifacts . --output-dir release-artifacts --change "describe the change" --tests "paste validation evidence"
```

The foundation audit is not a replacement for tests. It is a high-level checkpoint that complements pytest, corpus checks, runtime-governance checks, dependency audit, hygiene audit, and release artifact generation.
