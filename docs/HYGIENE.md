# Repository Hygiene

AXON keeps the compiler core deterministic and the repository clean. The `axon hygiene` command audits `.gitignore` rules and common local-file risks without calling providers, executing agents, or reading secrets.

## Commands

```bash
axon hygiene .
axon hygiene . --json
axon hygiene . --write-gitignore
axon hygiene . --write-gitignore --force
axon repo-hygiene .
```

`axon repo-hygiene` is an alias for `axon hygiene`.

## What the audit checks

The audit expects `.gitignore` to ignore:

- Python caches and bytecode such as `__pycache__/`, `*.py[cod]`, and `.pytest_cache/`.
- Python build outputs such as `build/`, `dist/`, and `*.egg-info/`.
- Virtual environments such as `.venv/`, `venv/`, and `env/`.
- AXON generated outputs such as `*_server.py`, trace JSONL files, and `.axon/cache/`.
- Local secrets such as `.env`, `.env.*`, `*.pem`, and `*.key`.
- OS/editor noise such as `.DS_Store` and `Thumbs.db`.

The audit also protects important source-controlled areas from being ignored accidentally:

- `src/`
- `tests/`
- `examples/`
- `docs/`
- `.github/`
- `.githooks/`
- `tests/snapshots/`
- `tests/golden_errors/`
- `pyproject.toml`, `README.md`, `CHANGELOG.md`, and `axon.toml`

## Why this matters

Generated servers, local traces, caches, and secrets should stay local. AXON source, examples, docs, CI workflows, snapshots, and golden errors should stay reviewable. This command creates a small safety gate before runtime features and provider integrations make repository hygiene more important.
