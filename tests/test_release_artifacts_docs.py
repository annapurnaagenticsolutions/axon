from __future__ import annotations

import json
from pathlib import Path

from axon.handoff import build_handoff_checklist, format_handoff_checklist, handoff_checklist_to_json


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_artifacts_documentation_exists_and_lists_outputs():
    doc = _read("docs/RELEASE_ARTIFACTS.md")

    for phrase in [
        "axon release-artifacts",
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
        "release-artifacts.json",
    ]:
        assert phrase in doc


def test_release_artifacts_documentation_preserves_runtime_boundary():
    doc = _read("docs/RELEASE_ARTIFACTS.md")
    boundary_phrases = [
        "does **not** execute AXON agents",
        "call providers",
        "dispatch tools",
        "resolve secrets",
        "import FastMCP",
        "mutate memory",
        "index RAG data",
        "execute flows",
        "replay traces",
    ]
    for phrase in boundary_phrases:
        assert phrase in doc


def test_handoff_checklist_includes_one_command_release_artifact_writer():
    checklist = build_handoff_checklist(ROOT)
    shells = [command.shell for command in checklist.commands]

    assert any(shell.startswith("axon release-artifacts") for shell in shells)
    assert any("--output-dir release-artifacts" in shell for shell in shells)
    assert "docs/RELEASE_ARTIFACTS.md" in checklist.documents

    rendered = format_handoff_checklist(checklist)
    assert "release-artifacts" in rendered
    assert "docs/RELEASE_ARTIFACTS.md" in rendered

    payload = json.loads(handoff_checklist_to_json(checklist))
    assert any(command["name"] == "release-artifacts" for command in payload["commands"])
    assert "api_key" not in json.dumps(payload).lower()


def test_release_artifacts_cross_links_are_documented():
    for path in [
        "README.md",
        "docs/CLI_REFERENCE.md",
        "docs/HANDOFF.md",
        "docs/RELEASE_BUNDLE.md",
        "docs/ROADMAP.md",
    ]:
        assert "docs/RELEASE_ARTIFACTS.md" in _read(path)
