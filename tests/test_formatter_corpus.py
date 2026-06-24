from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from axon.ast_snapshot import declarations_to_dicts
from axon.formatter import check_format_source, format_file, format_source, write_formatted_file
from axon.parser import parse
from axon.validator import has_errors, validate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"


def _example_paths() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.ax"))


def _semantic_projection(value: Any) -> Any:
    """Return the semantic parts of an AST snapshot for formatter round-trip checks.

    The Phase 1 formatter is intentionally AST-based and canonicalizes raw source
    text. For record-style type aliases, the parser stores both structured fields
    and the original raw record text. Formatting may normalize commas in that raw
    record text, so the structured fields are the semantic contract.
    """
    if isinstance(value, list):
        return [_semantic_projection(item) for item in value]
    if isinstance(value, dict):
        projected = {key: _semantic_projection(item) for key, item in value.items()}
        if projected.get("node") == "TypeAliasDecl" and projected.get("fields"):
            projected.pop("value", None)
        return projected
    return value


def _semantic_ast(source: str) -> list[dict[str, Any]]:
    return _semantic_projection(declarations_to_dicts(parse(source), include_lines=False))


def test_all_examples_are_discovered_for_formatter_corpus():
    examples = _example_paths()
    assert examples, "expected at least one .ax file in examples/"
    assert {"hello.ax", "github_triage.ax", "customer_support.ax", "debate.ax"}.issubset(
        {path.name for path in examples}
    )


def test_every_example_can_be_formatted_and_reparsed():
    for path in _example_paths():
        formatted = format_file(path)
        assert formatted.endswith("\n"), f"{path.name} formatter output must end with one newline"
        reparsed = parse(formatted)
        assert reparsed, f"{path.name} formatted output did not parse into declarations"


def test_formatting_preserves_semantic_ast_for_every_example():
    for path in _example_paths():
        original = path.read_text(encoding="utf-8")
        formatted = format_source(original)
        assert _semantic_ast(formatted) == _semantic_ast(original), (
            f"{path.name} formatting changed the semantic AST"
        )


def test_formatted_example_output_is_idempotent():
    for path in _example_paths():
        once = format_file(path)
        twice = format_source(once)
        assert twice == once, f"{path.name} formatter output is not idempotent"
        assert check_format_source(once).formatted, f"{path.name} formatted output failed --check"


def test_formatted_examples_still_validate_without_errors():
    for path in _example_paths():
        declarations = parse(format_file(path))
        diagnostics = validate(declarations)
        assert not has_errors(diagnostics), (
            f"{path.name} formatted output has validation errors:\n"
            + "\n".join(diagnostic.format() for diagnostic in diagnostics)
        )


def test_format_write_roundtrip_on_copied_example_corpus(tmp_path: Path):
    copied_examples = []
    for path in _example_paths():
        destination = tmp_path / path.name
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        copied_examples.append(destination)

    for path in copied_examples:
        write_formatted_file(path)
        result = check_format_source(path.read_text(encoding="utf-8"))
        assert result.formatted, f"{path.name} was not formatted after --write equivalent"
        assert parse(path.read_text(encoding="utf-8")), f"{path.name} no longer parses after formatting"


def test_cli_format_check_accepts_written_example_copy(tmp_path: Path):
    source = EXAMPLES_DIR / "github_triage.ax"
    destination = tmp_path / source.name
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    write = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(destination), "--write"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr or write.stdout

    check = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(destination), "--check"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr or check.stdout
    assert "already formatted" in check.stdout
