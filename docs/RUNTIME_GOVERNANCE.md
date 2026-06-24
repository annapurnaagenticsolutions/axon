# AXON Runtime Governance Quality Gate

`axon runtime-governance` is the combined release/governance evidence command for runtime-plan-adjacent changes.

It runs the existing inspection-only checks together:

```bash
axon runtime-plan-review
axon runtime-plan-review-check .
axon runtime-plan-corpus .
axon deps .
axon hygiene .
```

Alias:

```bash
axon runtime-governance-gate .
```

Useful forms:

```bash
axon runtime-governance .
axon runtime-governance . --json
axon runtime-governance . --skip-corpus
axon runtime-governance . --examples-dir examples --snapshot-dir tests/snapshots/runtime_plan/examples
```

## Boundary

This command is non-executing. It does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

It exists to collect release evidence before runtime behavior is implemented or changed.

## Runtime Governance Evidence Files

Task #47 adds a stable evidence artifact command for release bundles:

```bash
axon runtime-governance-evidence .
axon runtime-governance-evidence . --json
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
```

The evidence artifact wraps the same inspection-only governance gate used by `axon runtime-governance`, then records the result as JSON or Markdown for handoff review.

The evidence command remains non-executing. It does not execute agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

See `docs/RUNTIME_GOVERNANCE_EVIDENCE.md` for the release-bundle evidence workflow and handoff integration.
