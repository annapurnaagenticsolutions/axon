"""Snapshot tests: Rust parser IR output must match recorded snapshots.

Regenerate snapshots:
    python tests/test_parser_snapshots.py --update
"""

import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUST_PARSER = os.path.join(ROOT, "axon-parser", "target", "release", "axon-parser.exe")
SNAPSHOT_DIR = os.path.join(ROOT, "tests", "snapshots")


def _ensure_snapshot_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def _snapshot_path(example_name: str) -> str:
    return os.path.join(SNAPSHOT_DIR, f"{example_name}.json")


def _run_rust_parser(source_path: str) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        out_path = f.name
    try:
        result = subprocess.run(
            [RUST_PARSER, "parse", source_path, "--output", out_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Rust parse failed: {result.stderr}")
        with open(out_path, "r") as f:
            return json.load(f)
    finally:
        os.unlink(out_path)


class ParserSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(RUST_PARSER):
            raise unittest.SkipTest(f"Rust parser not found: {RUST_PARSER}")
        _ensure_snapshot_dir()

    def test_snapshots_match(self):
        examples = sorted(glob.glob(os.path.join(ROOT, "examples", "*.ax")))
        failures = []
        for path in examples:
            name = os.path.splitext(os.path.basename(path))[0]
            snap_path = _snapshot_path(name)

            ir = _run_rust_parser(path)
            actual = json.dumps(ir, indent=2, sort_keys=True)

            if not os.path.exists(snap_path):
                failures.append(f"  {name}: no snapshot (run --update)")
                continue

            with open(snap_path, "r") as f:
                expected = f.read().rstrip("\n")

            if actual != expected:
                failures.append(f"  {name}: IR changed")

        if failures:
            self.fail("Snapshot mismatches:\n" + "\n".join(failures))


def update_snapshots():
    _ensure_snapshot_dir()
    examples = sorted(glob.glob(os.path.join(ROOT, "examples", "*.ax")))
    for path in examples:
        name = os.path.splitext(os.path.basename(path))[0]
        ir = _run_rust_parser(path)
        snap_path = _snapshot_path(name)
        with open(snap_path, "w") as f:
            json.dump(ir, f, indent=2, sort_keys=True)
            f.write("\n")
        print(f"Updated {snap_path}")
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--update":
        sys.argv = sys.argv[:1]  # remove --update so unittest doesn't complain
        update_snapshots()
    else:
        unittest.main()
