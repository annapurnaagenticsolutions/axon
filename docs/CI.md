# AXON CI Workflow

AXON includes a conservative GitHub Actions workflow at `.github/workflows/ci.yml`.
The workflow is intended to protect the Phase 1 compiler/tooling foundation without
executing AXON agents, calling model providers, or requiring FastMCP at test time.

## Trigger policy

The workflow runs on:

- pushes to `main`
- pull requests targeting `main`
- manual `workflow_dispatch` runs

## Python matrix

The workflow tests the currently supported prototype interpreters:

- Python 3.11
- Python 3.12

## CI steps

The workflow installs the package with development extras only:

```bash
python -m pip install -e ".[dev]"
```

It intentionally does **not** install the `serve` extra. This keeps the compiler core
independent of FastMCP and verifies that smoke tests continue to work through the fake
FastMCP harness.

The workflow then runs:

```bash
python -m compileall -q src tests
axon deps .
axon hygiene .
axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots
axon format examples/hello.ax > /tmp/axon_hello_formatted.ax
axon format /tmp/axon_hello_formatted.ax --check
axon smoke examples/hello.ax
python -m pytest
```

## Runtime boundary

CI does not:

- call provider APIs
- load API keys
- execute AXON agent method bodies
- run generated MCP servers against real FastMCP
- perform RAG indexing or vector retrieval

This is deliberate. The current quality gate is deterministic and safe for every pull request.
