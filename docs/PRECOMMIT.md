# AXON Pre-commit Hook

AXON includes a conservative Git pre-commit hook template for local developer quality checks.

The hook delegates to:

```bash
python -m axon precommit run --path <project-root>
```

The default run is dependency-light and does not install or require FastMCP, provider SDKs, or API keys.

## Install

From the repository root:

```bash
axon precommit install
```

If a hook already exists, AXON preserves it by default. Overwrite only when intentional:

```bash
axon precommit install --force
```

## Check installation

```bash
axon precommit check
axon precommit check --json
```

## Print the hook template

```bash
axon precommit print
```

## Run checks manually

```bash
axon precommit run
axon precommit run --json
axon precommit run --full
```

The default local checks cover:

```text
compileall for src/ and tests/
dependency audit
repository hygiene audit
project syntax and validation through check-project
AST snapshot presence and matching for examples
formatter idempotency smoke check
pytest
```

`--full` keeps smoke tests enabled inside `axon check-project`. The default run uses `--no-smoke` to keep local commits fast and independent of optional serving dependencies.

## Python executable

The installed shell hook uses `python` by default. Set `AXON_PYTHON` when a repository needs a specific interpreter:

```bash
AXON_PYTHON=.venv/bin/python git commit
```

## Runtime boundary

The hook does not execute AXON agent method bodies, call provider APIs, resolve secrets, or require generated FastMCP servers to run.
