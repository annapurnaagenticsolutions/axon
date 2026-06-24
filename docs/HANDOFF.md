# AXON Release Handoff Checklist

This document defines the safe, repeatable handoff workflow for AXON prototype bundles.
It is meant for release notes, bug reports, task handoffs, and reviewer summaries.

The workflow is intentionally conservative:

- No AXON agent bodies are executed.
- No providers are called.
- No FastMCP runtime dependency is required for the compiler checks.
- No provider API keys are resolved or printed.
- No provider API keys should be pasted into `.ax` files, issue trackers, release notes, or handoff summaries.

## Generate the checklist

```bash
axon handoff .
axon handoff . --json
axon handoff . --output HANDOFF_CHECKLIST.md
axon handoff . --full
```

Use the default mode for fast local handoff checks. Use `--full` for a release bundle where generated-server smoke checks should be included in the project quality gate.

## Recommended handoff sequence

Run the following commands and paste the relevant outputs or summaries into the release handoff notes.

### 1. Version metadata

```bash
axon version
```

Records the AXON version used for the bundle.

### 2. Environment metadata

```bash
axon info --path .
```

Records Python version, platform, module path, discovered config path, and implemented capabilities. This command is safe for bug reports and does not print provider secrets.

### 3. Project inventory

```bash
axon project-info .
axon foundation-audit .
```

Summarizes source files, examples, docs, snapshots, traces, config providers, CI workflow presence, pre-commit hook presence, hygiene status, and dependency-audit status.

### 4. Dependency boundary audit

```bash
axon deps .
```

Confirms the compiler core remains stdlib-only and that runtime integrations stay behind optional extras.

### 5. Repository hygiene audit

```bash
axon hygiene .
```

Confirms generated servers, traces, caches, virtual environments, and local secret files are ignored without hiding source, docs, examples, tests, or snapshots.

### 6. Project quality gate

Fast handoff mode:

```bash
axon check-project . --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke
```

Full release mode:

```bash
axon check-project . --snapshot-dir tests/snapshots/examples --require-snapshots
```

This command checks syntax, static validation, AST snapshots, and optionally generated-server smoke tests.

### 7. Local pre-commit quality gate

Fast handoff mode:

```bash
axon precommit run --path .
```

Full release mode:

```bash
axon precommit run --path . --full
```

This mirrors the local contributor quality gate.

### 8. Release notes / changelog summary

```bash
axon release-notes \
  --change "describe the change" \
  --tests "paste validation evidence"
```

Use explicit change and validation evidence. Do not rely on hidden conversation context.

## Handoff evidence template

```text
AXON handoff summary
Version:
Environment:
Project inventory:
Dependency audit:
Repository hygiene:
Project quality gate:
Pre-commit gate:
Runtime governance evidence:
Release notes:
Known limitations:
Next safe milestone:
```

## Current limitations to mention when relevant

- AXON method bodies are parsed and preserved, not executed.
- Generated FastMCP servers contain implementation stubs.
- The compiler does not call OpenAI, Anthropic, Google, Ollama, or other providers.
- RAG declarations are parsed but indexing/vector retrieval is not implemented yet.
- Flow declarations are parsed but orchestration execution is not implemented yet.
- The formatter is conservative and AST-based; it does not preserve every non-AST comment yet.

## Runtime-boundary review

For release handoff, confirm that compiler-core commands remain non-executing and secret-safe. Use `docs/RUNTIME_BOUNDARY.md` as the checklist before accepting any provider, tool-dispatch, memory, RAG, flow, or replay implementation.

## Runtime RFC handoff

When a bundle includes runtime design work, include the generated `axon runtime-rfc-template` proposal and confirm it links back to `docs/RUNTIME_BOUNDARY.md`. The proposal must remain secret-safe and must identify which provider, tool dispatch, memory, RAG, flow, and trace boundaries are affected.


## Runtime-plan handoff evidence

For runtime-adjacent changes, include runtime-plan evidence in the handoff:

```bash
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root .
axon runtime-plan-corpus .
```

