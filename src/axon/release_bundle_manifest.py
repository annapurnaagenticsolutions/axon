"""Release bundle manifest utilities for AXON.

The manifest is a deterministic, inspection-only inventory for handoff bundles.
It does not execute AXON agents, call providers, resolve secrets, import FastMCP,
or inspect git history. It only lists files that should be present or generated
for a high-quality release handoff.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from axon import __version__


@dataclass(frozen=True)
class ReleaseBundleItem:
    """One file or glob-derived artifact in a release bundle manifest."""

    path: str
    category: str
    description: str
    required: bool = True
    exists: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category,
            "description": self.description,
            "required": self.required,
            "exists": self.exists,
        }


@dataclass(frozen=True)
class ReleaseBundleManifest:
    """Deterministic inventory of expected release handoff artifacts."""

    project_path: str
    axon_version: str
    items: list[ReleaseBundleItem] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def existing_items(self) -> int:
        return sum(1 for item in self.items if item.exists)

    @property
    def missing_required_items(self) -> list[ReleaseBundleItem]:
        return [item for item in self.items if item.required and not item.exists]

    @property
    def missing_expected_items(self) -> list[ReleaseBundleItem]:
        return [item for item in self.items if not item.exists]

    @property
    def passed(self) -> bool:
        return not self.missing_required_items

    def to_dict(self) -> dict[str, Any]:
        categories: dict[str, dict[str, int]] = {}
        for item in self.items:
            stats = categories.setdefault(item.category, {"total": 0, "existing": 0, "missing": 0})
            stats["total"] += 1
            if item.exists:
                stats["existing"] += 1
            else:
                stats["missing"] += 1

        return {
            "project_path": self.project_path,
            "axon_version": self.axon_version,
            "passed": self.passed,
            "summary": {
                "total_items": self.total_items,
                "existing_items": self.existing_items,
                "missing_required_items": len(self.missing_required_items),
                "missing_expected_items": len(self.missing_expected_items),
                "categories": categories,
            },
            "items": [item.to_dict() for item in self.items],
        }


CORE_PROJECT_FILES: tuple[tuple[str, str], ...] = (
    ("README.md", "primary project overview"),
    ("CHANGELOG.md", "release history and change summary"),
    ("pyproject.toml", "Python package metadata and optional extras"),
    ("axon.toml", "provider configuration template without secrets"),
    (".gitignore", "repository hygiene ignore rules"),
)

QUALITY_FILES: tuple[tuple[str, str], ...] = (
    (".github/workflows/ci.yml", "GitHub Actions CI workflow"),
    (".githooks/pre-commit", "local pre-commit hook template"),
)

RELEASE_HANDOFF_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("HANDOFF_CHECKLIST.md", "generated release handoff checklist"),
    ("handoff-checklist.json", "machine-readable release handoff checklist"),
    ("RELEASE_NOTES.md", "generated release notes"),
    ("release-notes.json", "machine-readable release notes"),
    ("runtime-governance.json", "JSON runtime governance evidence"),
    ("RUNTIME_GOVERNANCE_EVIDENCE.md", "Markdown runtime governance evidence"),
    ("runtime-plan-corpus.json", "runtime-plan corpus evidence artifact"),
    ("dependency-audit.json", "dependency audit evidence artifact"),
    ("hygiene.json", "repository hygiene evidence artifact"),
    ("release-bundle-manifest.json", "machine-readable release bundle manifest"),
    ("RELEASE_BUNDLE_MANIFEST.md", "Markdown release bundle manifest"),
    ("release-artifact-consistency.json", "release artifact consistency evidence artifact"),
    ("release-artifacts.json", "release artifact writer self-report"),
)


def build_release_bundle_manifest(path: str | Path = ".") -> ReleaseBundleManifest:
    """Build a deterministic, inspection-only release bundle manifest.

    Args:
        path: Project root to inspect.

    Returns:
        ReleaseBundleManifest with required source/docs/snapshot items and
        optional generated handoff artifacts.
    """
    root = Path(path).resolve()
    items: list[ReleaseBundleItem] = []

    for rel_path, description in CORE_PROJECT_FILES:
        items.append(_item(root, rel_path, "core_project_file", description, required=True))

    for rel_path, description in QUALITY_FILES:
        items.append(_item(root, rel_path, "quality_gate_file", description, required=True))

    for rel_path in _glob_relative(root, "docs", "**/*.md"):
        items.append(_item(root, rel_path, "documentation", "project documentation", required=True))

    for rel_path in _glob_relative(root, "examples", "*.ax"):
        items.append(_item(root, rel_path, "axon_example", "AXON example source", required=True))

    for rel_path in _glob_relative(root, "tests/snapshots/examples", "*.ast.json"):
        items.append(_item(root, rel_path, "ast_snapshot", "stable AST snapshot", required=True))

    for rel_path in _glob_relative(root, "tests/snapshots/formatted", "*.formatted.ax"):
        items.append(_item(root, rel_path, "format_snapshot", "canonical formatted-source snapshot", required=True))

    for rel_path in _glob_relative(root, "tests/snapshots/runtime_plan/examples", "*.runtime-plan.json"):
        items.append(_item(root, rel_path, "runtime_plan_snapshot", "non-executing runtime-plan snapshot", required=True))

    for rel_path in _glob_relative(root, "tests/golden_errors", "*.json"):
        items.append(_item(root, rel_path, "golden_error_snapshot", "syntax/validator golden error snapshot", required=True))

    for rel_path, description in RELEASE_HANDOFF_ARTIFACTS:
        items.append(_item(root, rel_path, "release_handoff_artifact", description, required=False))

    return ReleaseBundleManifest(
        project_path=str(root),
        axon_version=__version__,
        items=sorted(items, key=lambda item: (item.category, item.path)),
    )


def release_bundle_manifest_to_json(manifest: ReleaseBundleManifest) -> str:
    """Serialize a release bundle manifest to stable JSON."""
    return json.dumps(manifest.to_dict(), indent=2, sort_keys=True)


def format_release_bundle_manifest(manifest: ReleaseBundleManifest) -> str:
    """Format a release bundle manifest for human-readable CLI output."""
    lines = [
        "AXON release bundle manifest",
        f"Project: {manifest.project_path}",
        f"AXON version: {manifest.axon_version}",
        f"Status: {'passed' if manifest.passed else 'failed'}",
        f"Items: {manifest.existing_items}/{manifest.total_items} present",
        f"Missing required: {len(manifest.missing_required_items)}",
        f"Missing expected/generated: {len(manifest.missing_expected_items)}",
        "",
        "Categories:",
    ]

    summary = manifest.to_dict()["summary"]["categories"]
    for category in sorted(summary):
        stats = summary[category]
        lines.append(
            f"  - {category}: {stats['existing']}/{stats['total']} present"
            + (f" ({stats['missing']} missing)" if stats["missing"] else "")
        )

    if manifest.missing_required_items:
        lines.extend(["", "Missing required items:"])
        for item in manifest.missing_required_items:
            lines.append(f"  - {item.path} [{item.category}] — {item.description}")

    generated_missing = [item for item in manifest.items if not item.required and not item.exists]
    if generated_missing:
        lines.extend(["", "Expected generated handoff artifacts not yet present:"])
        for item in generated_missing:
            lines.append(f"  - {item.path} — {item.description}")

    lines.extend(
        [
            "",
            "Recommended evidence commands:",
            "  axon release-artifacts . --output-dir release-artifacts",
            "  axon handoff . --output HANDOFF_CHECKLIST.md",
            "  axon handoff . --json > handoff-checklist.json",
            "  axon release-notes --output RELEASE_NOTES.md",
            "  axon release-notes --json > release-notes.json",
            "  axon runtime-governance-evidence . --output runtime-governance.json",
            "  axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown",
            "  axon runtime-plan-corpus . --json > runtime-plan-corpus.json",
            "  axon deps . --json > dependency-audit.json",
            "  axon hygiene . --json > hygiene.json",
            "  axon release-bundle-manifest . --json > release-bundle-manifest.json",
            "  axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown",
            "  axon release-artifacts-check . --json > release-artifact-consistency.json",
            "  # axon release-artifacts writes release-artifact-consistency.json and release-artifacts.json automatically",
        ]
    )
    return "\n".join(lines)


def write_release_bundle_manifest(
    output_path: str | Path,
    manifest: ReleaseBundleManifest,
    *,
    format: str | None = None,
) -> Path:
    """Write a release bundle manifest as JSON or Markdown.

    Args:
        output_path: Destination file.
        manifest: Manifest to write.
        format: Optional explicit format: ``json`` or ``markdown``. When omitted,
            ``.json`` writes JSON and any other suffix writes Markdown.
    """
    destination = Path(output_path)
    chosen = (format or _infer_format(destination)).lower()
    if chosen not in {"json", "markdown", "md"}:
        raise ValueError("release bundle manifest format must be 'json' or 'markdown'")
    content = release_bundle_manifest_to_json(manifest) if chosen == "json" else _format_markdown(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content.rstrip("\n") + "\n", encoding="utf-8")
    return destination


def _item(root: Path, rel_path: str, category: str, description: str, *, required: bool) -> ReleaseBundleItem:
    return ReleaseBundleItem(
        path=rel_path.replace("\\", "/"),
        category=category,
        description=description,
        required=required,
        exists=(root / rel_path).exists(),
    )


def _glob_relative(root: Path, base: str, pattern: str) -> list[str]:
    base_path = root / base
    if not base_path.exists():
        return []
    return sorted(str(path.relative_to(root)).replace("\\", "/") for path in base_path.glob(pattern) if path.is_file())


def _infer_format(destination: Path) -> str:
    return "json" if destination.suffix.lower() == ".json" else "markdown"


def _format_markdown(manifest: ReleaseBundleManifest) -> str:
    lines = [
        "# AXON Release Bundle Manifest",
        "",
        f"- Project: `{manifest.project_path}`",
        f"- AXON version: `{manifest.axon_version}`",
        f"- Status: **{'passed' if manifest.passed else 'failed'}**",
        f"- Items present: `{manifest.existing_items}/{manifest.total_items}`",
        f"- Missing required items: `{len(manifest.missing_required_items)}`",
        "",
        "## Items",
        "",
        "| Category | Path | Required | Exists | Description |",
        "|---|---|---:|---:|---|",
    ]
    for item in manifest.items:
        lines.append(
            f"| {item.category} | `{item.path}` | {'yes' if item.required else 'no'} | {'yes' if item.exists else 'no'} | {item.description} |"
        )
    lines.extend(
        [
            "",
            "## Recommended Evidence Commands",
            "",
            "```bash",
            "axon release-artifacts . --output-dir release-artifacts",
            "axon handoff . --output HANDOFF_CHECKLIST.md",
            "axon handoff . --json > handoff-checklist.json",
            "axon release-notes --output RELEASE_NOTES.md",
            "axon release-notes --json > release-notes.json",
            "axon runtime-governance-evidence . --output runtime-governance.json",
            "axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown",
            "axon runtime-plan-corpus . --json > runtime-plan-corpus.json",
            "axon deps . --json > dependency-audit.json",
            "axon hygiene . --json > hygiene.json",
            "axon release-bundle-manifest . --json > release-bundle-manifest.json",
            "axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown",
            "axon release-artifacts-check . --json > release-artifact-consistency.json",
            "# axon release-artifacts writes release-artifact-consistency.json and release-artifacts.json automatically",
            "```",
            "",
            "This manifest is inspection-only. It does not execute AXON agents, call providers, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.",
        ]
    )
    return "\n".join(lines)
