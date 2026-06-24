"""Consistency checks for runtime-plan review governance.

This module keeps the runtime-plan reviewer checklist aligned with the
runtime-plan documentation, Runtime RFC #001, runtime-boundary documentation,
and corpus validation workflow. It is deliberately inspection-only: it reads
project files and optionally runs the existing non-executing runtime-plan corpus
check, but it never executes AXON agents or runtime capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from axon.runtime_plan import default_runtime_capabilities
from axon.runtime_plan_corpus import check_runtime_plan_corpus
from axon.runtime_plan_review import build_runtime_plan_review_checklist

DEFAULT_ENCODING = "utf-8"

REVIEW_DOC = Path("docs/RUNTIME_PLAN_REVIEW.md")
RUNTIME_PLAN_DOC = Path("docs/RUNTIME_PLAN.md")
RUNTIME_BOUNDARY_DOC = Path("docs/RUNTIME_BOUNDARY.md")
RUNTIME_RFC_001 = Path("docs/runtime-rfcs/0001-minimal-non-executing-runtime.md")
CLI_REFERENCE_DOC = Path("docs/CLI_REFERENCE.md")
README_DOC = Path("README.md")
HANDOFF_DOC = Path("docs/HANDOFF.md")
ROADMAP_DOC = Path("docs/ROADMAP.md")

REQUIRED_DOCS = [
    REVIEW_DOC,
    RUNTIME_PLAN_DOC,
    RUNTIME_BOUNDARY_DOC,
    RUNTIME_RFC_001,
    CLI_REFERENCE_DOC,
    README_DOC,
    HANDOFF_DOC,
    ROADMAP_DOC,
]

RUNTIME_PLAN_REVIEW_COMMAND = "axon runtime-plan-review"
RUNTIME_PLAN_CORPUS_COMMAND = "axon runtime-plan-corpus ."
RUNTIME_PLAN_SNAPSHOT_COMMAND_FRAGMENT = "axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root ."
CHECK_PROJECT_COMMAND = "axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke"


def enabled_runtime_capabilities() -> list[str]:
    """Return capability names currently enabled by Runtime RFC #001."""
    return [capability.name for capability in default_runtime_capabilities() if capability.enabled]


def disabled_runtime_capabilities() -> list[str]:
    """Return capability names currently disabled by Runtime RFC #001."""
    return [capability.name for capability in default_runtime_capabilities() if not capability.enabled]


@dataclass(frozen=True)
class ReviewConsistencyCheck:
    """One runtime-plan review consistency check result."""

    name: str
    passed: bool
    message: str
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "location": self.location,
        }


@dataclass(frozen=True)
class RuntimePlanReviewConsistencyReport:
    """Complete report for runtime-plan review/docs/corpus consistency."""

    project_path: str
    passed: bool
    checks: list[ReviewConsistencyCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for check in self.checks if check.passed),
                "failed": sum(1 for check in self.checks if not check.passed),
            },
        }

    def format(self) -> str:
        status = "passed" if self.passed else "failed"
        lines = [f"AXON runtime-plan review consistency: {status}", f"Project: {self.project_path}", ""]
        for check in self.checks:
            mark = "OK" if check.passed else "FAIL"
            location = f" ({check.location})" if check.location else ""
            lines.append(f"[{mark}] {check.name}{location}: {check.message}")
        return "\n".join(lines)


