"""Stable AST snapshot utilities for AXON source files.

The snapshot format is intentionally simple JSON. It is meant for parser
regression tests, documentation, and CLI inspection. It does not execute AXON
source and it does not validate semantic correctness; it serializes the AST that
``parse()`` produced.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import json
from pathlib import Path
from typing import Any

from axon.parser import parse


DEFAULT_ENCODING = "utf-8"


class SnapshotError(Exception):
    """Raised when an AST snapshot file cannot be read, written, or compared."""


@dataclass(frozen=True)
class SnapshotCheckResult:
    """Result of comparing a current AST snapshot against an expected file."""

    matched: bool
    expected_path: Path
    message: str


def declaration_to_dict(declaration: Any, *, include_lines: bool = True) -> dict[str, Any]:
    """Convert one AST dataclass declaration into a deterministic dictionary.

    Args:
        declaration: A dataclass AST node such as ``ToolDecl`` or ``AgentDecl``.
        include_lines: Whether to preserve source line numbers in the output.

    Returns:
        A JSON-serializable dictionary whose first field is ``node``.
    """
    if not is_dataclass(declaration):
        raise TypeError(f"expected dataclass AST node, got {type(declaration).__name__}")

    result: dict[str, Any] = {"node": type(declaration).__name__}
    for item in fields(declaration):
        if item.name == "line" and not include_lines:
            continue
        result[item.name] = _to_snapshot_value(getattr(declaration, item.name), include_lines=include_lines)
    return result


def declarations_to_dicts(declarations: list[Any], *, include_lines: bool = True) -> list[dict[str, Any]]:
    """Convert parsed AXON declarations into deterministic dictionaries."""
    return [declaration_to_dict(declaration, include_lines=include_lines) for declaration in declarations]


def declarations_to_json(declarations: list[Any], *, include_lines: bool = True) -> str:
    """Serialize parsed AXON declarations as stable pretty-printed JSON."""
    return json.dumps(
        declarations_to_dicts(declarations, include_lines=include_lines),
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def source_to_snapshot_json(source: str, *, include_lines: bool = True) -> str:
    """Parse AXON source text and return its AST snapshot JSON."""
    return declarations_to_json(parse(source), include_lines=include_lines)


def source_file_to_snapshot_json(path: str | Path, *, include_lines: bool = True) -> str:
    """Read an AXON source file and return its AST snapshot JSON."""
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"source file not found: {source_path}")
    if not source_path.is_file():
        raise IsADirectoryError(f"source path is not a file: {source_path}")
    return source_to_snapshot_json(source_path.read_text(encoding=DEFAULT_ENCODING), include_lines=include_lines)


def write_snapshot_file(
    source_path: str | Path,
    snapshot_path: str | Path,
    *,
    include_lines: bool = True,
) -> Path:
    """Write the current AST snapshot for ``source_path`` to ``snapshot_path``."""
    destination = Path(snapshot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        source_file_to_snapshot_json(source_path, include_lines=include_lines),
        encoding=DEFAULT_ENCODING,
    )
    return destination


def check_snapshot_file(
    source_path: str | Path,
    snapshot_path: str | Path,
    *,
    include_lines: bool = True,
) -> SnapshotCheckResult:
    """Compare the current AST snapshot against an existing expected snapshot.

    The comparison is exact. This is deliberate: AST snapshots should change only
    when the parser contract changes intentionally.
    """
    expected = Path(snapshot_path)
    if not expected.exists():
        raise FileNotFoundError(f"snapshot file not found: {expected}")
    if not expected.is_file():
        raise IsADirectoryError(f"snapshot path is not a file: {expected}")

    current_text = source_file_to_snapshot_json(source_path, include_lines=include_lines)
    expected_text = expected.read_text(encoding=DEFAULT_ENCODING)
    if expected_text == current_text:
        return SnapshotCheckResult(True, expected, f"OK: AST snapshot matches {expected}")

    expected_normalized = _normalize_json_text(expected_text)
    current_normalized = _normalize_json_text(current_text)
    if expected_normalized == current_normalized:
        return SnapshotCheckResult(True, expected, f"OK: AST snapshot matches {expected}")

    message = (
        f"AST snapshot mismatch: {expected}\n"
        f"expected {len(expected_text)} chars, current {len(current_text)} chars"
    )
    return SnapshotCheckResult(False, expected, message)


def _to_snapshot_value(value: Any, *, include_lines: bool) -> Any:
    if is_dataclass(value):
        return declaration_to_dict(value, include_lines=include_lines)
    if isinstance(value, list):
        return [_to_snapshot_value(item, include_lines=include_lines) for item in value]
    if isinstance(value, tuple):
        return [_to_snapshot_value(item, include_lines=include_lines) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _to_snapshot_value(value[key], include_lines=include_lines)
            for key in sorted(value, key=lambda item: str(item))
        }
    return value


def _normalize_json_text(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
