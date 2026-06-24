from __future__ import annotations

import json
from pathlib import Path

from axon.cli import main
from axon.release_artifact_consistency import (
    STANDARD_RELEASE_ARTIFACT_FILES,
    check_release_artifact_consistency,
    format_release_artifact_consistency_report,
    release_artifact_consistency_to_json,
)
from axon.release_bundle_manifest import RELEASE_HANDOFF_ARTIFACTS

ROOT = Path(__file__).resolve().parents[1]


def test_standard_release_artifacts_match_manifest_constant():
    manifest_artifacts = {path for path, _description in RELEASE_HANDOFF_ARTIFACTS}
    assert set(STANDARD_RELEASE_ARTIFACT_FILES) == manifest_artifacts


def test_release_artifact_consistency_passes_for_repository():
    report = check_release_artifact_consistency(ROOT)
    assert report.passed, [issue.format() for issue in report.issues]
    assert report.error_count == 0
    assert "release-artifacts.json" in report.artifact_files


def test_release_artifact_consistency_json_is_stable():
    report = check_release_artifact_consistency(ROOT)
    payload = json.loads(release_artifact_consistency_to_json(report))
    assert payload["schema"] == "axon.release_artifact_consistency.v1"
    assert payload["passed"] is True
    assert "api_key" not in json.dumps(payload).lower()


def test_release_artifact_consistency_format_mentions_boundary():
    text = format_release_artifact_consistency_report(check_release_artifact_consistency(ROOT))
    assert "AXON release artifact consistency check" in text
    assert "Non-execution guarantee" in text
    assert "release-bundle-manifest.json" in text


def test_release_artifacts_check_cli_outputs_human_report(capsys):
    code = main(["release-artifacts-check", str(ROOT)])
    captured = capsys.readouterr()
    assert code == 0
    assert "AXON release artifact consistency check" in captured.out


def test_release_artifacts_check_cli_outputs_json(capsys):
    code = main(["release-artifacts-check", str(ROOT), "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["passed"] is True


def test_release_artifact_consistency_alias(capsys):
    code = main(["release-artifact-consistency", str(ROOT)])
    captured = capsys.readouterr()
    assert code == 0
    assert "Status: passed" in captured.out