def check_runtime_plan_review_consistency(
    project_path: str | Path = ".",
    *,
    examples_dir: str | Path = "examples",
    snapshot_dir: str | Path = "tests/snapshots/runtime_plan/examples",
    skip_corpus: bool = False,
) -> RuntimePlanReviewConsistencyReport:
    """Check runtime-plan reviewer checklist/docs/corpus alignment.

    The check is non-executing. It reads project documentation, builds the
    generated reviewer checklist, and optionally runs the existing runtime-plan
    corpus inspection gate.
    """
    root = Path(project_path).expanduser().resolve()
    checks: list[ReviewConsistencyCheck] = []

    docs = _read_required_docs(root, checks)
    checklist = build_runtime_plan_review_checklist()
    checklist_text = json.dumps(checklist.to_dict(), sort_keys=True) + "\n" + _format_checklist_text(checklist)

    _check_generated_checklist_capabilities(checks, checklist_text)
    _check_docs_mention_capabilities(checks, docs)
    _check_required_commands(checks, docs, checklist.required_commands)
    _check_command_documentation(checks, docs)
    _check_rfc_alignment(checks, docs)
    _check_no_execution_claims(checks, docs)

    if skip_corpus:
        checks.append(
            ReviewConsistencyCheck(
                name="runtime-plan-corpus",
                passed=True,
                message="skipped by caller; documentation and checklist alignment still checked",
            )
        )
    else:
        corpus_report = check_runtime_plan_corpus(
            root,
            examples_dir=examples_dir,
            snapshot_dir=snapshot_dir,
            require_snapshots=True,
        )
        checks.append(
            ReviewConsistencyCheck(
                name="runtime-plan-corpus",
                passed=corpus_report.passed,
                message=f"runtime-plan corpus {'passed' if corpus_report.passed else 'failed'} for {corpus_report.total_sources} source(s)",
                location=str(Path(snapshot_dir)),
            )
        )

    passed = all(check.passed for check in checks)
    return RuntimePlanReviewConsistencyReport(project_path=str(root), passed=passed, checks=checks)


