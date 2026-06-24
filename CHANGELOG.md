# AXON Changelog

This changelog is maintained alongside generated release notes.

## 0.1.0 — Phase 1 compiler/tooling prototype

Current implemented surface includes parser support for AXON declarations, static validation, FastMCP stub generation, syntax diagnostics, AST snapshots, golden error snapshots, project checks, trace preview/log inspection, project initialization, provider config loading, version/info commands, release-note generation, pre-commit hook tooling, and runtime-governance evidence handoff integration.

Use the generator for handoff bundles:

```bash
axon release-notes --change "describe the change" --tests "pytest passed" --output RELEASE_NOTES.md
```

`axon changelog` is an alias for `axon release-notes`.


## Task #54 — Release Artifact Consistency Handoff Integration

- Added `release-artifact-consistency.json` to the standard release artifact set.
- Updated `axon release-artifacts` to write release artifact consistency evidence.
- Integrated `axon release-artifacts-check . --json > release-artifact-consistency.json` into handoff and release bundle workflows.
- Updated docs and tests so release artifact names stay aligned across writer, manifest, handoff, README, and CLI reference.


## Task #49 — Release Bundle Manifest

- Added `axon release-bundle-manifest` to generate a deterministic release handoff artifact inventory.
- Added release bundle documentation and tests.
