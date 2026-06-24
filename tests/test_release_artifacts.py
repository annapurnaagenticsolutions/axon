from __future__ import annotations

import json
from pathlib import Path

from axon.release_artifacts import (
    NON_EXECUTION_GUARANTEE,
    format_release_artifact_bundle,
    release_artifact_bundle_to_json,
    write_release_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]


def test_write_release_artifacts_creates_standard_files(tmp_path: Path):
    out = tmp_path / "release"
    bundle = write_release_artifacts(
        ROOT,
        output_dir=out,
        version="0.1.0-test",
        release_date="2026-06-01",
        changes=["completed Task #51"],
        tests=["targeted tests passed"],
        skip_corpus=True,
    )

    assert bundle.output_dir == str(out.resolve())
    assert bundle.artifact_count >= 10
    assert (out / "HANDOFF_CHECKLIST.md").exists()
    assert (out / "handoff-checklist.json").exists()
    assert (out / "RELEASE_NOTES.md").exists()
    assert (out / "release-notes.json").exists()
    assert (out / "runtime-governance.json").exists()
    assert (out / "RUNTIME_GOVERNANCE_EVIDENCE.md").exists()
    assert (out / "runtime-plan-corpus.json").exists()
    assert (out / "dependency-audit.json").exists()
    assert (out / "hygiene.json").exists()
    assert (out / "release-bundle-manifest.json").exists()
    assert (out / "RELEASE_BUNDLE_MANIFEST.md").exists()
    assert (out / "release-artifacts.json").exists()


def test_release_artifact_json_is_stable_and_secret_safe(tmp_path: Path):
    bundle = write_release_artifacts(ROOT, output_dir=tmp_path / "release", skip_corpus=True)
    payload = json.loads(release_artifact_bundle_to_json(bundle))

    assert payload["schema"] == "axon.release_artifacts.v1"
    assert payload["non_execution_guarantee"] == NON_EXECUTION_GUARANTEE
    assert "api_key" not in json.dumps(payload).lower()
    assert "call providers" in payload["non_execution_guarantee"]


def test_release_artifact_self_report_matches_returned_bundle(tmp_path: Path):
    out = tmp_path / "release"
    bundle = write_release_artifacts(ROOT, output_dir=out, skip_corpus=True)
    on_disk = json.loads((out / "release-artifacts.json").read_text(encoding="utf-8"))

    assert on_disk["artifact_count"] == bundle.artifact_count
    assert any(artifact["name"] == "release-artifacts" for artifact in on_disk["artifacts"])


def test_format_release_artifact_bundle_mentions_output_and_guarantee(tmp_path: Path):
    bundle = write_release_artifacts(ROOT, output_dir=tmp_path / "release", skip_corpus=True)
    text = format_release_artifact_bundle(bundle)

    assert "AXON release artifacts" in text
    assert "Artifacts written:" in text
    assert "Non-execution guarantee" in text
    assert "release-artifacts.json" in text


def test_release_artifacts_cli_writes_directory(tmp_path: Path):
    from axon.cli import main

    out = tmp_path / "bundle"
    code = main([
        "release-artifacts",
        str(ROOT),
        "--output-dir",
        str(out),
        "--version",
        "0.1.0-test",
        "--date",
        "2026-06-01",
        "--change",
        "completed Task #51",
        "--tests",
        "targeted tests passed",
        "--skip-corpus",
    ])

    assert code == 0
    assert (out / "release-artifacts.json").exists()
    assert (out / "RELEASE_NOTES.md").exists()


def test_release_artifacts_cli_json_output(tmp_path: Path, capsys):
    from axon.cli import main

    out = tmp_path / "bundle"
    code = main(["release-artifacts", str(ROOT), "--output-dir", str(out), "--skip-corpus", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["schema"] == "axon.release_artifacts.v1"
    assert payload["output_dir"] == str(out.resolve())
