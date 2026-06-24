"""Runtime governance quality gate for AXON projects.

This module combines the existing non-executing runtime governance checks into
one release-evidence workflow. It deliberately calls inspection-only helpers: it
never executes AXON agents, calls providers, dispatches tools, resolves secrets,
imports FastMCP, mutates memory, indexes RAG data, executes flows, or replays
traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from axon.dependency_audit import audit_dependencies
from axon.hygiene import audit_hygiene
from axon.runtime_plan_corpus import check_runtime_plan_corpus
from axon.runtime_plan_review import build_runtime_plan_review_checklist
from axon.runtime_plan_review_consistency import check_runtime_plan_review_consistency

DEFAULT_RUNTIME_GOVERNANCE_COMMANDS = [
    "axon runtime-plan-review",
    "axon runtime-plan-review-check .",
    "axon runtime-plan-corpus .",
    "axon deps .",
    "axon hygiene .",
]

NON_EXECUTION_GUARANTEE = (
    "inspection-only: does not execute AXON agents, call providers, dispatch tools, "
    "resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, "
    "or replay traces"
)


@dataclass(frozen=True)
class RuntimeGovernanceStep:
    """One step in the runtime-governance quality gate."""

    name: str
    command: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "passed": self.passed,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class RuntimeGovernanceReport:
    """Combined runtime-governance quality gate report."""

    project_path: str
    passed: bool
    non_execution_guarantee: str
    steps: list[RuntimeGovernanceStep] = field(default_factory=list)
    required_commands: list[str] = field(default_factory=lambda: list(DEFAULT_RUNTIME_GOVERNANCE_COMMANDS))

    @property
    def failed_steps(self) -> list[RuntimeGovernanceStep]:
        return [step for step in self.steps if not step.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "passed": self.passed,
            "non_execution_guarantee": self.non_execution_guarantee,
            "required_commands": list(self.required_commands),
            "summary": {
                "total": len(self.steps),
                "passed": sum(1 for step in self.steps if step.passed),
                "failed": sum(1 for step in self.steps if not step.passed),
            },
            "steps": [step.to_dict() for step in self.steps],
        }

    def format(self) -> str:
        status = "passed" if self.passed else "failed"
        lines = [
            f"AXON runtime governance gate: {status}",
            f"Project: {self.project_path}",
            f"Boundary: {self.non_execution_guarantee}",
            "",
            "Steps:",
        ]
        for step in self.steps:
            mark = "OK" if step.passed else "FAIL"
            lines.append(f"  [{mark}] {step.name}: {step.message}")
            lines.append(f"       command: {step.command}")
        lines.append("")
        lines.append("Required evidence commands:")
        lines.extend(f"  - {command}" for command in self.required_commands)
        return "\n".join(lines)


def check_runtime_governance(
    project_path: str | Path = ".",
    *,
    examples_dir: str | Path = "examples",
    snapshot_dir: str | Path = "tests/snapshots/runtime_plan/examples",
    skip_corpus: bool = False,
) -> RuntimeGovernanceReport:
    """Run the inspection-only runtime-governance quality gate.

    The gate combines the reviewer checklist, review/docs consistency checks,
    runtime-plan corpus checks, dependency audit, and repository hygiene audit.
    """
    root = Path(project_path).expanduser().resolve()
    steps: list[RuntimeGovernanceStep] = []

    checklist = build_runtime_plan_review_checklist(change="runtime governance gate")
    checklist_passed = bool(checklist.sections) and bool(checklist.required_commands)
    steps.append(
        RuntimeGovernanceStep(
            name="runtime-plan-review",
            command="axon runtime-plan-review",
            passed=checklist_passed,
            message=(
                f"generated checklist with {len(checklist.sections)} section(s) "
                f"and {len(checklist.required_commands)} required command(s)"
            ),
            details=checklist.to_dict(),
        )
    )

    review_report = check_runtime_plan_review_consistency(
        root,
        examples_dir=examples_dir,
        snapshot_dir=snapshot_dir,
        skip_corpus=skip_corpus,
    )
    steps.append(
        RuntimeGovernanceStep(
            name="runtime-plan-review-check",
            command="axon runtime-plan-review-check ." + (" --skip-corpus" if skip_corpus else ""),
            passed=review_report.passed,
            message=(
                f"review/docs consistency {'passed' if review_report.passed else 'failed'} "
                f"with {sum(1 for check in review_report.checks if not check.passed)} failed check(s)"
            ),
            details=review_report.to_dict(),
        )
    )

    if skip_corpus:
        steps.append(
            RuntimeGovernanceStep(
                name="runtime-plan-corpus",
                command="axon runtime-plan-corpus .",
                passed=True,
                message="skipped by caller; use without --skip-corpus for release evidence",
                details={"skipped": True},
            )
        )
    else:
        corpus_report = check_runtime_plan_corpus(
            root,
            examples_dir=examples_dir,
            snapshot_dir=snapshot_dir,
            require_snapshots=True,
        )
        steps.append(
            RuntimeGovernanceStep(
                name="runtime-plan-corpus",
                command="axon runtime-plan-corpus .",
                passed=corpus_report.passed,
                message=(
                    f"runtime-plan corpus {'passed' if corpus_report.passed else 'failed'} "
                    f"for {corpus_report.total_sources} source(s)"
                ),
                details=corpus_report.to_dict(),
            )
        )

    dependency_report = audit_dependencies(root)
    steps.append(
        RuntimeGovernanceStep(
            name="deps",
            command="axon deps .",
            passed=dependency_report.passed,
            message=(
                f"dependency audit {'passed' if dependency_report.passed else 'failed'} "
                f"with {dependency_report.error_count} error(s) and {dependency_report.warning_count} warning(s)"
            ),
            details=dependency_report.to_dict(),
        )
    )

    hygiene_report = audit_hygiene(root)
    steps.append(
        RuntimeGovernanceStep(
            name="hygiene",
            command="axon hygiene .",
            passed=hygiene_report.passed,
            message=(
                f"repository hygiene {'passed' if hygiene_report.passed else 'failed'} "
                f"with {hygiene_report.error_count} error(s) and {hygiene_report.warning_count} warning(s)"
            ),
            details=hygiene_report.to_dict(),
        )
    )

    passed = all(step.passed for step in steps)
    return RuntimeGovernanceReport(
        project_path=str(root),
        passed=passed,
        non_execution_guarantee=NON_EXECUTION_GUARANTEE,
        steps=steps,
        required_commands=list(DEFAULT_RUNTIME_GOVERNANCE_COMMANDS),
    )


def runtime_governance_report_to_json(report: RuntimeGovernanceReport) -> str:
    """Serialize a runtime-governance report to stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def format_runtime_governance_report(report: RuntimeGovernanceReport) -> str:
    """Render a runtime-governance report for humans."""
    return report.format()
