# AXON Runtime Governance Evidence

`axon runtime-governance-evidence` creates the release-bundle artifact that records the current runtime governance boundary in a stable, secret-safe form.

It wraps the same inspection-only checks used by `axon runtime-governance` and writes the result as JSON or Markdown for reviewer handoff.

## Commands

```bash
axon runtime-governance-evidence .
axon runtime-governance-evidence . --json
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
```

Use the JSON artifact as the machine-readable release evidence file. Use the Markdown artifact when a reviewer needs a readable checklist in the release bundle.

## Standard release bundle artifacts

For runtime-plan, runtime-boundary, runtime-governance, or Runtime RFC handoffs, include these artifacts when available:

```text
runtime-governance.json
RUNTIME_GOVERNANCE_EVIDENCE.md
RUNTIME_PLAN_REVIEW.md
runtime-plan-corpus.json
dependency-audit.json
hygiene.json
```

The minimum required artifact for runtime-governance handoff is:

```text
runtime-governance.json
```

## Recommended release workflow

```bash
axon runtime-governance .
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
axon handoff . --output HANDOFF_CHECKLIST.md
```

For a full release bundle, also run:

```bash
axon check-project . --snapshot-dir tests/snapshots/examples --require-snapshots
axon precommit run --path . --full
```

## Non-execution boundary

`axon runtime-governance-evidence` is inspection-only. It does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

The current enabled runtime capability remains:

```text
declaration_inspection
```

The following capabilities remain disabled unless a future accepted Runtime RFC changes the boundary:

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

## Handoff integration

`axon handoff .` includes the runtime-governance evidence command in the standard checklist. Reviewers should confirm that `runtime-governance.json` is present for any task that touches runtime planning, runtime snapshots, runtime boundary documentation, runtime governance docs, or Runtime RFCs.

Do not paste API keys or resolved environment secrets into runtime-governance evidence, release notes, issue trackers, or handoff summaries.
