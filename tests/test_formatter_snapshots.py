from __future__ import annotations

from pathlib import Path

from axon.format_snapshot import (
    check_format_snapshot_file,
    source_file_to_formatted_snapshot,
    write_format_snapshot_file,
)
from axon.formatter import check_format_source, format_source
from axon.parser import parse
from axon.validator import has_errors, validate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
FORMAT_SNAPSHOT_DIR = ROOT / "tests" / "snapshots" / "formatted"


def _example_paths() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.ax"))


def _snapshot_path_for_example(path: Path) -> Path:
    return FORMAT_SNAPSHOT_DIR / f"{path.stem}.formatted.ax"


def _snapshot_paths() -> list[Path]:
    return sorted(FORMAT_SNAPSHOT_DIR.glob("*.formatted.ax"))


def test_all_examples_have_formatted_snapshots():
    missing = [path.name for path in _example_paths() if not _snapshot_path_for_example(path).exists()]
    assert not missing, "missing formatted snapshots: " + ", ".join(missing)


def test_no_orphan_formatted_snapshots():
    example_stems = {path.stem for path in _example_paths()}
    orphaned = [path.name for path in _snapshot_paths() if path.name.removesuffix(".formatted.ax") not in example_stems]
    assert not orphaned, "orphan formatted snapshots: " + ", ".join(orphaned)


def test_formatted_snapshots_match_current_formatter_output():
    for example in _example_paths():
        result = check_format_snapshot_file(example, _snapshot_path_for_example(example))
        assert result.matched, result.message


def test_formatted_snapshots_are_parseable_and_validate_without_errors():
    for snapshot in _snapshot_paths():
        source = snapshot.read_text(encoding="utf-8")
        declarations = parse(source)
        assert declarations, f"{snapshot.name} did not parse into declarations"
        diagnostics = validate(declarations)
        assert not has_errors(diagnostics), (
            f"{snapshot.name} has validation errors:\n"
            + "\n".join(diagnostic.format() for diagnostic in diagnostics)
        )


def test_formatted_snapshots_are_idempotent():
    for snapshot in _snapshot_paths():
        source = snapshot.read_text(encoding="utf-8")
        assert format_source(source) == source, f"{snapshot.name} is not formatter-idempotent"
        assert check_format_source(source).formatted, f"{snapshot.name} failed format check"


def test_write_format_snapshot_file_roundtrip(tmp_path: Path):
    example = EXAMPLES_DIR / "github_triage.ax"
    destination = tmp_path / "github_triage.formatted.ax"
    written = write_format_snapshot_file(example, destination)
    assert written == destination
    assert destination.read_text(encoding="utf-8") == source_file_to_formatted_snapshot(example)
