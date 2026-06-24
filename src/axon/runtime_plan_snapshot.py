"""Golden snapshot helpers for non-executing AXON runtime plans.

Runtime-plan snapshots lock the inspection-only runtime boundary introduced by
Runtime RFC #001. They serialize the same safe data returned by
``axon runtime-plan --json`` while normalizing the source path so snapshots are
portable across machines and CI workspaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from axon.runtime_plan import DEFAULT_ENCODING, build_runtime_plan_from_source, runtime_plan_to_json


@dataclass(frozen=True)
class RuntimePlanSnapshotCheckResult:
    """Result of comparing current runtime-plan JSON with a golden snapshot."""

    matched: bool
    message: str
    expected: str
    actual: str
    expected_path: Path


def source_file_to_runtime_plan_snapshot_json(
    source_path: str | Path,
    *,
    root: str | Path | None = None,
) -> str:
    """Return stable JSON for the non-executing runtime plan of one source file.

    Args:
        source_path: AXON source file to parse, validate, and summarize.
        root: Optional project root used to normalize ``source_path`` in the
            snapshot. When omitted, only the file name is used. Passing a root is
            recommended for corpus snapshots, e.g. ``examples/hello.ax``.

    Returns:
        Pretty-printed JSON with sorted keys and a trailing newline.
    """
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"source file not found: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"source path is not a file: {path}")

    source = path.read_text(encoding=DEFAULT_ENCODING)
    stable_path = _stable_source_path(path, root=root)
    plan = build_runtime_plan_from_source(source, source_path=stable_path)
    return runtime_plan_to_json(plan)


def write_runtime_plan_snapshot_file(
    source_path: str | Path,
    snapshot_path: str | Path,
    *,
    root: str | Path | None = None,
) -> Path:
    """Write the current non-executing runtime-plan snapshot for ``source_path``."""
    destination = Path(snapshot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        source_file_to_runtime_plan_snapshot_json(source_path, root=root),
        encoding=DEFAULT_ENCODING,
    )
    return destination


def check_runtime_plan_snapshot_file(
    source_path: str | Path,
    snapshot_path: str | Path,
    *,
    root: str | Path | None = None,
) -> RuntimePlanSnapshotCheckResult:
    """Compare the current runtime plan for ``source_path`` against a snapshot."""
    expected_path = Path(snapshot_path)
    actual = source_file_to_runtime_plan_snapshot_json(source_path, root=root)
    if not expected_path.exists():
        return RuntimePlanSnapshotCheckResult(
            matched=False,
            message=f"Runtime-plan snapshot missing: {expected_path}",
            expected="",
            actual=actual,
            expected_path=expected_path,
        )
    if not expected_path.is_file():
        raise IsADirectoryError(f"runtime-plan snapshot path is not a file: {expected_path}")

    expected = expected_path.read_text(encoding=DEFAULT_ENCODING)
    matched = expected == actual
    return RuntimePlanSnapshotCheckResult(
        matched=matched,
        message=(
            f"OK: runtime-plan snapshot matches {expected_path}"
            if matched
            else f"Runtime-plan snapshot mismatch: {expected_path}"
        ),
        expected=expected,
        actual=actual,
        expected_path=expected_path,
    )


def _stable_source_path(source_path: Path, *, root: str | Path | None = None) -> str:
    path = source_path.expanduser()
    if root is not None:
        root_path = Path(root).expanduser()
        try:
            return path.resolve().relative_to(root_path.resolve()).as_posix()
        except ValueError:
            pass
    return path.name
