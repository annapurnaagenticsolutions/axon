"""Phase 1 foundation audit for AXON.

This module provides a high-level, inspection-only checkpoint across the Phase 1
compiler/tooling foundation. It intentionally does not execute AXON agents, call
providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index
RAG data, execute flows, or replay traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


NON_EXECUTION_GUARANTEE = (
    "foundation audit is inspection-only: it does not execute AXON agents, call providers, "
    "dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, "
    "execute flows, or replay traces"
)

FOUNDATION_AREAS: tuple[str, ...] = (
    "parser_ast",
    "validation_diagnostics",
    "codegen_smoke",
    "configuration_security",
    "formatting_snapshots",
    "trace_tooling",
    "runtime_plan_boundary",
    "runtime_governance",
    "release_handoff",
    "developer_workflow",
)

REQUIRED_SOURCE_MODULES: tuple[str, ...] = (
    "src/axon/ast_nodes.py",
    "src/axon/parser.py",
    "src/axon/validator.py",
    "src/axon/syntax.py",
    "src/axon/ast_snapshot.py",
    "src/axon/formatter.py",
    "src/axon/format_snapshot.py",
    "src/axon/codegen/mcp.py",
    "src/axon/smoke.py",
    "src/axon/config.py",
    "src/axon/trace.py",
    "src/axon/trace_extract.py",
    "src/axon/trace_reader.py",
    "src/axon/runtime_plan.py",
    "src/axon/runtime_plan_corpus.py",
    "src/axon/runtime_plan_review.py",
    "src/axon/runtime_plan_review_consistency.py",
    "src/axon/runtime_governance.py",
    "src/axon/runtime_governance_evidence.py",
    "src/axon/release_artifacts.py",
    "src/axon/release_artifact_consistency.py",
    "src/axon/release_bundle_manifest.py",
    "src/axon/handoff.py",
    "src/axon/dependency_audit.py",
    "src/axon/hygiene.py",
    "src/axon/precommit.py",
    "src/axon/cli.py",
)

REQUIRED_DOCS: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "docs/CLI_REFERENCE.md",
    "docs/ROADMAP.md",
    "docs/RUNTIME_BOUNDARY.md",
    "docs/RUNTIME_PLAN.md",
    "docs/RUNTIME_PLAN_REVIEW.md",
    "docs/RUNTIME_PLAN_REVIEW_CONSISTENCY.md",
    "docs/RUNTIME_GOVERNANCE.md",
    "docs/RUNTIME_GOVERNANCE_EVIDENCE.md",
    "docs/RELEASE_ARTIFACTS.md",
    "docs/RELEASE_ARTIFACTS_CONSISTENCY.md",
    "docs/RELEASE_BUNDLE.md",
    "docs/HANDOFF.md",
    "docs/CONTRIBUTING.md",
    "docs/TASK_TICKET_TEMPLATE.md",
    "docs/PRECOMMIT.md",
    "docs/HYGIENE.md",
    "docs/FOUNDATION_AUDIT.md",
    "docs/runtime-rfcs/0001-minimal-non-executing-runtime.md",
)

REQUIRED_SNAPSHOT_DIRS: tuple[str, ...] = (
    "tests/snapshots/examples",
    "tests/snapshots/formatted",
    "tests/snapshots/runtime_plan/examples",
    "tests/golden_errors",
)

REQUIRED_EXAMPLES: tuple[str, ...] = (
    "examples/hello.ax",
    "examples/types.ax",
    "examples/prompts.ax",
    "examples/rag.ax",
    "examples/flow.ax",
    "examples/trace_preview.ax",
    "examples/github_triage.ax",
    "examples/customer_support.ax",
    "examples/invoice_extraction.ax",
    "examples/monitoring_alerts.ax",
    "examples/meeting_notes.ax",
    "examples/data_analysis.ax",
    "examples/debate.ax",
)

REQUIRED_TEST_FILES: tuple[str, ...] = (
    "tests/test_parser.py",
    "tests/test_validator.py",
    "tests/test_syntax.py",
    "tests/test_codegen_mcp.py",
    "tests/test_smoke.py",
    "tests/test_formatter.py",
    "tests/test_formatter_corpus.py",
    "tests/test_formatter_snapshots.py",
    "tests/test_ast_snapshot.py",
    "tests/test_golden_errors.py",
    "tests/test_runtime_plan.py",
    "tests/test_runtime_plan_corpus.py",
    "tests/test_runtime_plan_snapshots.py",
    "tests/test_runtime_plan_docs.py",
    "tests/test_runtime_governance.py",
    "tests/test_runtime_governance_evidence.py",
    "tests/test_release_artifacts.py",
    "tests/test_release_artifact_consistency.py",
    "tests/test_handoff.py",
    "tests/test_cli_help_consistency.py",
    "tests/test_docs.py",
)

REQUIRED_DOC_PHRASES: dict[str, tuple[str, ...]] = {
    "README.md": (
        "axon foundation-audit",
        "non-executing runtime-plan inspection",
        "method execution, provider calls, tool dispatch",
    ),
    "docs/CLI_REFERENCE.md": (
        "axon foundation-audit",
        "--json",
    ),
    "docs/HANDOFF.md": (
        "axon foundation-audit",
        "release-artifacts",
    ),
    "docs/ROADMAP.md": (
        "foundation audit",
        "runtime boundary",
    ),
    "docs/FOUNDATION_AUDIT.md": (
        "axon foundation-audit",
        "inspection-only",
        "Phase 1 foundation",
    ),
}

DISABLED_RUNTIME_CAPABILITIES: tuple[str, ...] = (
    "method_execution",
    "provider_calls",
    "tool_dispatch",
    "memory_mutation",
    "rag_indexing",
    "rag_retrieval",
    "flow_execution",
    "trace_replay",
    "secret_resolution",
    "fastmcp_runtime_import",
)


@dataclass(frozen=True)
class FoundationAuditIssue:
    """One foundation audit issue or warning."""

    code: str
    message: str
    path: str | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }

    def format(self) -> str:
        location = f" {self.path}:" if self.path else ""
        return f"{self.severity}:{location} {self.code}: {self.message}"


@dataclass(frozen=True)
class FoundationAuditReport:
    """Inspection-only report for the Phase 1 foundation."""

    project_path: str
    areas: tuple[str, ...] = FOUNDATION_AREAS
    source_modules_checked: int = 0
    docs_checked: int = 0
    examples_checked: int = 0
    test_files_checked: int = 0
    ast_snapshot_count: int = 0
    formatted_snapshot_count: int = 0
    runtime_plan_snapshot_count: int = 0
    golden_error_count: int = 0
    issues: list[FoundationAuditIssue] = field(default_factory=list)
    non_execution_guarantee: str = NON_EXECUTION_GUARANTEE

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "axon.foundation_audit.v1",
            "project_path": self.project_path,
            "passed": self.passed,
            "areas": list(self.areas),
            "summary": {
                "source_modules_checked": self.source_modules_checked,
                "docs_checked": self.docs_checked,
                "examples_checked": self.examples_checked,
                "test_files_checked": self.test_files_checked,
                "ast_snapshot_count": self.ast_snapshot_count,
                "formatted_snapshot_count": self.formatted_snapshot_count,
                "runtime_plan_snapshot_count": self.runtime_plan_snapshot_count,
                "golden_error_count": self.golden_error_count,
                "error_count": self.error_count,
                "warning_count": self.warning_count,
            },
            "disabled_runtime_capabilities": list(DISABLED_RUNTIME_CAPABILITIES),
            "issues": [issue.to_dict() for issue in self.issues],
            "non_execution_guarantee": self.non_execution_guarantee,
        }


def audit_foundation(path: str | Path = ".") -> FoundationAuditReport:
    """Audit the current non-executing Phase 1 compiler/tooling foundation."""
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"project path is not a directory: {root}")

    issues: list[FoundationAuditIssue] = []

    _check_required_paths(root, REQUIRED_SOURCE_MODULES, "missing_source_module", issues)
    _check_required_paths(root, REQUIRED_DOCS, "missing_documentation", issues)
    _check_required_paths(root, REQUIRED_SNAPSHOT_DIRS, "missing_snapshot_directory", issues)
    _check_required_paths(root, REQUIRED_EXAMPLES, "missing_example", issues)
    _check_required_paths(root, REQUIRED_TEST_FILES, "missing_test_file", issues)
    _check_doc_phrases(root, issues)
    _check_runtime_boundary_docs(root, issues)

    return FoundationAuditReport(
        project_path=str(root),
        source_modules_checked=len(REQUIRED_SOURCE_MODULES),
        docs_checked=len(REQUIRED_DOCS),
        examples_checked=len(REQUIRED_EXAMPLES),
        test_files_checked=len(REQUIRED_TEST_FILES),
        ast_snapshot_count=_count_files(root / "tests/snapshots/examples", "*.ast.json"),
        formatted_snapshot_count=_count_files(root / "tests/snapshots/formatted", "*.formatted.ax"),
        runtime_plan_snapshot_count=_count_files(root / "tests/snapshots/runtime_plan/examples", "*.runtime-plan.json"),
        golden_error_count=_count_files(root / "tests/golden_errors", "*.json"),
        issues=issues,
    )


def foundation_audit_to_json(report: FoundationAuditReport) -> str:
    """Serialize a foundation audit report as stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def format_foundation_audit_report(report: FoundationAuditReport) -> str:
    """Render a foundation audit report for humans."""
    lines = [
        "AXON Phase 1 foundation audit",
        f"Project: {report.project_path}",
        f"Status: {'passed' if report.passed else 'failed'}",
        f"Areas: {len(report.areas)}",
        f"Source modules checked: {report.source_modules_checked}",
        f"Docs checked: {report.docs_checked}",
        f"Examples checked: {report.examples_checked}",
        f"Test files checked: {report.test_files_checked}",
        f"AST snapshots: {report.ast_snapshot_count}",
        f"Formatted snapshots: {report.formatted_snapshot_count}",
        f"Runtime-plan snapshots: {report.runtime_plan_snapshot_count}",
        f"Golden error snapshots: {report.golden_error_count}",
        f"Errors: {report.error_count}",
        f"Warnings: {report.warning_count}",
        "",
        "Foundation areas:",
    ]
    lines.extend(f"  - {area}" for area in report.areas)
    lines.extend(["", "Disabled runtime capabilities:"])
    lines.extend(f"  - {capability}" for capability in DISABLED_RUNTIME_CAPABILITIES)

    if report.issues:
        lines.extend(["", "Issues:"])
        lines.extend(f"  - {issue.format()}" for issue in report.issues)
    else:
        lines.extend(["", "No foundation audit issues found."])

    lines.extend(["", "Non-execution guarantee:", f"  {report.non_execution_guarantee}"])
    return "\n".join(lines)


