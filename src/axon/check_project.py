"""Project-level quality gate for AXON projects.

The checker intentionally composes existing deterministic building blocks:
syntax diagnostics, semantic validation, AST snapshot comparison, config loading,
and generated-server smoke testing. It does not execute AXON agents or call model
providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Literal

from axon.ast_snapshot import check_snapshot_file
from axon.config import CONFIG_FILENAME, ConfigError, load_config
from axon.smoke import smoke_test_source_file
from axon.syntax import check_syntax_file
from axon.validator import diagnostics_to_json, has_errors, validate
from axon.parser import parse

CheckStatus = Literal["pass", "fail", "warn", "skip"]
DEFAULT_ENCODING = "utf-8"
_EXCLUDED_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "snapshots", "fixtures"}


@dataclass(frozen=True)
class ProjectCheckItem:
    """One project quality-gate result item."""

    name: str
    status: CheckStatus
    message: str
    path: str | None = None
    code: str = ""

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "path": self.path,
            "code": self.code,
        }

    def format(self) -> str:
        icon = {"pass": "OK", "fail": "FAIL", "warn": "WARN", "skip": "SKIP"}[self.status]
        path = f" {self.path}" if self.path else ""
        code = f" [{self.code}]" if self.code else ""
        return f"{icon}: {self.name}{path}: {self.message}{code}"


@dataclass
class ProjectCheckReport:
    """Structured result for a full AXON project quality check."""

    project_root: Path
    files_checked: list[Path] = field(default_factory=list)
    items: list[ProjectCheckItem] = field(default_factory=list)
    warnings_as_errors: bool = False

    @property
    def passed(self) -> bool:
        if any(item.status == "fail" for item in self.items):
            return False
        if self.warnings_as_errors and any(item.status == "warn" for item in self.items):
            return False
        return True

    def counts(self) -> dict[str, int]:
        counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
        for item in self.items:
            counts[item.status] += 1
        return counts

    def to_dict(self) -> dict[str, object]:
        return {
            "project_root": str(self.project_root),
            "passed": self.passed,
            "warnings_as_errors": self.warnings_as_errors,
            "files_checked": [str(path) for path in self.files_checked],
            "counts": self.counts(),
            "items": [item.to_dict() for item in self.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def format(self) -> str:
        counts = self.counts()
        status = "passed" if self.passed else "failed"
        lines = [
            f"AXON project check {status}: {self.project_root}",
            f"Files checked: {len(self.files_checked)}",
            f"Results: {counts['pass']} passed, {counts['fail']} failed, {counts['warn']} warnings, {counts['skip']} skipped",
        ]
        if self.items:
            lines.append("")
            lines.extend(item.format() for item in self.items)
        return "\n".join(lines)


def check_project(
    project_root: str | Path = ".",
    *,
    no_smoke: bool = False,
    warnings_as_errors: bool = False,
    snapshot_dir: str | Path | None = None,
    require_snapshots: bool = False,
) -> ProjectCheckReport:
    """Run deterministic project-level checks for an AXON project.

    The checker scans ``*.ax`` files, validates ``axon.toml`` when present,
    optionally compares AST snapshots, and smoke-tests generated server code.
    It never calls external model providers.
    """
    root = Path(project_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"project path is not a directory: {root}")

    report = ProjectCheckReport(project_root=root, warnings_as_errors=warnings_as_errors)
    axon_files = list(find_axon_files(root))
    report.files_checked = axon_files

    _check_config(root, report)
    if not axon_files:
        report.items.append(
            ProjectCheckItem(
                name="source-discovery",
                status="fail",
                message="no .ax files found in project",
                code="no-axon-files",
            )
        )
        return report

    snapshot_root = _resolve_snapshot_root(root, snapshot_dir)

    for source in axon_files:
        _check_source_file(
            source,
            root=root,
            report=report,
            no_smoke=no_smoke,
            warnings_as_errors=warnings_as_errors,
            snapshot_root=snapshot_root,
            require_snapshots=require_snapshots,
        )

    return report


def find_axon_files(project_root: str | Path) -> list[Path]:
    """Return project ``*.ax`` files while skipping common generated/vendor dirs."""
    root = Path(project_root)
    files: list[Path] = []
    for path in root.rglob("*.ax"):
        if any(part in _EXCLUDED_DIRS or part.startswith(".") and part not in {"."} for part in path.relative_to(root).parts[:-1]):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def _check_config(root: Path, report: ProjectCheckReport) -> None:
    config_path = root / CONFIG_FILENAME
    if not config_path.exists():
        report.items.append(
            ProjectCheckItem(
                name="config",
                status="warn",
                message="axon.toml not found; provider defaults will be empty",
                code="missing-config",
            )
        )
        return
    try:
        config = load_config(path=config_path)
    except ConfigError as exc:
        report.items.append(
            ProjectCheckItem(
                name="config",
                status="fail",
                message=str(exc),
                path=str(config_path),
                code="invalid-config",
            )
        )
        return
    provider_count = len(config.providers)
    default_count = len(config.defaults)
    report.items.append(
        ProjectCheckItem(
            name="config",
            status="pass",
            message=f"loaded axon.toml with {provider_count} provider(s) and {default_count} default(s)",
            path=str(config_path),
            code="config-ok",
        )
    )


def _check_source_file(
    source: Path,
    *,
    root: Path,
    report: ProjectCheckReport,
    no_smoke: bool,
    warnings_as_errors: bool,
    snapshot_root: Path | None,
    require_snapshots: bool,
) -> None:
    display_path = str(source.relative_to(root))

    syntax = check_syntax_file(source)
    if not syntax.ok:
        report.items.append(
            ProjectCheckItem(
                name="syntax",
                status="fail",
                message=syntax.format(),
                path=display_path,
                code="syntax-error",
            )
        )
        report.items.append(
            ProjectCheckItem(
                name="validation",
                status="skip",
                message="skipped because syntax failed",
                path=display_path,
                code="syntax-failed",
            )
        )
        if not no_smoke:
            report.items.append(
                ProjectCheckItem(
                    name="smoke",
                    status="skip",
                    message="skipped because syntax failed",
                    path=display_path,
                    code="syntax-failed",
                )
            )
        return

    report.items.append(
        ProjectCheckItem(
            name="syntax",
            status="pass",
            message=f"parsed {len(syntax.declarations)} declaration(s)",
            path=display_path,
            code="syntax-ok",
        )
    )

    try:
        declarations = parse(source.read_text(encoding=DEFAULT_ENCODING))
        diagnostics = validate(declarations)
    except Exception as exc:  # pragma: no cover - defensive; syntax already passed
        report.items.append(
            ProjectCheckItem(
                name="validation",
                status="fail",
                message=f"validation crashed: {type(exc).__name__}: {exc}",
                path=display_path,
                code="validation-crash",
            )
        )
        return

    if diagnostics:
        status: CheckStatus = "fail" if has_errors(diagnostics) or warnings_as_errors else "warn"
        report.items.append(
            ProjectCheckItem(
                name="validation",
                status=status,
                message=diagnostics_to_json(diagnostics).strip(),
                path=display_path,
                code="validation-diagnostics",
            )
        )
    else:
        report.items.append(
            ProjectCheckItem(
                name="validation",
                status="pass",
                message="no validation diagnostics",
                path=display_path,
                code="validation-ok",
            )
        )

    _check_snapshot(source, root=root, report=report, snapshot_root=snapshot_root, require_snapshots=require_snapshots)

    if no_smoke:
        report.items.append(
            ProjectCheckItem(
                name="smoke",
                status="skip",
                message="skipped by --no-smoke",
                path=display_path,
                code="smoke-skipped",
            )
        )
        return

    try:
        smoke_report = smoke_test_source_file(source)
    except Exception as exc:
        report.items.append(
            ProjectCheckItem(
                name="smoke",
                status="fail",
                message=str(exc),
                path=display_path,
                code="smoke-error",
            )
        )
        return

    if smoke_report.passed:
        report.items.append(
            ProjectCheckItem(
                name="smoke",
                status="pass",
                message="generated server passed smoke test",
                path=display_path,
                code="smoke-ok",
            )
        )
    else:
        report.items.append(
            ProjectCheckItem(
                name="smoke",
                status="fail",
                message="; ".join(diag.format() for diag in smoke_report.diagnostics),
                path=display_path,
                code="smoke-failed",
            )
        )


def _check_snapshot(
    source: Path,
    *,
    root: Path,
    report: ProjectCheckReport,
    snapshot_root: Path | None,
    require_snapshots: bool,
) -> None:
    display_path = str(source.relative_to(root))
    snapshot = _snapshot_path_for_source(source, root=root, snapshot_root=snapshot_root)
    if snapshot is None:
        if require_snapshots:
            report.items.append(
                ProjectCheckItem(
                    name="ast-snapshot",
                    status="fail",
                    message="no snapshot directory found",
                    path=display_path,
                    code="missing-snapshot-dir",
                )
            )
        else:
            report.items.append(
                ProjectCheckItem(
                    name="ast-snapshot",
                    status="skip",
                    message="no snapshot directory found",
                    path=display_path,
                    code="snapshot-skipped",
                )
            )
        return

    if not snapshot.exists():
        report.items.append(
            ProjectCheckItem(
                name="ast-snapshot",
                status="fail" if require_snapshots else "warn",
                message=f"snapshot not found: {snapshot}",
                path=display_path,
                code="missing-snapshot",
            )
        )
        return

    try:
        result = check_snapshot_file(source, snapshot)
    except Exception as exc:
        report.items.append(
            ProjectCheckItem(
                name="ast-snapshot",
                status="fail",
                message=str(exc),
                path=display_path,
                code="snapshot-error",
            )
        )
        return

    report.items.append(
        ProjectCheckItem(
            name="ast-snapshot",
            status="pass" if result.matched else "fail",
            message=result.message,
            path=display_path,
            code="snapshot-ok" if result.matched else "snapshot-mismatch",
        )
    )


def _resolve_snapshot_root(root: Path, snapshot_dir: str | Path | None) -> Path | None:
    if snapshot_dir is not None:
        return Path(snapshot_dir).expanduser().resolve()
    examples_snapshot = root / "tests" / "snapshots" / "examples"
    if examples_snapshot.exists():
        return examples_snapshot
    generic_snapshot = root / "tests" / "snapshots"
    if generic_snapshot.exists():
        return generic_snapshot
    return None


def _snapshot_path_for_source(source: Path, *, root: Path, snapshot_root: Path | None) -> Path | None:
    if snapshot_root is None:
        return None
    # The bundled AXON corpus stores examples/* snapshots in tests/snapshots/examples.
    return snapshot_root / f"{source.stem}.ast.json"
