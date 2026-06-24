"""Safe AXON project/workspace metadata reporting.

`axon project-info` is intentionally inspection-only. It summarizes the files,
configuration, snapshots, docs, and lightweight audit status of an AXON project
without executing agents, resolving provider secrets, importing FastMCP, or
calling model/provider SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable

from axon.config import ConfigError, load_config
from axon.dependency_audit import audit_dependencies
from axon.hygiene import audit_hygiene

_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".axon",
    "build",
    "dist",
}


@dataclass(frozen=True)
class ProjectFileInventory:
    """Categorized project files relevant to the AXON toolchain."""

    axon_files: list[str] = field(default_factory=list)
    example_files: list[str] = field(default_factory=list)
    doc_files: list[str] = field(default_factory=list)
    ast_snapshots: list[str] = field(default_factory=list)
    formatted_snapshots: list[str] = field(default_factory=list)
    golden_error_snapshots: list[str] = field(default_factory=list)
    trace_logs: list[str] = field(default_factory=list)
    workflow_files: list[str] = field(default_factory=list)
    hook_files: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """Return stable category counts."""
        return {
            "axon_files": len(self.axon_files),
            "example_files": len(self.example_files),
            "doc_files": len(self.doc_files),
            "ast_snapshots": len(self.ast_snapshots),
            "formatted_snapshots": len(self.formatted_snapshots),
            "golden_error_snapshots": len(self.golden_error_snapshots),
            "trace_logs": len(self.trace_logs),
            "workflow_files": len(self.workflow_files),
            "hook_files": len(self.hook_files),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": self.counts(),
            "axon_files": list(self.axon_files),
            "example_files": list(self.example_files),
            "doc_files": list(self.doc_files),
            "ast_snapshots": list(self.ast_snapshots),
            "formatted_snapshots": list(self.formatted_snapshots),
            "golden_error_snapshots": list(self.golden_error_snapshots),
            "trace_logs": list(self.trace_logs),
            "workflow_files": list(self.workflow_files),
            "hook_files": list(self.hook_files),
        }


@dataclass(frozen=True)
class ProjectInfoReport:
    """Safe project/workspace metadata for an AXON repository."""

    project_path: str
    config_path: str | None
    config_found: bool
    config_defaults: list[str] = field(default_factory=list)
    config_providers: list[str] = field(default_factory=list)
    has_pyproject: bool = False
    has_readme: bool = False
    has_changelog: bool = False
    has_gitignore: bool = False
    has_ci_workflow: bool = False
    has_precommit_hook: bool = False
    inventory: ProjectFileInventory = field(default_factory=ProjectFileInventory)
    hygiene_passed: bool | None = None
    hygiene_errors: int | None = None
    hygiene_warnings: int | None = None
    dependency_audit_passed: bool | None = None
    dependency_errors: int | None = None
    dependency_warnings: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable, secret-safe representation."""
        return {
            "project_path": self.project_path,
            "config_path": self.config_path,
            "config_found": self.config_found,
            "config_defaults": list(self.config_defaults),
            "config_providers": list(self.config_providers),
            "has_pyproject": self.has_pyproject,
            "has_readme": self.has_readme,
            "has_changelog": self.has_changelog,
            "has_gitignore": self.has_gitignore,
            "has_ci_workflow": self.has_ci_workflow,
            "has_precommit_hook": self.has_precommit_hook,
            "inventory": self.inventory.to_dict(),
            "hygiene": {
                "passed": self.hygiene_passed,
                "errors": self.hygiene_errors,
                "warnings": self.hygiene_warnings,
            },
            "dependency_audit": {
                "passed": self.dependency_audit_passed,
                "errors": self.dependency_errors,
                "warnings": self.dependency_warnings,
            },
            "notes": list(self.notes),
        }


def collect_project_info(project_path: str | Path = ".") -> ProjectInfoReport:
    """Collect safe metadata for an AXON project directory.

    The report is informational: hygiene/dependency audit failures are reflected
    in the report but do not make collection fail. Missing or non-directory
    project paths still raise a normal file-system exception.
    """
    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"project path is not a directory: {root}")

    notes: list[str] = []
    try:
        config = load_config(start=root)
    except ConfigError as exc:
        config = None
        notes.append(f"config could not be loaded: {exc}")

    try:
        hygiene = audit_hygiene(root)
        hygiene_passed: bool | None = hygiene.passed
        hygiene_errors: int | None = hygiene.error_count
        hygiene_warnings: int | None = hygiene.warning_count
    except Exception as exc:  # pragma: no cover - defensive, keeps info command non-invasive
        hygiene_passed = None
        hygiene_errors = None
        hygiene_warnings = None
        notes.append(f"hygiene audit could not run: {exc}")

    try:
        deps = audit_dependencies(root)
        deps_passed: bool | None = deps.passed
        deps_errors: int | None = deps.error_count
        deps_warnings: int | None = deps.warning_count
    except Exception as exc:  # pragma: no cover - defensive, keeps info command non-invasive
        deps_passed = None
        deps_errors = None
        deps_warnings = None
        notes.append(f"dependency audit could not run: {exc}")

    config_path = str(config.path) if config and config.path else None
    config_defaults = sorted(config.defaults.keys()) if config else []
    config_providers = sorted(config.providers.keys()) if config else []

    return ProjectInfoReport(
        project_path=str(root),
        config_path=config_path,
        config_found=config_path is not None,
        config_defaults=config_defaults,
        config_providers=config_providers,
        has_pyproject=(root / "pyproject.toml").is_file(),
        has_readme=(root / "README.md").is_file(),
        has_changelog=(root / "CHANGELOG.md").is_file(),
        has_gitignore=(root / ".gitignore").is_file(),
        has_ci_workflow=any((root / ".github" / "workflows").glob("*.yml"))
        or any((root / ".github" / "workflows").glob("*.yaml")),
        has_precommit_hook=(root / ".githooks" / "pre-commit").is_file(),
        inventory=_collect_inventory(root),
        hygiene_passed=hygiene_passed,
        hygiene_errors=hygiene_errors,
        hygiene_warnings=hygiene_warnings,
        dependency_audit_passed=deps_passed,
        dependency_errors=deps_errors,
        dependency_warnings=deps_warnings,
        notes=notes,
    )


