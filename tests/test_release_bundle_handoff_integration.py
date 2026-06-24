from __future__ import annotations

import json
from pathlib import Path

from axon.handoff import build_handoff_checklist, format_handoff_checklist, handoff_checklist_to_json
from axon.release_bundle_manifest import RELEASE_HANDOFF_ARTIFACTS, build_release_bundle_manifest, format_release_bundle_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_handoff_includes_release_bundle_manifest_command():
    checklist = build_handoff_checklist(ROOT)
    shells = [command.shell for command in checklist.commands]

    assert any(shell == "axon release-bundle-manifest . --output release-bundle-manifest.json" for shell in shells)
    assert any(
        shell == "axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown"
        for shell in shells
    )


def test_handoff_json_mentions_release_bundle_manifest_artifacts():
    payload = json.loads(handoff_checklist_to_json(build_handoff_checklist(ROOT)))
    rendered = json.dumps(payload)

    assert "release-bundle-manifest.json" in rendered
    assert "RELEASE_BUNDLE_MANIFEST.md" in rendered
    assert "docs/RELEASE_BUNDLE.md" in rendered


def test_handoff_text_and_manifest_recommend_same_json_artifact():
    handoff = format_handoff_checklist(build_handoff_checklist(ROOT))
    manifest_text = format_release_bundle_manifest(build_release_bundle_manifest(ROOT))

    assert "release-bundle-manifest.json" in handoff
    assert "release-bundle-manifest.json" in manifest_text
    assert "axon release-bundle-manifest" in handoff
    assert "axon release-bundle-manifest" in manifest_text


def test_release_bundle_manifest_expected_artifacts_align_with_handoff_commands():
    expected_artifacts = {path for path, _description in RELEASE_HANDOFF_ARTIFACTS}
    handoff_shells = [command.shell for command in build_handoff_checklist(ROOT).commands]
    handoff_text = "\n".join(handoff_shells)

    for artifact in [
        "HANDOFF_CHECKLIST.md",
        "RELEASE_NOTES.md",
        "runtime-governance.json",
        "RUNTIME_GOVERNANCE_EVIDENCE.md",
        "release-bundle-manifest.json",
    ]:
        assert artifact in expected_artifacts
        assert artifact in handoff_text