Review `docs/RUNTIME_PLAN.md`, `docs/RUNTIME_BOUNDARY.md`, and `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md` before accepting any task that could enable execution behavior.

## Runtime-plan review handoff evidence

For runtime-plan-adjacent changes, include:

```bash
axon runtime-plan-review
axon runtime-plan-review-check .
axon runtime-plan-corpus .
```

See `docs/RUNTIME_PLAN_REVIEW.md` for the full reviewer checklist.

## Runtime governance evidence

For runtime-plan, runtime-boundary, runtime-governance, or Runtime RFC handoffs, run:

```bash
axon runtime-governance .
axon runtime-governance . --json
axon runtime-governance-evidence . --output runtime-governance.json
axon release-bundle-manifest . --output release-bundle-manifest.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
```

`axon runtime-governance` combines `axon runtime-plan-review`, `axon runtime-plan-review-check .`, `axon runtime-plan-corpus .`, `axon deps .`, and `axon hygiene .` in one inspection-only workflow.

`axon runtime-governance-evidence` turns that workflow into stable JSON or Markdown evidence for release bundles. Include `runtime-governance.json` with any handoff that changes runtime-plan output, runtime-plan snapshots, runtime-boundary docs, runtime governance docs, or Runtime RFCs. See `docs/RUNTIME_GOVERNANCE_EVIDENCE.md` for the artifact workflow.


## Release bundle manifest

Use `axon release-bundle-manifest` as part of every final release handoff. The manifest lists required source files, documentation, examples, snapshots, quality-gate files, and expected generated evidence artifacts.

```bash
axon release-bundle-manifest . --output release-bundle-manifest.json
axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown
```

Include `release-bundle-manifest.json` in the final handoff bundle. Include `RELEASE_BUNDLE_MANIFEST.md` when reviewers need a human-readable inventory.

## Final release bundle command sequence

For a final handoff bundle, generate the standard artifacts in this order:

```bash
axon handoff . --output HANDOFF_CHECKLIST.md
axon release-notes --output RELEASE_NOTES.md --change "describe the change" --tests "paste validation evidence"
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
axon runtime-plan-corpus . --json > runtime-plan-corpus.json
axon deps . --json > dependency-audit.json
axon hygiene . --json > hygiene.json
axon release-bundle-manifest . --output release-bundle-manifest.json
axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown
axon release-artifacts-check . --json > release-artifact-consistency.json
```

The release bundle manifest and release artifact consistency report should be generated after the other evidence files so reviewers can confirm the expected handoff artifacts and their canonical names are present.

## One-command Release Artifact Writer

For final handoff preparation, use `axon release-artifacts` to write the standard artifact set into a chosen directory:

```bash
axon release-artifacts . --output-dir release-artifacts --version 0.1.0 --date 2026-06-01 --change "describe the change" --tests "paste validation evidence"
```

The command writes the checklist, release notes, runtime governance evidence, runtime-plan corpus evidence, dependency audit, hygiene audit, release bundle manifest, release artifact consistency evidence, and `release-artifacts.json`. It is the preferred final handoff directory writer; see `docs/RELEASE_ARTIFACTS.md` for the full artifact list, reviewer flow, and safety boundary. It remains inspection-only and does not execute agents, call providers, dispatch tools, resolve secrets, or import FastMCP.


## Release artifact consistency check

Before final handoff, run:

```bash
axon release-artifacts-check .
```

This confirms `HANDOFF_CHECKLIST.md`, `handoff-checklist.json`, `RELEASE_NOTES.md`, `release-notes.json`, `runtime-governance.json`, `RUNTIME_GOVERNANCE_EVIDENCE.md`, `runtime-plan-corpus.json`, `dependency-audit.json`, `hygiene.json`, `release-bundle-manifest.json`, `RELEASE_BUNDLE_MANIFEST.md`, `release-artifact-consistency.json`, and `release-artifacts.json` remain aligned across source, handoff docs, release bundle docs, and CLI reference.


## Foundation audit evidence

Run `axon foundation-audit .` before final handoff to confirm the Phase 1 compiler/tooling foundation is still aligned. Include the output alongside `release-artifacts/` for reviewer context.
