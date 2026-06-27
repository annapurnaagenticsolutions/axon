#!/usr/bin/env python3
"""Benchmark: Python parser vs Rust parser (via WASM in Node.js).

Note: We benchmark the Rust parser through its WASM build because:
1. The WASM binary IS the Rust parser compiled to WebAssembly
2. Running via Node.js avoids Windows subprocess overhead that would
   otherwise dominate the CLI benchmark and make results misleading.
"""

import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PKG_DIR = Path(__file__).parent.parent / "axon-parser" / "pkg" / "node"
ITERATIONS = 50
WARMUP = 5


def timeit(fn, name, iterations=ITERATIONS, warmup=WARMUP):
    """Time a callable over N iterations, with warmup."""
    for _ in range(warmup):
        fn()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    per_call_ms = (elapsed / iterations) * 1000
    print(f"  {name:30s} {per_call_ms:8.3f} ms/call  ({iterations} iters)")
    return per_call_ms


def bench_file(path: Path):
    print(f"\n{'=' * 60}")
    print(f"File: {path.name}  ({path.stat().st_size:,} bytes)")
    print(f"{'=' * 60}")
    src = path.read_text()

    # Python parser ----------------------------------------------------------
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from axon.parser import parse

    # Verify Python parser can handle this file
    try:
        parse(src)
    except Exception as e:
        print(f"  {'Python parser':30s} PARSE ERROR: {e}")
        return

    def python_parse():
        parse(src)

    py_ms = timeit(python_parse, "Python parser", iterations=ITERATIONS)

    # WASM (Node.js) — this IS the Rust parser ------------------------------
    if not PKG_DIR.exists():
        print(f"  {'WASM (Rust → Node.js)':30s} NOT FOUND")
        return

    # Write source to temp file to avoid command-line length limits on Windows
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ax', delete=False) as tf:
        tf.write(src)
        tmp_path = tf.name

    # Verify WASM parser can handle this file
    pkg_path = PKG_DIR.as_posix().replace("'", "\\'")
    src_path = tmp_path.replace("\\", "/")
    verify_script = f"""
const {{ parse_axon }} = require('{pkg_path}/axon_parser.js');
const fs = require('fs');
const src = fs.readFileSync('{src_path}', 'utf8');
try {{ parse_axon(src); console.log('OK'); }}
catch(e) {{ console.log('ERR: ' + e); }}
"""
    v = subprocess.run(["node", "-e", verify_script], capture_output=True, text=True)
    if v.returncode != 0 or not v.stdout.strip().startswith("OK"):
        print(f"  {'WASM (Rust → Node.js)':30s} PARSE ERROR: {v.stdout.strip() or v.stderr.strip()}")
        import os; os.unlink(tmp_path)
        return

    bench_script = f"""
const {{ parse_axon }} = require('{pkg_path}/axon_parser.js');
const fs = require('fs');
const src = fs.readFileSync('{src_path}', 'utf8');
const start = process.hrtime.bigint();
for (let i = 0; i < {ITERATIONS}; i++) {{
    parse_axon(src);
}}
const end = process.hrtime.bigint();
const ms = Number(end - start) / 1e6 / {ITERATIONS};
console.log(ms.toFixed(6));
"""
    result = subprocess.run(["node", "-e", bench_script], capture_output=True, text=True)
    import os; os.unlink(tmp_path)
    if result.returncode != 0:
        print(f"  {'WASM (Rust → Node.js)':30s} BENCH ERROR: {result.stderr.strip()}")
        return

    wasm_ms = float(result.stdout.strip())
    print(f"  {'WASM (Rust → Node.js)':30s} {wasm_ms:8.3f} ms/call  ({ITERATIONS} iters)")

    # Speedup ---------------------------------------------------------------
    speedup = py_ms / wasm_ms
    print(f"  {'Rust speedup vs Python':30s} {speedup:8.1f}x")
    throughput_py = 1000 / py_ms
    throughput_wasm = 1000 / wasm_ms
    print(f"  {'Python throughput':30s} {throughput_py:8.1f} parses/sec")
    print(f"  {'Rust throughput':30s} {throughput_wasm:8.1f} parses/sec")


# ---------------------------------------------------------------------------
# Benchmark harness
# ---------------------------------------------------------------------------
def main():
    examples_dir = Path(__file__).parent.parent / "examples"
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    files = sorted(examples_dir.glob("*.ax")) + sorted(fixtures_dir.glob("*.ax"))

    if not files:
        print("No .ax files found in examples/")
        sys.exit(1)

    print(f"Benchmark: Python parser vs Rust parser (WASM -> Node.js)")
    print(f"Iterations per file: {ITERATIONS} (warmup {WARMUP})")
    print(f"Note: WASM IS the Rust parser compiled to WebAssembly.")

    for f in files:
        bench_file(f)

    print(f"\n{'=' * 60}")
    print("Done.")


if __name__ == "__main__":
    main()
