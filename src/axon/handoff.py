"""Release handoff checklist utilities for AXON projects.

The handoff checklist is intentionally non-invasive: it does not run checks,
execute agents, resolve secrets, import FastMCP, or call providers. It turns the
existing safe AXON inspection and quality-gate commands into a repeatable release
handoff workflow that project maintainers can copy into issue trackers, release
notes, or bundle summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HandoffCommand:
    """One command that should be run or recorded during release handoff."""

    name: str
    command: list[str]
    purpose: str
    required: bool = True

    @property
    def shell(self) -> str:
        """Return a shell-friendly display form."""
        return " ".join(self.command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "shell": self.shell,
            "purpose": self.purpose,
            "required": self.required,
        }


@dataclass(frozen=True)
class HandoffChecklist:
    """Safe release handoff checklist for an AXON project."""

    project_path: str
    full: bool
    commands: list[HandoffCommand] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "full": self.full,
            "commands": [command.to_dict() for command in self.commands],
            "documents": list(self.documents),
            "notes": list(self.notes),
        }


def build_handoff_checklist(project_path: str | Path = ".", *, full: bool = False) -> HandoffChecklist:
    """Build a deterministic, safe handoff checklist for a project.

    Args:
        project_path: AXON project directory. The path must exist and be a directory.
        full: When true, the checklist asks project-quality gates to include smoke
            checks. When false, it keeps local handoff checks fast with `--no-smoke`.

    Raises:
        FileNotFoundError: if the project path does not exist.
        NotADirectoryError: if the path is not a directory.
    """
    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"project path is not a directory: {root}")

    project_arg = _display_project_arg(root)
    snapshot_dir = root / "tests" / "snapshots" / "examples"
    snapshot_arg = _display_relative(snapshot_dir, root) if snapshot_dir.is_dir() else "tests/snapshots/examples"

    check_project = [
        "axon",
        "check-project",
        project_arg,
        "--snapshot-dir",
        snapshot_arg,
        "--require-snapshots",
    ]
    if not full:
        check_project.append("--no-smoke")

    precommit = ["axon", "precommit", "run", "--path", project_arg]
    if full:
        precommit.append("--full")

    handoff_command = ["axon", "handoff", project_arg, "--output", "HANDOFF_CHECKLIST.md"]
    if full:
        handoff_command.append("--full")

    commands = [
        HandoffCommand(
            name="handoff-checklist",
            command=handoff_command,
            purpose="Write the release handoff checklist artifact for the bundle.",
        ),
        HandoffCommand(
            name="release-artifacts",
            command=[
                "axon",
                "release-artifacts",
                project_arg,
                "--output-dir",
                "release-artifacts",
                "--change",
                '"describe the change"',
                "--tests",
                '"paste validation evidence"',
            ],
            purpose="Write the standard one-command release artifact directory for final handoff.",
        ),
        HandoffCommand(
            name="release-artifacts-check",
            command=["axon", "release-artifacts-check", project_arg],
            purpose="Confirm release artifact names are aligned across writer, manifest, handoff checklist, README, and release docs.",
        ),
        HandoffCommand(
            name="version",
            command=["axon", "version"],
            purpose="Record the AXON release/build version in the handoff.",
        ),
        HandoffCommand(
            name="environment-info",
            command=["axon", "info", "--path", project_arg],
            purpose="Record safe Python, platform, module, capability, and config-discovery metadata.",
        ),
        HandoffCommand(
            name="project-info",
            command=["axon", "project-info", project_arg],
            purpose="Summarize safe project inventory, docs, snapshots, config providers, and audit status.",
        ),
        HandoffCommand(
            name="foundation-audit",
            command=["axon", "foundation-audit", project_arg],
            purpose="Audit the Phase 1 compiler/tooling foundation before moving into runtime-adjacent work.",
        ),
        HandoffCommand(
            name="dependency-audit",
            command=["axon", "deps", project_arg],
            purpose="Confirm compiler-core dependencies and optional extras remain clean.",
        ),
        HandoffCommand(
            name="repository-hygiene",
            command=["axon", "hygiene", project_arg],
            purpose="Confirm generated files, traces, caches, virtualenvs, and local secrets are ignored safely.",
        ),
        HandoffCommand(
            name="project-quality-gate",
            command=check_project,
            purpose="Run syntax, validation, AST snapshot, and generated-server smoke checks for the project.",
        ),
        HandoffCommand(
            name="precommit-quality-gate",
            command=precommit,
            purpose="Run the same local quality gate expected before committing changes.",
        ),
        HandoffCommand(
            name="runtime-governance-evidence",
            command=[
                "axon",
                "runtime-governance-evidence",
                project_arg,
                "--output",
                "runtime-governance.json",
            ],
            purpose="Write the inspection-only runtime governance evidence artifact for release handoff.",
        ),
        HandoffCommand(
            name="runtime-governance-evidence-markdown",
            command=[
                "axon",
                "runtime-governance-evidence",
                project_arg,
                "--output",
                "RUNTIME_GOVERNANCE_EVIDENCE.md",
                "--format",
                "markdown",
            ],
            purpose="Write a Markdown runtime governance evidence artifact for reviewers.",
            required=False,
        ),
        HandoffCommand(
            name="release-bundle-manifest",
            command=[
                "axon",
                "release-bundle-manifest",
                project_arg,
                "--output",
                "release-bundle-manifest.json",
            ],
            purpose="Write the deterministic release bundle inventory that lists source, docs, snapshots, quality gates, and expected handoff artifacts.",
        ),
        HandoffCommand(
            name="release-bundle-manifest-markdown",
            command=[
                "axon",
                "release-bundle-manifest",
                project_arg,
                "--output",
                "RELEASE_BUNDLE_MANIFEST.md",
                "--format",
                "markdown",
            ],
            purpose="Write a Markdown release bundle manifest for reviewers.",
            required=False,
        ),
        HandoffCommand(
            name="release-notes",
            command=[
                "axon",
                "release-notes",
                "--path",
                project_arg,
                "--change",
                '"describe the change"',
                "--tests",
                '"paste validation evidence"',
                "--output",
                "RELEASE_NOTES.md",
            ],
            purpose="Generate release notes with explicit change bullets and validation evidence.",
        ),
    ]

    documents = [
        "README.md",
        "CHANGELOG.md",
        "docs/CLI_REFERENCE.md",
        "docs/HANDOFF.md",
        "docs/FOUNDATION_AUDIT.md",
        "docs/ROADMAP.md",
        "docs/CI.md",
        "docs/PRECOMMIT.md",
        "docs/HYGIENE.md",
        "docs/RUNTIME_GOVERNANCE.md",
        "docs/RUNTIME_GOVERNANCE_EVIDENCE.md",
        "docs/RELEASE_ARTIFACTS.md",
        "docs/RELEASE_BUNDLE.md",
    ]

    notes = [
        "The checklist is inspection-only; it does not execute AXON agent bodies or call providers.",
        "Run axon foundation-audit before crossing from compiler/tooling foundation work into runtime-adjacent work.",
        "Do not paste API keys into .ax files, release notes, issue trackers, or handoff summaries.",
        "Use --full when preparing a release bundle that should include generated-server smoke checks.",
        "Include runtime-governance.json for any runtime-plan, runtime-boundary, or runtime-governance change.",
        "Use axon release-artifacts for the standard one-command handoff directory when preparing final bundles.",
        "Include release-bundle-manifest.json and RELEASE_BUNDLE_MANIFEST.md in every final release handoff bundle.",
        "The standard release artifact set includes HANDOFF_CHECKLIST.md, handoff-checklist.json, RELEASE_NOTES.md, release-notes.json, runtime-governance.json, RUNTIME_GOVERNANCE_EVIDENCE.md, runtime-plan-corpus.json, dependency-audit.json, hygiene.json, release-bundle-manifest.json, RELEASE_BUNDLE_MANIFEST.md, release-artifact-consistency.json, and release-artifacts.json.",
    ]

    return HandoffChecklist(
        project_path=str(root),
        full=full,
        commands=commands,
        documents=documents,
        notes=notes,
    )


def handoff_checklist_to_json(checklist: HandoffChecklist) -> str:
    """Render a handoff checklist as stable JSON."""
    return json.dumps(checklist.to_dict(), indent=2, sort_keys=True)


def format_handoff_checklist(checklist: HandoffChecklist) -> str:
    """Render a human-readable handoff checklist."""
    lines = [
        "AXON release handoff checklist",
        f"Project: {checklist.project_path}",
        f"Mode: {'full release' if checklist.full else 'fast handoff'}",
        "",
        "Commands to run and record:",
    ]
    for index, command in enumerate(checklist.commands, start=1):
        required = "required" if command.required else "optional"
        lines.extend(
            [
                f"{index}. [{required}] {command.name}",
                f"   command: {command.shell}",
                f"   purpose: {command.purpose}",
            ]
        )

    lines.extend(["", "Documents to review/update:"])
    lines.extend(f"- {document}" for document in checklist.documents)

    if checklist.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in checklist.notes)

    return "\n".join(lines)


def write_handoff_checklist(path: str | Path, checklist: HandoffChecklist, *, json_output: bool = False) -> Path:
    """Write a handoff checklist as Markdown-like text or JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = handoff_checklist_to_json(checklist) if json_output else format_handoff_checklist(checklist)
    destination.write_text(content + "\n", encoding="utf-8")
    return destination


def _display_project_arg(root: Path) -> str:
    cwd = Path.cwd().resolve()
    if root == cwd:
        return "."
    try:
        return _display_relative(root, cwd)
    except ValueError:
        return str(root)


def _display_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())