def _check_required_paths(
    root: Path,
    rel_paths: tuple[str, ...],
    code: str,
    issues: list[FoundationAuditIssue],
) -> None:
    for rel_path in rel_paths:
        if not (root / rel_path).exists():
            issues.append(
                FoundationAuditIssue(
                    code=code,
                    message=f"required Phase 1 foundation path is missing: {rel_path}",
                    path=rel_path,
                )
            )


def _check_doc_phrases(root: Path, issues: list[FoundationAuditIssue]) -> None:
    for rel_path, phrases in REQUIRED_DOC_PHRASES.items():
        path = root / rel_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                issues.append(
                    FoundationAuditIssue(
                        code="documentation_phrase_missing",
                        message=f"required phrase is missing: {phrase}",
                        path=rel_path,
                    )
                )


def _check_runtime_boundary_docs(root: Path, issues: list[FoundationAuditIssue]) -> None:
    boundary_docs = [
        "docs/RUNTIME_BOUNDARY.md",
        "docs/RUNTIME_PLAN.md",
        "docs/runtime-rfcs/0001-minimal-non-executing-runtime.md",
    ]
    for rel_path in boundary_docs:
        path = root / rel_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for capability in DISABLED_RUNTIME_CAPABILITIES:
            if capability not in text:
                issues.append(
                    FoundationAuditIssue(
                        code="runtime_boundary_capability_missing",
                        message=f"disabled runtime capability is not documented: {capability}",
                        path=rel_path,
                    )
                )
        if "declaration_inspection" not in text:
            issues.append(
                FoundationAuditIssue(
                    code="runtime_boundary_enabled_capability_missing",
                    message="enabled capability declaration_inspection is not documented",
                    path=rel_path,
                )
            )


def _count_files(path: Path, pattern: str) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for _ in path.glob(pattern))
