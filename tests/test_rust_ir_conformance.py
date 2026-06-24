"""Conformance test: Rust parser IR output must match Python IR output."""
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

# Root of the axon repo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUST_PARSER = os.path.join(ROOT, "axon-parser", "target", "release", "axon-parser.exe")

# Dynamically discover all .ax examples
EXAMPLES = sorted(
    os.path.relpath(p, ROOT)
    for p in glob.glob(os.path.join(ROOT, "examples", "*.ax"))
)


class RustIRConformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(RUST_PARSER):
            raise unittest.SkipTest(f"Rust parser binary not found: {RUST_PARSER}")

    def _compile_python(self, source_path: str) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "axon.cli", "compile", source_path, "--output", out_path],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": "src"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"Python compile failed: {result.stderr}")
            with open(out_path, "r") as f:
                return json.load(f)
        finally:
            os.unlink(out_path)

    def _compile_rust(self, source_path: str) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            result = subprocess.run(
                [RUST_PARSER, "parse", source_path, "--output", out_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"Rust compile failed: {result.stderr}")
            with open(out_path, "r") as f:
                return json.load(f)
        finally:
            os.unlink(out_path)

    def _normalize_text(self, text: str) -> str:
        """Strip leading whitespace and remove all blank lines."""
        lines = [line.lstrip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line != "")

    def _normalize_ir(self, ir: dict) -> dict:
        """Normalize IR for comparison between Python and Rust parser."""
        import re
        # Collapse type alias values for comparison
        for ta in ir.get("type_aliases", []):
            if "value" in ta:
                ta["value"] = re.sub(r"\s+", " ", ta["value"]).strip()

        # Normalize bodies in tools, agents, rags
        for tool in ir.get("tools", []):
            tool["body"] = self._normalize_text(tool["body"])
        for agent in ir.get("agents", []):
            for method in agent.get("methods", []):
                method["body"] = self._normalize_text(method["body"])
        for rag in ir.get("rags", []):
            for method in rag.get("methods", []):
                method["body"] = self._normalize_text(method["body"])

        # Normalize prompt templates
        for prompt in ir.get("prompts", []):
            prompt["template"] = self._normalize_text(prompt["template"])

        return ir

    def test_example_ir_matches(self):
        for example in EXAMPLES:
            with self.subTest(example=example):
                source_path = os.path.join(ROOT, example)
                if not os.path.exists(source_path):
                    continue
                py_ir = self._compile_python(source_path)
                rs_ir = self._compile_rust(source_path)
                py_ir = self._normalize_ir(py_ir)
                rs_ir = self._normalize_ir(rs_ir)
                self.assertEqual(
                    py_ir, rs_ir,
                    f"IR mismatch for {example}",
                )


if __name__ == "__main__":
    unittest.main()
