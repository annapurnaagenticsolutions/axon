"""Release-note and changelog generation helpers for AXON.

The Phase 1 prototype intentionally keeps release notes deterministic and
secret-safe. This module does not inspect git history and does not execute any
AXON source. It formats explicit change/test inputs together with safe project
metadata so every handoff bundle can clearly report what changed, which CLI
commands are available, and which validation/test evidence was collected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from axon.info import CAPABILITIES, collect_info, get_version


DEFAULT_CHANGE = "Maintenance release generated from current AXON project metadata."
DEFAULT_STATUS = "Phase 1 compiler/tooling prototype"


@dataclass(frozen=True)
class ReleaseNotes:
    """Structured release-note content suitable for Markdown or JSON output."""

    version: str
    date: str
    status: str
    project_path: str
    commands: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    ax_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable representation."""
        return {
            "version": self.version,
            "date": self.date,
            "status": self.status,
            "project_path": self.project_path,
            "commands": list(self.commands),
            "capabilities": list(self.capabilities),
            "changes": list(self.changes),
            "tests": list(self.tests),
            "ax_files": list(self.ax_files),
            "ax_file_count": len(self.ax_files),
        }


def normalize_items(items: Iterable[str] | None) -> list[str]:
    """Normalize user-supplied release-note bullet items.

    Empty strings are ignored. Leading Markdown bullet markers are removed so the
    renderer can produce consistent output regardless of how the caller supplied
    the values.
    """
    normalized: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if not text:
            continue
        while text.startswith(('-', '*')):
            text = text[1:].strip()
        if text:
            normalized.append(text)
    return normalized


def discover_ax_files(project_path: str | Path) -> list[str]:
    """Return project-relative `.ax` files, excluding hidden/cache directories."""
    root = Path(project_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []

    ignored_parts = {".git", ".pytest_cache", "__pycache__", ".venv", "venv"}
    files: list[str] = []
    for path in root.rglob("*.ax"):
        if any(part in ignored_parts for part in path.parts):
            continue
        try:
            files.append(path.relative_to(root).as_posix())
        except ValueError:
            files.append(str(path))
    return sorted(files)


def build_release_notes(
    *,
    version: str | None = None,
    release_date: str | None = None,
    project_path: str | Path = ".",
    commands: Sequence[str] | None = None,
    changes: Iterable[str] | None = None,
    tests: Iterable[str] | None = None,
    status: str = DEFAULT_STATUS,
) -> ReleaseNotes:
    """Collect safe metadata and return structured release notes."""
    project = Path(project_path).expanduser().resolve()
    normalized_changes = normalize_items(changes)
    normalized_tests = normalize_items(tests)
    metadata = collect_info(project_path=project)

    return ReleaseNotes(
        version=version or get_version(),
        date=release_date or date.today().isoformat(),
        status=status,
        project_path=str(project),
        commands=sorted(set(commands or [])),
        capabilities=list(metadata.capabilities or CAPABILITIES),
        changes=normalized_changes or [DEFAULT_CHANGE],
        tests=normalized_tests,
        ax_files=discover_ax_files(project),
    )


def release_notes_to_json(notes: ReleaseNotes) -> str:
    """Render release notes as stable JSON."""
    return json.dumps(notes.to_dict(), indent=2, sort_keys=True)


def format_release_notes(notes: ReleaseNotes) -> str:
    """Render release notes as Markdown."""
    lines = [
        f"# AXON Release Notes — {notes.version}",
        "",
        f"Date: {notes.date}",
        f"Status: {notes.status}",
        "",
        "## Changes",
    ]
    lines.extend(_bullet_lines(notes.changes))

    lines.extend(["", "## Validation evidence"])
    if notes.tests:
        lines.extend(_bullet_lines(notes.tests))
    else:
        lines.append("- No test summary was supplied. Run `pytest` and add `--tests \"N passed\"` for release evidence.")

    lines.extend(["", "## CLI commands"])
    if notes.commands:
        lines.extend(_bullet_lines(f"axon {command}" for command in notes.commands))
    else:
        lines.append("- No CLI command list supplied.")

    lines.extend(["", "## Capabilities"])
    lines.extend(_bullet_lines(notes.capabilities))

    lines.extend(["", "## AXON source corpus"])
    if notes.ax_files:
        lines.append(f"- {len(notes.ax_files)} `.ax` file(s) discovered under `{notes.project_path}`.")
        for rel_path in notes.ax_files:
            lines.append(f"  - `{rel_path}`")
    else:
        lines.append(f"- No `.ax` files discovered under `{notes.project_path}`.")

    lines.extend([
        "",
        "## Notes",
        "- This report is generated from safe local metadata and explicit release inputs.",
        "- Provider secrets and API keys are not resolved or printed.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def write_release_notes(path: str | Path, notes: ReleaseNotes, *, json_output: bool = False) -> Path:
    """Write Markdown or JSON release notes to disk and return the destination."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = release_notes_to_json(notes) + "\n" if json_output else format_release_notes(notes)
    destination.write_text(content, encoding="utf-8")
    return destination


def _bullet_lines(items: Iterable[str]) -> list[str]:
    return [f"- {item}" for item in items]
