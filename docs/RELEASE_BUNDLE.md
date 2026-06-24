# AXON Release Bundle Manifest

`axon release-bundle-manifest` creates a deterministic, inspection-only inventory for release handoff bundles.

```bash
axon release-bundle-manifest .
axon release-bundle-manifest . --json
axon release-bundle-manifest . --output release-bundle-manifest.json
axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown
axon release-artifacts-check . --json > release-artifact-consistency.json
```

The manifest lists:

- core project files such as `README.md`, `CHANGELOG.md`, `pyproject.toml`, `axon.toml`, and `.gitignore`
- documentation under `docs/`
- AXON examples under `examples/`
- AST snapshots, formatter snapshots, runtime-plan snapshots, and golden error snapshots
- CI and pre-commit quality-gate files
- expected generated handoff artifacts such as `HANDOFF_CHECKLIST.md`, `handoff-checklist.json`, `RELEASE_NOTES.md`, `release-notes.json`, `runtime-governance.json`, `RUNTIME_GOVERNANCE_EVIDENCE.md`, `runtime-plan-corpus.json`, `dependency-audit.json`, `hygiene.json`, `release-bundle-manifest.json`, `RELEASE_BUNDLE_MANIFEST.md`, `release-artifact-consistency.json`, and `release-artifacts.json`

This command is safe for release handoff: it does not execute AXON agents, call providers, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.


## Standard release handoff integration

`axon release-bundle-manifest` is part of the standard final handoff workflow. Generate it after the main evidence artifacts so the manifest can show which expected files are present:

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

`release-bundle-manifest.json` is the machine-readable artifact. `RELEASE_BUNDLE_MANIFEST.md` is optional but useful for reviewer-facing handoffs. The `axon handoff` checklist now includes both commands so maintainers do not forget the bundle inventory step.

## One-command Artifact Directory

`axon release-artifacts` writes the standard release handoff artifacts into a single output directory:

```bash
axon release-artifacts . --output-dir release-artifacts
```

This is useful when preparing a downloadable or attachable release bundle. The command still uses the same safe inspection-only boundaries as the individual handoff commands. See `docs/RELEASE_ARTIFACTS.md` for the canonical artifact list and final handoff workflow.


## Artifact name consistency

Use this check before final handoff to ensure the artifact writer, manifest, handoff checklist, README, and release docs agree on standard artifact names:

```bash
axon release-artifacts-check .
```

The standard artifact names are `HANDOFF_CHECKLIST.md`, `handoff-checklist.json`, `RELEASE_NOTES.md`, `release-notes.json`, `runtime-governance.json`, `RUNTIME_GOVERNANCE_EVIDENCE.md`, `runtime-plan-corpus.json`, `dependency-audit.json`, `hygiene.json`, `release-bundle-manifest.json`, `RELEASE_BUNDLE_MANIFEST.md`, `release-artifact-consistency.json`, and `release-artifacts.json`.
