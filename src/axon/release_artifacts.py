"""Release artifact writer for AXON handoff bundles.

This module writes the standard inspection-only release handoff artifacts into a
chosen output directory. It deliberately does not execute AXON agents, call
providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index
RAG data, execute flows, or replay traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
from typing import Any, Iterable

from axon import __version__
from axon.dependency_audit import audit_dependencies
from axon.handoff import build_handoff_checklist, handoff_checklist_to_json, write_handoff_checklist
from axon.hygiene import audit_hygiene
from axon.release_artifact_consistency import (
    check_release_artifact_consistency,
    release_artifact_consistency_to_json,
)
from axon.release_bundle_manifest import build_release_bundle_manifest, write_release_bundle_manifest
from axon.release_notes import build_release_notes, write_release_notes
from axon.runtime_governance_evidence import build_runtime_governance_evidence, write_runtime_governance_evidence
from axon.runtime_plan_corpus import check_runtime_plan_corpus, runtime_plan_corpus_report_to_json


NON_EXECUTION_GUARANTEE = (
    "release artifact generation is inspection-only: it does not execute AXON agents, "
    "call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, "
    "index RAG data, execute flows, or replay traces"
)


@dataclass(frozen=True)
class ReleaseArtifact:
    """One artifact written into a release handoff output directory."""

    name: str
    path: str
    kind: str
    description: str
    written: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "kind": self.kind,
            "description": self.description,
            "written": self.written,
        }


@dataclass(frozen=True)
class ReleaseArtifactBundle:
    """Report for a generated AXON release artifact directory."""

    project_path: str
    output_dir: str
    axon_version: str
    passed: bool
    non_execution_guarantee: str = NON_EXECUTION_GUARANTEE
    artifacts: list[ReleaseArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "axon.release_artifacts.v1",
            "project_path": self.project_path,
            "output_dir": self.output_dir,
            "axon_version": self.axon_version,
            "passed": self.passed,
            "artifact_count": self.artifact_count,
            "non_execution_guarantee": self.non_execution_guarantee,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": list(self.warnings),
        }


def write_release_artifacts(
    project_path: str | Path = ".",
    *,
    output_dir: str | Path = "release-artifacts",
    version: str | None = None,
    release_date: str | None = None,
    changes: Iterable[str] | None = None,
    tests: Iterable[str] | None = None,
    skip_corpus: bool = False,
) -> ReleaseArtifactBundle:
    """Write standard AXON handoff artifacts into ``output_dir``.

    The writer creates deterministic release evidence files using existing safe
    AXON inspection utilities. It does not execute generated servers or AXON
    method bodies, and it does not resolve provider secrets.
    """
    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"project path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"project path is not a directory: {root}")

    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    artifacts: list[ReleaseArtifact] = []
    warnings: list[str] = []

    def record(name: str, path: Path, kind: str, description: str) -> None:
        artifacts.append(
            ReleaseArtifact(
                name=name,
                path=str(path),
                kind=kind,
                description=description,
                written=path.exists(),
            )
        )

    # Handoff checklist.
    handoff = build_handoff_checklist(root, full=not skip_corpus)
    handoff_md = write_handoff_checklist(out / "HANDOFF_CHECKLIST.md", handoff, json_output=False)
    handoff_json = out / "handoff-checklist.json"
    handoff_json.write_text(handoff_checklist_to_json(handoff) + "\n", encoding="utf-8")
    record("handoff-checklist", handoff_md, "markdown", "release handoff checklist")
    record("handoff-checklist-json", handoff_json, "json", "machine-readable release handoff checklist")

    # Release notes.
    notes = build_release_notes(
        version=version,
        release_date=release_date,
        project_path=root,
        changes=changes,
        tests=tests,
    )
    notes_md = write_release_notes(out / "RELEASE_NOTES.md", notes, json_output=False)
    notes_json = write_release_notes(out / "release-notes.json", notes, json_output=True)
    record("release-notes", notes_md, "markdown", "release notes with explicit changes and validation evidence")
    record("release-notes-json", notes_json, "json", "machine-readable release notes")

    # Runtime governance evidence.
    governance = build_runtime_governance_evidence(root, skip_corpus=skip_corpus)
    governance_json = write_runtime_governance_evidence(out / "runtime-governance.json", governance, format="json")
    governance_md = write_runtime_governance_evidence(
        out / "RUNTIME_GOVERNANCE_EVIDENCE.md", governance, format="markdown"
    )
    record("runtime-governance", governance_json, "json", "runtime governance evidence")
    record("runtime-governance-markdown", governance_md, "markdown", "reviewer-friendly runtime governance evidence")
    if not governance.passed:
        warnings.append("runtime governance evidence did not pass")

    # Runtime-plan corpus evidence.
    corpus = check_runtime_plan_corpus(root, require_snapshots=True)
    corpus_json = out / "runtime-plan-corpus.json"
    corpus_json.write_text(runtime_plan_corpus_report_to_json(corpus) + "\n", encoding="utf-8")
    record("runtime-plan-corpus", corpus_json, "json", "runtime-plan corpus evidence")
    if not corpus.passed:
        warnings.append("runtime-plan corpus check did not pass")

    # Dependency and hygiene evidence.
    dependency = audit_dependencies(root)
    dependency_json = out / "dependency-audit.json"
    dependency_json.write_text(dependency.to_json() + "\n", encoding="utf-8")
    record("dependency-audit", dependency_json, "json", "dependency boundary audit evidence")
    if not dependency.passed:
        warnings.append("dependency audit did not pass")

    hygiene = audit_hygiene(root)
    hygiene_json = out / "hygiene.json"
    hygiene_json.write_text(json.dumps(hygiene.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record("hygiene", hygiene_json, "json", "repository hygiene audit evidence")
    if not hygiene.passed:
        warnings.append("repository hygiene audit did not pass")

    # Release bundle manifest. It inventories the project and expected artifacts.
    manifest = build_release_bundle_manifest(root)
    manifest_json = write_release_bundle_manifest(out / "release-bundle-manifest.json", manifest, format="json")
    manifest_md = write_release_bundle_manifest(out / "RELEASE_BUNDLE_MANIFEST.md", manifest, format="markdown")
    record("release-bundle-manifest", manifest_json, "json", "release bundle manifest")
    record("release-bundle-manifest-markdown", manifest_md, "markdown", "reviewer-friendly release bundle manifest")
    if not manifest.passed:
        warnings.append("release bundle manifest has missing required source artifacts")

    # Release artifact consistency evidence.
    consistency = check_release_artifact_consistency(root)
    consistency_json = out / "release-artifact-consistency.json"
    consistency_json.write_text(release_artifact_consistency_to_json(consistency) + "\n", encoding="utf-8")
    record("release-artifact-consistency", consistency_json, "json", "release artifact name consistency evidence")
    if not consistency.passed:
        warnings.append("release artifact consistency check did not pass")

    # Self-report. Register first so the on-disk JSON includes itself.
    self_report = out / "release-artifacts.json"
    artifacts.append(
        ReleaseArtifact(
            name="release-artifacts",
            path=str(self_report),
            kind="json",
            description="machine-readable release artifact writer report",
            written=True,
        )
    )
    bundle = ReleaseArtifactBundle(
        project_path=str(root),
        output_dir=str(out),
        axon_version=__version__,
        passed=not warnings,
        artifacts=artifacts,
        warnings=warnings,
    )
    self_report.write_text(release_artifact_bundle_to_json(bundle) + "\n", encoding="utf-8")

    return bundle


def release_artifact_bundle_to_json(bundle: ReleaseArtifactBundle) -> str:
    """Serialize release artifact writer output as stable JSON."""
    return json.dumps(bundle.to_dict(), indent=2, sort_keys=True)


def format_release_artifact_bundle(bundle: ReleaseArtifactBundle) -> str:
    """Render release artifact writer output for humans."""
    lines = [
        "AXON release artifacts",
        f"Project: {bundle.project_path}",
        f"Output directory: {bundle.output_dir}",
        f"AXON version: {bundle.axon_version}",
        f"Status: {'passed' if bundle.passed else 'warnings'}",
        f"Artifacts written: {bundle.artifact_count}",
        "",
        "Artifacts:",
    ]
    for artifact in bundle.artifacts:
        marker = "ok" if artifact.written else "missing"
        lines.append(f"  - {artifact.name}: {artifact.path} [{artifact.kind}, {marker}]")
    if bundle.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - {warning}" for warning in bundle.warnings)
    lines.extend(["", "Non-execution guarantee:", f"  {bundle.non_execution_guarantee}"])
    return "\n".join(lines)
