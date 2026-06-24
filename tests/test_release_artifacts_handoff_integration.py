from __future__ import annotations

import json
from pathlib import Path

from axon.handoff import build_handoff_checklist, format_handoff_checklist
from axon.release_artifact_consistency import (
    STANDARD_RELEASE_ARTIFACT_FILES,
    check_release_artifact_consistency,
)
from axon.release_artifacts import write_release_artifacts
from axon.release_bundle_manifest import RELEASE_HANDOFF_ARTIFACTS, format_release_bundle_manifest, build_release_bundle_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_release_artifact_consistency_evidence_is_standard_artifact():
    assert "release-artifact-consistency.json" in STANDARD_RELEASE_ARTIFACT_FILES
    assert "release-artifact-consistency.json" in {path for path, _ in RELEASE_HANDOFF_ARTIFACTS}


def test_release_artifacts_writer_outputs_consistency_evidence(tmp_path: Path):
    out = tmp_path / "release"
    bundle = write_release_artifacts(ROOT, output_dir=out, skip_corpus=True)

    evidence_path = out / "release-artifact-consistency.json"
    assert evidence_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "axon.release_artifact_consistency.v1"
    assert payload["passed"] is True
    assert "release-artifact-consistency.json" in payload["artifact_files"]
    assert any(artifact.name == "release-artifact-consistency" for artifact in bundle.artifacts)


def test_handoff_includes_release_artifact_consistency_command():
    checklist = build_handoff_checklist(ROOT)
    shells = [command.shell for command in checklist.commands]

    assert any(shell.startswith("axon release-artifacts-check") for shell in shells)
    assert "release-artifact-consistency.json" in format_handoff_checklist(checklist)


def test_release_bundle_manifest_mentions_consistency_artifact():
    manifest = build_release_bundle_manifest(ROOT)
    text = format_release_bundle_manifest(manifest)

    assert "release-artifact-consistency.json" in text
    assert "axon release-artifacts-check . --json > release-artifact-consistency.json" in text


def test_release_artifact_consistency_check_passes_after_handoff_integration():
    report = check_release_artifact_consistency(ROOT)
    assert report.passed, [issue.format() for issue in report.issues]
    assert "release-artifact-consistency.json" in report.artifact_files
