"""Runtime governance evidence file helpers for AXON projects.

This module writes stable, secret-safe governance evidence artifacts. It wraps
``axon.runtime_governance`` and deliberately remains inspection-only: it never
executes AXON agents, calls providers, dispatches tools, resolves secrets,
imports FastMCP, mutates memory, indexes RAG data, executes flows, or replays
traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Literal

from axon import __version__
from axon.runtime_governance import (
    NON_EXECUTION_GUARANTEE,
    RuntimeGovernanceReport,
    check_runtime_governance,
)

EvidenceFormat = Literal["json", "markdown"]


@dataclass(frozen=True)
class RuntimeGovernanceEvidence:
    """Stable evidence artifact for runtime-governance review and release handoff."""

    schema: str
    axon_version: str
    evidence_kind: str
    project_path: str
    passed: bool
    non_execution_guarantee: str
    report: RuntimeGovernanceReport
    recommended_artifacts: list[str] = field(default_factory=list)
    recommended_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "axon_version": self.axon_version,
            "evidence_kind": self.evidence_kind,
            "project_path": self.project_path,
            "passed": self.passed,
            "non_execution_guarantee": self.non_execution_guarantee,
            "recommended_artifacts": list(self.recommended_artifacts),
            "recommended_commands": list(self.recommended_commands),
            "report": self.report.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize evidence to stable JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        """Render evidence as Markdown for release handoff bundles."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            "# AXON Runtime Governance Evidence",
            "",
            f"- Schema: `{self.schema}`",
            f"- AXON version: `{self.axon_version}`",
            f"- Evidence kind: `{self.evidence_kind}`",
            f"- Project: `{self.project_path}`",
            f"- Status: **{status}**",
            f"- Boundary: {self.non_execution_guarantee}",
            "",
            "## Governance Steps",
            "",
        ]
        for step in self.report.steps:
            mark = "OK" if step.passed else "FAIL"
            lines.extend(
                [
                    f"### {step.name}",
                    "",
                    f"- Status: `{mark}`",
                    f"- Command: `{step.command}`",
                    f"- Message: {step.message}",
                    "",
                ]
            )
        lines.extend(
            [
                "## Required Evidence Commands",
                "",
                *[f"- `{command}`" for command in self.recommended_commands],
                "",
                "## Recommended Artifact Files",
                "",
                *[f"- `{artifact}`" for artifact in self.recommended_artifacts],
                "",
                "## Non-Execution Guarantee",
                "",
                self.non_execution_guarantee,
                "",
            ]
        )
        return "\n".join(lines)


DEFAULT_RECOMMENDED_ARTIFACTS = [
    "runtime-governance.json",
    "runtime-plan-review.md",
    "runtime-plan-corpus.json",
    "dependency-audit.json",
    "hygiene.json",
]


def build_runtime_governance_evidence(
    project_path: str | Path = ".",
    *,
    examples_dir: str | Path = "examples",
    snapshot_dir: str | Path = "tests/snapshots/runtime_plan/examples",
    skip_corpus: bool = False,
) -> RuntimeGovernanceEvidence:
    """Build a stable, non-executing runtime-governance evidence artifact."""
    report = check_runtime_governance(
        project_path,
        examples_dir=examples_dir,
        snapshot_dir=snapshot_dir,
        skip_corpus=skip_corpus,
    )
    return RuntimeGovernanceEvidence(
        schema="axon.runtime_governance_evidence.v1",
        axon_version=__version__,
        evidence_kind="runtime-governance",
        project_path=report.project_path,
        passed=report.passed,
        non_execution_guarantee=NON_EXECUTION_GUARANTEE,
        report=report,
        recommended_artifacts=list(DEFAULT_RECOMMENDED_ARTIFACTS),
        recommended_commands=list(report.required_commands),
    )


def runtime_governance_evidence_to_json(evidence: RuntimeGovernanceEvidence) -> str:
    """Serialize runtime-governance evidence to stable JSON."""
    return evidence.to_json()


def format_runtime_governance_evidence(evidence: RuntimeGovernanceEvidence) -> str:
    """Render runtime-governance evidence as Markdown."""
    return evidence.to_markdown()


def write_runtime_governance_evidence(
    output_path: str | Path,
    evidence: RuntimeGovernanceEvidence,
    *,
    format: EvidenceFormat | None = None,
) -> Path:
    """Write evidence to JSON or Markdown.

    If ``format`` is omitted, ``.json`` selects JSON; every other suffix selects
    Markdown. Parent directories are created automatically.
    """
    destination = Path(output_path)
    chosen_format: EvidenceFormat
    if format is None:
        chosen_format = "json" if destination.suffix.lower() == ".json" else "markdown"
    else:
        chosen_format = format

    destination.parent.mkdir(parents=True, exist_ok=True)
    content = evidence.to_json() if chosen_format == "json" else evidence.to_markdown()
    destination.write_text(content, encoding="utf-8")
    return destination
