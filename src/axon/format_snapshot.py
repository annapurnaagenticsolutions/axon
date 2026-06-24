"""Golden snapshot helpers for canonical AXON formatting.

These helpers compare formatter output against checked-in `.ax` snapshot files.
They are intentionally small and deterministic so formatter changes are explicit
in review, just like AST and error snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from axon.formatter import DEFAULT_ENCODING, format_file


@dataclass(frozen=True)
class FormatSnapshotCheckResult:
    """Result of comparing formatter output with a golden formatted snapshot."""

    matched: bool
    message: str
    expected: str
    actual: str


def source_file_to_formatted_snapshot(path: str | Path) -> str:
    """Return canonical formatted AXON source for a source file."""
    return format_file(path)


def write_format_snapshot_file(source_path: str | Path, snapshot_path: str | Path) -> Path:
    """Write canonical formatted source to a golden snapshot file."""
    destination = Path(snapshot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source_file_to_formatted_snapshot(source_path), encoding=DEFAULT_ENCODING)
    return destination


def check_format_snapshot_file(source_path: str | Path, snapshot_path: str | Path) -> FormatSnapshotCheckResult:
    """Compare current canonical formatting for a source file against a snapshot."""
    snapshot = Path(snapshot_path)
    actual = source_file_to_formatted_snapshot(source_path)
    if not snapshot.exists():
        return FormatSnapshotCheckResult(
            matched=False,
            message=f"Formatted snapshot missing: {snapshot}",
            expected="",
            actual=actual,
        )

    expected = snapshot.read_text(encoding=DEFAULT_ENCODING)
    matched = expected == actual
    return FormatSnapshotCheckResult(
        matched=matched,
        message=(
            f"Formatted snapshot matched: {snapshot}"
            if matched
            else f"Formatted snapshot mismatch: {snapshot}"
        ),
        expected=expected,
        actual=actual,
    )
