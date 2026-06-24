"""Benchmark AXON parser across three implementations:
  1. Pure Python reference parser
  2. Rust parser via WASM (JS bridge)
  3. Rust parser via pyo3 native extension

Usage:
    python tests/benchmark_all.py
"""

import os
import sys
import time
import json
import tempfile
import subprocess

from pathlib import Path

ITERATIONS = 50
WARMUP = 5


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from axon.parser import parse

def timeit(fn, name, iterations=ITERATIONS, warmup=WARMUP):
    for _ in range(warmup):
        fn()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    per_call_ms = (elapsed / iterations) * 1000
    print(f"  {name:30s} {per_call_ms:8.3f} ms/call  ({iterations} iters)")
    return per_call_ms


def parse_with_wasm(source: str) -> dict:
    """Parse via WASM (Node.js bridge)."""
    wasm_dir = os.path.join(os.path.dirname(__file__), '..', 'axon-parser', 'pkg', 'node')
    wasm_dir_js = wasm_dir.replace('\\', '/')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ax', delete=False, encoding='utf-8') as f:
        f.write(source)
        tmp = f.name
    tmp_js = tmp.replace('\\', '/')
    try:
        result = subprocess.run(
            ['node', '-e',
             f"const m = require('{wasm_dir_js}/axon_parser.js'); "
             f"console.log(JSON.stringify(m.parse_axon(require('fs').readFileSync('{tmp_js}', 'utf8'))))"],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(result.stdout.strip())
    finally:
        os.unlink(tmp)


def bench_file(path: Path):
    print(f"\n{'=' * 60}")
    print(f"File: {path.name}  ({path.stat().st_size:,} bytes)")
    print(f"{'=' * 60}")
    src = path.read_text()

    try:
        parse(src)
    except Exception as e:
        print(f"  {'Python parser':30s} PARSE ERROR: {e}")
        return

    py_ms = timeit(lambda: parse(src), "Python parser")

    try:
        parse_with_wasm(src)
    except Exception as e:
        print(f"  {'WASM (Rust)':30s} PARSE ERROR: {e}")
        return
    wasm_ms = timeit(lambda: parse_with_wasm(src), "WASM (Rust)")

    try:
        import axon_parser
        axon_parser.parse_axon(src)
    except ImportError:
        print(f"  {'pyo3 native':30s} not installed")
        return
    except Exception as e:
        print(f"  {'pyo3 native':30s} PARSE ERROR: {e}")
        return
    pyo3_ms = timeit(lambda: axon_parser.parse_axon(src), "pyo3 native")

    print(f"  {'Speedup vs Python':30s} WASM {py_ms/wasm_ms:5.1f}x,  pyo3 {py_ms/pyo3_ms:5.1f}x")
    print(f"  {'Speedup vs WASM':30s} pyo3 {wasm_ms/pyo3_ms:5.1f}x faster than WASM")


def main():
    examples_dir = Path(__file__).parent.parent / "examples"
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    files = sorted(examples_dir.glob("*.ax")) + sorted(fixtures_dir.glob("*.ax"))

    if not files:
        print("No .ax files found in examples/ or tests/fixtures/")
        sys.exit(1)

    print("Benchmark: Python vs Rust (WASM) vs Rust (pyo3 native)")
    print(f"Iterations per file: {ITERATIONS} (warmup {WARMUP})")

    for f in files:
        bench_file(f)

    print(f"\n{'=' * 60}")
    print("Done.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
