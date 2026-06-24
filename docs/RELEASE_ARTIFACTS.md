# AXON Release Artifacts

`axon release-artifacts` is the standard one-command workflow for preparing a reviewable AXON handoff directory.

It wraps the existing inspection-only handoff tools and writes their outputs into one chosen directory. The command is intended for release preparation, task handoff, milestone review, and attaching evidence to issue trackers or pull requests.

## Command

```bash
axon release-artifacts . --output-dir release-artifacts
axon release-artifacts . --output-dir release-artifacts --version 0.1.0 --date 2026-06-01 --change "completed Task #51" --tests "targeted tests passed"
axon release-artifacts . --output-dir release-artifacts --skip-corpus
axon release-artifacts . --output-dir release-artifacts --json
```

Use `--skip-corpus` only for fast local drafts. For a final release bundle, run without `--skip-corpus` so runtime-plan corpus evidence is generated normally.

## Files written

The output directory contains:

| File | Purpose |
|---|---|
| `HANDOFF_CHECKLIST.md` | Human-readable handoff checklist. |
| `handoff-checklist.json` | Machine-readable handoff checklist. |
| `RELEASE_NOTES.md` | Human-readable release notes with change and validation bullets. |
| `release-notes.json` | Machine-readable release notes. |
| `runtime-governance.json` | Runtime governance evidence. |
| `RUNTIME_GOVERNANCE_EVIDENCE.md` | Reviewer-facing runtime governance evidence. |
| `runtime-plan-corpus.json` | Runtime-plan corpus evidence. |
| `dependency-audit.json` | Dependency boundary evidence. |
| `hygiene.json` | Repository hygiene evidence. |
| `release-bundle-manifest.json` | Machine-readable release bundle manifest. |
| `RELEASE_BUNDLE_MANIFEST.md` | Reviewer-facing release bundle manifest. |
| `release-artifact-consistency.json` | Release artifact name consistency evidence. |
| `release-artifacts.json` | Self-report from the artifact writer. |

## Recommended final handoff flow

```bash
axon release-artifacts . --output-dir release-artifacts --version 0.1.0 --date 2026-06-01 --change "describe the completed milestone" --tests "paste validation evidence"
```

Then attach or archive the entire `release-artifacts/` directory.

For a deeper manual review, use the individual commands listed in `docs/HANDOFF.md` and `docs/RELEASE_BUNDLE.md`.

## Safety boundary

`axon release-artifacts` is inspection-only. It does **not** execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

The command may read local project files such as `.ax` examples, docs, snapshots, `axon.toml`, `pyproject.toml`, and `.gitignore`. It must not print API keys or resolve `${ENV_VAR}` provider secrets.

## Relationship to other release commands

`axon release-artifacts` combines the output of these safe workflows, including the artifact-name consistency evidence produced by `axon release-artifacts-check`:

```bash
axon handoff . --output HANDOFF_CHECKLIST.md
axon release-notes --path . --change "..." --tests "..." --output RELEASE_NOTES.md
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
axon runtime-plan-corpus . --json > runtime-plan-corpus.json
axon deps . --json > dependency-audit.json
axon hygiene . --json > hygiene.json
axon release-bundle-manifest . --output release-bundle-manifest.json
axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown
axon release-artifacts-check . --json > release-artifact-consistency.json
```

Use the one-command writer for normal handoff preparation. Use the individual commands when diagnosing a failure or reviewing a specific subsystem.
