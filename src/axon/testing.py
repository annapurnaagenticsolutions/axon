"""Test block parser and runner for AXON.

Parses `test "name" { assert Agent.run(args) == expected }` blocks from
AXON source files and executes them against mock providers.

Test block syntax:
    test "test name" {
        assert AgentName.run(arg1, arg2) == expected_value
    }

Multiple assert statements are supported. All must pass for the test to pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestResult:
    name: str
    passed: bool
    expected: str = ""
    actual: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "error": self.error,
        }


@dataclass
class TestBlock:
    name: str
    assertions: list[dict[str, str]] = field(default_factory=list)


def parse_test_blocks(source: str) -> list[TestBlock]:
    """Parse test blocks from AXON source text."""
    blocks: list[TestBlock] = []
    pos = 0
    length = len(source)

    while pos < length:
        # Find 'test' keyword at top level (not inside other declarations)
        match = re.search(r'(?<!\w)test\s+"([^"]+)"\s*\{', source[pos:])
        if not match:
            break

        name = match.group(1)
        block_start = pos + match.end()
        # Find matching closing brace
        depth = 1
        i = block_start
        while i < length and depth > 0:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1

        block_body = source[block_start : i - 1]
        assertions = _parse_assertions(block_body)
        blocks.append(TestBlock(name=name, assertions=assertions))
        pos = i

    return blocks


def _parse_assertions(body: str) -> list[dict[str, str]]:
    """Parse assert statements from a test block body."""
    assertions = []
    for match in re.finditer(r'assert\s+(.+?)\s*==\s*(.+?)(?:\n|$)', body):
        assertions.append({
            "expression": match.group(1).strip(),
            "expected": match.group(2).strip(),
        })
    return assertions


def _extract_run_args(expression: str) -> tuple[str | None, dict[str, str]]:
    """Extract agent name and args from 'AgentName.run(arg1, arg2, ...)' expression.

    Returns (agent_name, args_dict) where args_dict maps positional args to
    the agent's run() parameter names (inferred as 'arg0', 'arg1', ... or
    common names like 'q', 'input', 'query').
    """
    match = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\.run\s*\(([^)]*)\)', expression)
    if not match:
        return None, {}
    agent_name = match.group(1)
    args_str = match.group(2).strip()
    if not args_str:
        return agent_name, {}
    # Parse positional arguments (string literals or identifiers)
    raw_args = [a.strip() for a in args_str.split(",")] if args_str else []
    # Map to common param names: try 'input' first, then 'q', then positional
    args_dict = {}
    for i, a in enumerate(raw_args):
        # Strip quotes from string literals
        val = a.strip('"').strip("'")
        if i == 0:
            args_dict["input"] = val
            args_dict["q"] = val
            args_dict["query"] = val
        else:
            args_dict[f"arg{i}"] = val
    return agent_name, args_dict


def run_tests(source: str) -> list[TestResult]:
    """Parse and run test blocks from AXON source.

    Executes each assertion against the mock runtime and compares results.
    """
    from axon.parser import parse
    from axon.validator import validate

    blocks = parse_test_blocks(source)
    results: list[TestResult] = []

    # Parse the source to get declarations (for validation)
    try:
        declarations = parse(source)
        diagnostics = validate(declarations)
        errors = [d for d in diagnostics if d.severity == "error"]
        if errors:
            for block in blocks:
                results.append(TestResult(
                    name=block.name,
                    passed=False,
                    error=f"Validation error: {'; '.join(str(e) for e in errors)}",
                ))
            return results
    except SyntaxError as e:
        for block in blocks:
            results.append(TestResult(
                name=block.name,
                passed=False,
                error=f"Parse error: {e}",
            ))
        return results

    # Try to execute with mock runtime
    try:
        import tempfile
        from pathlib import Path
        from axon.runtime import RuntimeConfig, execute_runtime
    except ImportError:
        # Runtime not available — mark tests as skipped
        for block in blocks:
            results.append(TestResult(
                name=block.name,
                passed=False,
                error="Runtime not available (install with: pip install axon-dsl[serve])",
            ))
        return results

    # Write source to a temp file for the runtime
    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False, encoding="utf-8") as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)

    try:
        for block in blocks:
            all_passed = True
            actual_values = []
            error_msg = ""

            for assertion in block.assertions:
                expr = assertion["expression"]
                expected = assertion["expected"]

                try:
                    agent_name, run_args = _extract_run_args(expr)
                    config = RuntimeConfig(
                        source_path=tmp_path,
                        mock=True,
                        args=run_args,
                        agent_name=agent_name,
                    )
                    result = execute_runtime(config)
                    if hasattr(result, "is_ok") and result.is_ok():
                        actual = str(result.unwrap())
                    elif hasattr(result, "is_err") and result.is_err():
                        actual = f"error: {result.unwrap_err()}"
                    else:
                        actual = str(result)
                    actual_values.append(actual)

                    if not _values_equal(actual, expected):
                        all_passed = False
                        error_msg = f"Expected {expected}, got {actual}"
                        break
                except Exception as e:
                    all_passed = False
                    error_msg = str(e)
                    actual_values.append("")
                    break

            results.append(TestResult(
                name=block.name,
                passed=all_passed,
                expected=block.assertions[0]["expected"] if block.assertions else "",
                actual=actual_values[0] if actual_values else "",
                error=error_msg,
            ))
    finally:
        tmp_path.unlink(missing_ok=True)

    return results


def _values_equal(actual: str, expected: str) -> bool:
    """Compare actual and expected values, handling quotes and whitespace."""
    a = actual.strip().strip('"').strip("'")
    e = expected.strip().strip('"').strip("'")
    return a == e