def runtime_plan_review_consistency_report_to_json(report: RuntimePlanReviewConsistencyReport) -> str:
    """Serialize a runtime-plan review consistency report to stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def format_runtime_plan_review_consistency_report(report: RuntimePlanReviewConsistencyReport) -> str:
    """Render a runtime-plan review consistency report for humans."""
    return report.format()


def _read_required_docs(root: Path, checks: list[ReviewConsistencyCheck]) -> dict[Path, str]:
    docs: dict[Path, str] = {}
    for relative in REQUIRED_DOCS:
        path = root / relative
        if path.exists() and path.is_file():
            docs[relative] = path.read_text(encoding=DEFAULT_ENCODING)
            checks.append(
                ReviewConsistencyCheck(
                    name="doc-exists",
                    passed=True,
                    message="documentation file exists",
                    location=str(relative),
                )
            )
        else:
            checks.append(
                ReviewConsistencyCheck(
                    name="doc-exists",
                    passed=False,
                    message="required documentation file is missing",
                    location=str(relative),
                )
            )
    return docs


def _format_checklist_text(checklist: Any) -> str:
    # Avoid importing the formatter at module import time in tests that inspect
    # minimal dependencies; this helper keeps it local and explicit.
    from axon.runtime_plan_review import format_runtime_plan_review_checklist

    return format_runtime_plan_review_checklist(checklist)


def _check_generated_checklist_capabilities(checks: list[ReviewConsistencyCheck], checklist_text: str) -> None:
    for capability in enabled_runtime_capabilities():
        checks.append(
            ReviewConsistencyCheck(
                name="checklist-enabled-capability",
                passed=capability in checklist_text,
                message=f"generated checklist mentions enabled capability {capability}",
            )
        )
    for capability in disabled_runtime_capabilities():
        checks.append(
            ReviewConsistencyCheck(
                name="checklist-disabled-capability",
                passed=capability in checklist_text,
                message=f"generated checklist mentions disabled capability {capability}",
            )
        )


def _check_docs_mention_capabilities(checks: list[ReviewConsistencyCheck], docs: dict[Path, str]) -> None:
    capability_docs = [REVIEW_DOC, RUNTIME_PLAN_DOC, RUNTIME_BOUNDARY_DOC, RUNTIME_RFC_001]
    for doc in capability_docs:
        text = docs.get(doc, "")
        for capability in enabled_runtime_capabilities():
            checks.append(
                ReviewConsistencyCheck(
                    name="doc-enabled-capability",
                    passed=capability in text,
                    message=f"{doc} mentions enabled capability {capability}",
                    location=str(doc),
                )
            )
        for capability in disabled_runtime_capabilities():
            checks.append(
                ReviewConsistencyCheck(
                    name="doc-disabled-capability",
                    passed=capability in text,
                    message=f"{doc} mentions disabled capability {capability}",
                    location=str(doc),
                )
            )


def _check_required_commands(checks: list[ReviewConsistencyCheck], docs: dict[Path, str], required_commands: list[str]) -> None:
    review_doc = docs.get(REVIEW_DOC, "")
    runtime_plan_doc = docs.get(RUNTIME_PLAN_DOC, "")
    boundary_doc = docs.get(RUNTIME_BOUNDARY_DOC, "")
    handoff_doc = docs.get(HANDOFF_DOC, "")

    for command in required_commands:
        checks.append(
            ReviewConsistencyCheck(
                name="review-doc-required-command",
                passed=command in review_doc,
                message=f"review doc includes required command: {command}",
                location=str(REVIEW_DOC),
            )
        )

    for doc, text, command in [
        (RUNTIME_PLAN_DOC, runtime_plan_doc, RUNTIME_PLAN_CORPUS_COMMAND),
        (RUNTIME_BOUNDARY_DOC, boundary_doc, RUNTIME_PLAN_CORPUS_COMMAND),
        (HANDOFF_DOC, handoff_doc, RUNTIME_PLAN_CORPUS_COMMAND),
        (RUNTIME_PLAN_DOC, runtime_plan_doc, RUNTIME_PLAN_REVIEW_COMMAND),
        (HANDOFF_DOC, handoff_doc, RUNTIME_PLAN_REVIEW_COMMAND),
    ]:
        checks.append(
            ReviewConsistencyCheck(
                name="workflow-command-alignment",
                passed=command in text,
                message=f"{doc} includes workflow command: {command}",
                location=str(doc),
            )
        )

    checks.append(
        ReviewConsistencyCheck(
            name="snapshot-command-alignment",
            passed=RUNTIME_PLAN_SNAPSHOT_COMMAND_FRAGMENT in review_doc,
            message="review doc includes canonical runtime-plan snapshot check command",
            location=str(REVIEW_DOC),
        )
    )
    checks.append(
        ReviewConsistencyCheck(
            name="project-command-alignment",
            passed=CHECK_PROJECT_COMMAND in review_doc,
            message="review doc includes canonical check-project command",
            location=str(REVIEW_DOC),
        )
    )


def _check_command_documentation(checks: list[ReviewConsistencyCheck], docs: dict[Path, str]) -> None:
    for doc in [README_DOC, CLI_REFERENCE_DOC, RUNTIME_PLAN_DOC, REVIEW_DOC]:
        text = docs.get(doc, "")
        for command in ["axon runtime-plan-review", "axon runtime-plan-corpus"]:
            checks.append(
                ReviewConsistencyCheck(
                    name="command-documented",
                    passed=command in text,
                    message=f"{doc} documents {command}",
                    location=str(doc),
                )
            )


def _check_rfc_alignment(checks: list[ReviewConsistencyCheck], docs: dict[Path, str]) -> None:
    rfc = docs.get(RUNTIME_RFC_001, "")
    boundary = docs.get(RUNTIME_BOUNDARY_DOC, "")
    review = docs.get(REVIEW_DOC, "")
    for phrase in [
        "Minimal Non-Executing Runtime",
        "non-executing",
        "declaration_inspection",
        "Runtime RFC",
    ]:
        checks.append(
            ReviewConsistencyCheck(
                name="rfc-review-boundary-alignment",
                passed=phrase in rfc and phrase in boundary and phrase in review,
                message=f"RFC, boundary doc, and review doc all mention {phrase!r}",
            )
        )


def _check_no_execution_claims(checks: list[ReviewConsistencyCheck], docs: dict[Path, str]) -> None:
    # These exact phrases would contradict the currently accepted boundary. The
    # check is intentionally narrow to avoid blocking legitimate discussion like
    # "must not execute".
    forbidden_fragments = [
        "method_execution: enabled",
        "provider_calls: enabled",
        "tool_dispatch: enabled",
        "memory_mutation: enabled",
        "rag_indexing: enabled",
        "rag_retrieval: enabled",
        "flow_execution: enabled",
        "trace_replay: enabled",
        "secret_resolution: enabled",
        "fastmcp_runtime_import: enabled",
    ]
    searchable = "\n".join(docs.values())
    for fragment in forbidden_fragments:
        checks.append(
            ReviewConsistencyCheck(
                name="no-execution-capability-enabled-claim",
                passed=fragment not in searchable,
                message=f"documentation does not claim {fragment}",
            )
        )
