# Verified Test Baseline

Date: 2026-10-05  
Status: **repository evidence verified; local execution pending**

This file deliberately separates tested repository claims from tests actually re-executed during reconciliation.

## Repository evidence

AXON current documentation claims:
- 1200+ pytest tests;
- 108 Rust tests;
- Rust/Python IR conformance;
- WASM build/tests;
- native PyO3 build;
- parser benchmarks.

AXON CI definition currently executes:
- Python 3.11 and 3.12;
- compileall;
- dependency boundary audit;
- repository hygiene audit;
- project quality gate;
- formatter check;
- smoke test;
- full pytest.

Rust Parser CI currently executes:
- `cargo test`;
- release build;
- WASM build;
- Python/Rust IR conformance;
- parser snapshots;
- Node WASM tests;
- PyO3 wheel build/import verification;
- benchmarks.

Mesh documentation claims:
- 125 backend tests;
- 80 API smoke checks;
- benchmark/readiness checks.

Mesh CI currently executes on Python 3.10, 3.11 and 3.12:
- backend pytest;
- API smoke test;
- public repository validation.

## Important limitation

The reconciliation chat environment has inspected the repository and CI definitions but has **not executed these repositories locally**. Therefore numeric pass counts are not promoted to a new verified baseline here.

Latest inspected main commits:
- AXON: `e357969312e9b4970aff5f2afb21cb1ac24dc90e`
- Mesh: `4b90bcbf3b537064368c9db05e365bcfdc8c494a`

## Codex/local verification commands

AXON:

```bash
python -m pip install -e ".[dev,serve]"
python -m compileall -q src tests
axon deps .
axon hygiene .
axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots
axon smoke examples/hello.ax
python -m pytest
cd axon-parser
cargo test
cargo build --release
cd ..
python -m pytest tests/test_rust_ir_conformance.py -v
python -m pytest tests/test_parser_snapshots.py -v
```

Mesh:

```bash
cd framework/backend
python -m pip install -e ".[dev]"
python -m pytest -v
cd ../../scripts
python smoke_test_api.py
python validate_public_repo.py
python run_benchmark_suite.py
```

## Baseline acceptance

Before migration work:
- all currently blocking CI checks pass;
- test counts are captured from actual output;
- failures are classified as pre-existing vs migration-caused;
- no API key is required;
- no paid model call occurs.