def project_info_to_json(report: ProjectInfoReport) -> str:
    """Render a project-info report as stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def format_project_info(report: ProjectInfoReport) -> str:
    """Render a project-info report for humans."""
    counts = report.inventory.counts()
    lines = [
        "AXON project information",
        f"Project: {report.project_path}",
        f"Config: {report.config_path if report.config_path else '<not found>'}",
        f"Providers: {', '.join(report.config_providers) if report.config_providers else '<none>'}",
        f"Defaults: {', '.join(report.config_defaults) if report.config_defaults else '<none>'}",
        "Files:",
        f"  AXON sources: {counts['axon_files']}",
        f"  Examples: {counts['example_files']}",
        f"  Docs: {counts['doc_files']}",
        f"  AST snapshots: {counts['ast_snapshots']}",
        f"  Formatter snapshots: {counts['formatted_snapshots']}",
        f"  Golden error snapshots: {counts['golden_error_snapshots']}",
        f"  Trace logs: {counts['trace_logs']}",
        f"  CI workflows: {counts['workflow_files']}",
        f"  Git hooks: {counts['hook_files']}",
        "Project files:",
        f"  pyproject.toml: {_yes_no(report.has_pyproject)}",
        f"  README.md: {_yes_no(report.has_readme)}",
        f"  CHANGELOG.md: {_yes_no(report.has_changelog)}",
        f"  .gitignore: {_yes_no(report.has_gitignore)}",
        f"  CI workflow: {_yes_no(report.has_ci_workflow)}",
        f"  pre-commit hook: {_yes_no(report.has_precommit_hook)}",
        "Audits:",
        f"  Hygiene: {_status(report.hygiene_passed, report.hygiene_errors, report.hygiene_warnings)}",
        f"  Dependencies: {_status(report.dependency_audit_passed, report.dependency_errors, report.dependency_warnings)}",
    ]
    if report.notes:
        lines.append("Notes:")
        lines.extend(f"  - {note}" for note in report.notes)
    return "\n".join(lines)


def _collect_inventory(root: Path) -> ProjectFileInventory:
    all_files = list(_iter_project_files(root))
    return ProjectFileInventory(
        axon_files=_relative_sorted(root, (path for path in all_files if path.suffix == ".ax")),
        example_files=_relative_sorted(root, (path for path in all_files if _is_under(path, root / "examples") and path.suffix == ".ax")),
        doc_files=_relative_sorted(root, (path for path in all_files if (path.suffix.lower() == ".md" and (_is_under(path, root / "docs") or path.name in {"README.md", "CHANGELOG.md"})))),
        ast_snapshots=_relative_sorted(root, (path for path in all_files if _is_under(path, root / "tests" / "snapshots") and path.name.endswith(".ast.json"))),
        formatted_snapshots=_relative_sorted(root, (path for path in all_files if _is_under(path, root / "tests" / "snapshots") and path.name.endswith(".formatted.ax"))),
        golden_error_snapshots=_relative_sorted(root, (path for path in all_files if _is_under(path, root / "tests" / "golden_errors") and path.suffix == ".json")),
        trace_logs=_relative_sorted(root, (path for path in all_files if path.suffix == ".jsonl")),
        workflow_files=_relative_sorted(root, (path for path in all_files if _is_under(path, root / ".github" / "workflows") and path.suffix in {".yml", ".yaml"})),
        hook_files=_relative_sorted(root, (path for path in all_files if _is_under(path, root / ".githooks"))),
    )


def _iter_project_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:  # pragma: no cover - defensive
            continue
        if any(part in _SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        if path.is_file():
            yield path


def _relative_sorted(root: Path, paths: Iterable[Path]) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in paths)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _status(passed: bool | None, errors: int | None, warnings: int | None) -> str:
    if passed is None:
        return "unknown"
    label = "PASS" if passed else "FAIL"
    return f"{label} ({errors or 0} error(s), {warnings or 0} warning(s))"
