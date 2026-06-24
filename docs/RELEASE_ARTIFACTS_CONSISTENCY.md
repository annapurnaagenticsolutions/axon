# AXON Release Artifact Consistency Checks

`axon release-artifacts-check` verifies that the standard release handoff artifact names stay aligned across the artifact writer, release bundle manifest, handoff checklist, README, and release documentation.

```bash
axon release-artifacts-check .
axon release-artifacts-check . --json
```

`axon release-artifact-consistency` is an alias.

## Standard artifact names

The checker treats this list as the canonical release artifact surface:

- `HANDOFF_CHECKLIST.md`
- `handoff-checklist.json`
- `RELEASE_NOTES.md`
- `release-notes.json`
- `runtime-governance.json`
- `RUNTIME_GOVERNANCE_EVIDENCE.md`
- `runtime-plan-corpus.json`
- `dependency-audit.json`
- `hygiene.json`
- `release-bundle-manifest.json`
- `RELEASE_BUNDLE_MANIFEST.md`
- `release-artifacts.json`

## Surfaces checked

The consistency check reads these project files:

- `src/axon/release_artifacts.py`
- `src/axon/release_bundle_manifest.py`
- `src/axon/handoff.py`
- `docs/RELEASE_ARTIFACTS.md`
- `docs/RELEASE_BUNDLE.md`
- `docs/HANDOFF.md`
- `docs/CLI_REFERENCE.md`
- `README.md`

The goal is to prevent future drift where the artifact writer creates one set of files, the manifest expects another set, and the docs describe a third set.

## Safety boundary

This check is inspection-only. It does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.
