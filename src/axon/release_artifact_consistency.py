"""Release artifact manifest consistency checks for AXON.

This module verifies that the standard release handoff artifact names stay
aligned across the artifact writer, release bundle manifest, handoff checklist,
and documentation. The check is inspection-only: it reads local source and docs
files, but it does not execute AXON agents, call providers, resolve secrets,
import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from axon.release_bundle_manifest import RELEASE_HANDOFF_ARTIFACTS


STANDARD_RELEASE_ARTIFACT_FILES: tuple[str, ...] = (
    "HANDOFF_CHECKLIST.md",
    "handoff-checklist.json",
    "RELEASE_NOTES.md",
    "release-notes.json",
    "runtime-governance.json",
    "RUNTIME_GOVERNANCE_EVIDENCE.md",
    "runtime-plan-corpus.json",
    "dependency-audit.json",
    "hygiene.json",
    "release-bundle-manifest.json",
    "RELEASE_BUNDLE_MANIFEST.md",
    "release-artifact-consistency.json",
    "release-artifacts.json",
)

REQUIRED_ARTIFACT_CONSISTENCY_FILES: tuple[str, ...] = (
    "src/axon/release_artifacts.py",
    "src/axon/release_bundle_manifest.py",
    "src/axon/handoff.py",
    "docs/RELEASE_ARTIFACTS.md",
    "docs/RELEASE_BUNDLE.md",
    "docs/HANDOFF.md",
    "docs/CLI_REFERENCE.md",
    "README.md",
)

NON_EXECUTION_GUARANTEE = (
    "release artifact consistency checks are inspection-only: they do not execute AXON agents, "
    "call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, "
    "index RAG data, execute flows, or replay traces"
)


@dataclass(frozen=True)
class ReleaseArtifactConsistencyIssue:
    """One release artifact consistency problem or warning."""

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
        prefix = self.severity
        location = f" {self.path}:" if self.path else ""
        return f"{prefix}:{location} {self.code}: {self.message}"


@dataclass(frozen=True)
class ReleaseArtifactConsistencyReport:
    """Report for release artifact name consistency."""

    project_path: str
    artifact_files: tuple[str, ...] = STANDARD_RELEASE_ARTIFACT_FILES
    checked_files: tuple[str, ...] = REQUIRED_ARTIFACT_CONSISTENCY_FILES
    issues: list[ReleaseArtifactConsistencyIssue] = field(default_factory=list)
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
            "schema": "axon.release_artifact_consistency.v1",
            "project_path": self.project_path,
            "passed": self.passed,
            "artifact_files": list(self.artifact_files),
            "checked_files": list(self.checked_files),
            "summary": {
                "artifact_count": len(self.artifact_files),
                "checked_file_count": len(self.checked_files),
                "error_count": self.error_count,
                "warning_count": self.warning_count,
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "non_execution_guarantee": self.non_execution_guarantee,
        }


def check_release_artifact_consistency(path: str | Path = ".") -> ReleaseArtifactConsistencyReport:
    """Check standard release artifact names across source and documentation."""
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"project path is not a directory: {root}")

    issues: list[ReleaseArtifactConsistencyIssue] = []

    # The release bundle manifest constant should include the full standard set.
    manifest_artifacts = {artifact_path for artifact_path, _description in RELEASE_HANDOFF_ARTIFACTS}
    expected_artifacts = set(STANDARD_RELEASE_ARTIFACT_FILES)
    missing_from_manifest = sorted(expected_artifacts - manifest_artifacts)
    extra_in_manifest = sorted(manifest_artifacts - expected_artifacts)
    for artifact in missing_from_manifest:
        issues.append(
            ReleaseArtifactConsistencyIssue(
                code="manifest_missing_artifact",
                message=f"release bundle manifest does not list standard artifact {artifact}",
                path="src/axon/release_bundle_manifest.py",
            )
        )
    for artifact in extra_in_manifest:
        issues.append(
            ReleaseArtifactConsistencyIssue(
                code="manifest_extra_artifact",
                message=f"release bundle manifest lists non-standard artifact {artifact}",
                path="src/axon/release_bundle_manifest.py",
                severity="warning",
            )
        )

    for rel_path in REQUIRED_ARTIFACT_CONSISTENCY_FILES:
        file_path = root / rel_path
        if not file_path.exists():
            issues.append(
                ReleaseArtifactConsistencyIssue(
                    code="missing_consistency_file",
                    message=f"required consistency surface is missing: {rel_path}",
                    path=rel_path,
                )
            )
            continue

        text = file_path.read_text(encoding="utf-8")
        required = _required_artifacts_for_file(rel_path)
        for artifact in required:
            if artifact not in text:
                issues.append(
                    ReleaseArtifactConsistencyIssue(
                        code="artifact_name_missing",
                        message=f"standard artifact {artifact} is not mentioned",
                        path=rel_path,
                    )
                )

    return ReleaseArtifactConsistencyReport(project_path=str(root), issues=issues)


def release_artifact_consistency_to_json(report: ReleaseArtifactConsistencyReport) -> str:
    """Serialize release artifact consistency report as stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def format_release_artifact_consistency_report(report: ReleaseArtifactConsistencyReport) -> str:
    """Render release artifact consistency report for humans."""
    lines = [
        "AXON release artifact consistency check",
        f"Project: {report.project_path}",
        f"Status: {'passed' if report.passed else 'failed'}",
        f"Standard artifacts: {len(report.artifact_files)}",
        f"Checked files: {len(report.checked_files)}",
        f"Errors: {report.error_count}",
        f"Warnings: {report.warning_count}",
        "",
        "Standard artifact files:",
    ]
    lines.extend(f"  - {artifact}" for artifact in report.artifact_files)

    if report.issues:
        lines.extend(["", "Issues:"])
        lines.extend(f"  - {issue.format()}" for issue in report.issues)
    else:
        lines.extend(["", "No release artifact consistency issues found."])

    lines.extend(["", "Non-execution guarantee:", f"  {report.non_execution_guarantee}"])
    return "\n".join(lines)


def _required_artifacts_for_file(rel_path: str) -> tuple[str, ...]:
    # Source and canonical release-artifact docs should mention the full set.
    if rel_path in {
        "src/axon/release_artifacts.py",
        "docs/RELEASE_ARTIFACTS.md",
        "docs/CLI_REFERENCE.md",
    }:
        return STANDARD_RELEASE_ARTIFACT_FILES

    # The manifest source and release-bundle docs should also carry the full set
    # so the expected artifact inventory matches the artifact writer.
    if rel_path in {"src/axon/release_bundle_manifest.py", "docs/RELEASE_BUNDLE.md"}:
        return STANDARD_RELEASE_ARTIFACT_FILES

    # Handoff and README are summary surfaces. Require the main human artifacts,
    # governance evidence, manifest artifacts, and artifact-writer self-report.
    if rel_path in {"src/axon/handoff.py", "docs/HANDOFF.md", "README.md"}:
        return (
            "HANDOFF_CHECKLIST.md",
            "RELEASE_NOTES.md",
            "runtime-governance.json",
            "RUNTIME_GOVERNANCE_EVIDENCE.md",
            "release-bundle-manifest.json",
            "RELEASE_BUNDLE_MANIFEST.md",
            "release-artifacts.json",
        )

    return STANDARD_RELEASE_ARTIFACT_FILES
