"""Stable golden snapshots for AXON syntax and validation errors.

This module is intentionally small and deterministic. It gives the test suite a
single place to convert parser/validator failures into JSON snapshots that can be
checked into the repository. The goal is to protect developer experience: future
parser or validator changes should not accidentally degrade error messages,
locations, codes, snippets, or hints.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal

from axon.parser import parse
from axon.syntax import check_syntax
from axon.validator import validate

ErrorMode = Literal["syntax", "validation"]


@dataclass(frozen=True)
class GoldenSnapshotCheckResult:
    """Result of comparing a current error snapshot with a golden file."""

    matched: bool
    expected_path: Path
    expected: str
    actual: str

    def format(self) -> str:
        if self.matched:
            return f"OK: error snapshot matches {self.expected_path}"
        return (
            f"ERROR: error snapshot differs from {self.expected_path}\n"
            "--- expected ---\n"
            f"{self.expected}\n"
            "--- actual ---\n"
            f"{self.actual}"
        )


def syntax_error_snapshot(source: str, filename: str = "case.ax") -> dict[str, Any]:
    """Return a stable dictionary for one syntax-check result.

    The filename defaults to a synthetic stable value. Tests should avoid using
    absolute temp paths in golden syntax snapshots because those make snapshots
    machine-dependent.
    """

    result = check_syntax(source, filename=filename)
    return {
        "kind": "syntax",
        "ok": result.ok,
        "diagnostics": [diagnostic.to_dict() for diagnostic in result.diagnostics],
    }


def validation_error_snapshot(source: str) -> dict[str, Any]:
    """Return a stable dictionary for validation diagnostics.

    If the source cannot be parsed, this intentionally lets SyntaxError bubble
    up. Validation golden cases should be syntactically valid AXON files that
    fail semantic checks.
    """

    diagnostics = validate(parse(source))
    return {
        "kind": "validation",
        "ok": not any(diagnostic.severity == "error" for diagnostic in diagnostics),
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def error_snapshot(source: str, mode: ErrorMode, filename: str = "case.ax") -> dict[str, Any]:
    """Return a syntax or validation error snapshot for AXON source text."""

    if mode == "syntax":
        return syntax_error_snapshot(source, filename=filename)
    if mode == "validation":
        return validation_error_snapshot(source)
    raise ValueError(f"unsupported error snapshot mode: {mode}")


def snapshot_to_json(snapshot: dict[str, Any]) -> str:
    """Serialize an error snapshot with deterministic formatting."""

    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def source_to_snapshot_json(source: str, mode: ErrorMode, filename: str = "case.ax") -> str:
    """Create deterministic JSON for one source/mode pair."""

    return snapshot_to_json(error_snapshot(source, mode=mode, filename=filename))


def write_error_snapshot_file(
    source: str,
    snapshot_path: str | Path,
    mode: ErrorMode,
    filename: str = "case.ax",
) -> Path:
    """Write a golden error snapshot JSON file and return its path."""

    path = Path(snapshot_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source_to_snapshot_json(source, mode=mode, filename=filename), encoding="utf-8")
    return path


def check_error_snapshot_file(
    source: str,
    snapshot_path: str | Path,
    mode: ErrorMode,
    filename: str = "case.ax",
) -> GoldenSnapshotCheckResult:
    """Compare a current error snapshot against a checked-in golden file."""

    path = Path(snapshot_path)
    expected = path.read_text(encoding="utf-8")
    actual = source_to_snapshot_json(source, mode=mode, filename=filename)
    return GoldenSnapshotCheckResult(
        matched=expected == actual,
        expected_path=path,
        expected=expected,
        actual=actual,
    )
