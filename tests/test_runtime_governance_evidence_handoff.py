from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from axon.handoff import build_handoff_checklist, format_handoff_checklist, handoff_checklist_to_json

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def test_handoff_checklist_includes_runtime_governance_evidence_artifacts():
    checklist = build_handoff_checklist(ROOT)
    shells = [command.shell for command in checklist.commands]
    names = [command.name for command in checklist.commands]

    assert "runtime-governance-evidence" in names
    assert "runtime-governance-evidence-markdown" in names
    assert any(shell == "axon runtime-governance-evidence . --output runtime-governance.json" for shell in shells)
    assert any("RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown" in shell for shell in shells)
    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in checklist.documents
    assert any("runtime-governance.json" in note for note in checklist.notes)


def test_handoff_json_exposes_runtime_governance_evidence_without_secrets():
    payload = json.loads(handoff_checklist_to_json(build_handoff_checklist(ROOT)))
    rendered = json.dumps(payload)

    assert "runtime-governance-evidence" in rendered
    assert "runtime-governance.json" in rendered
    assert "RUNTIME_GOVERNANCE_EVIDENCE.md" in rendered
    assert "api_key" not in rendered.lower()
    assert "ANTHROPIC_API_KEY" not in rendered


def test_formatted_handoff_mentions_runtime_governance_evidence_doc():
    rendered = format_handoff_checklist(build_handoff_checklist(ROOT))

    assert "runtime-governance-evidence" in rendered
    assert "runtime-governance.json" in rendered
    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in rendered


def test_runtime_governance_evidence_doc_exists_and_defines_release_workflow():
    doc = _read("docs/RUNTIME_GOVERNANCE_EVIDENCE.md")

    for phrase in [
        "axon runtime-governance-evidence",
        "runtime-governance.json",
        "RUNTIME_GOVERNANCE_EVIDENCE.md",
        "axon handoff .",
        "does not execute AXON agents",
        "declaration_inspection",
        "method_execution",
        "provider_calls",
        "tool_dispatch",
        "secret_resolution",
    ]:
        assert phrase in doc


def test_handoff_docs_integrate_runtime_governance_evidence():
    handoff = _read("docs/HANDOFF.md")
    readme = _read("README.md")
    cli_reference = _read("docs/CLI_REFERENCE.md")
    governance = _read("docs/RUNTIME_GOVERNANCE.md")

    for text in (handoff, readme, cli_reference, governance):
        assert "runtime-governance-evidence" in text
        assert "runtime-governance.json" in text

    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in handoff
    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in readme
    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in cli_reference
    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in governance


def test_handoff_cli_outputs_runtime_governance_evidence_command():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "handoff", str(ROOT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )

    assert completed.returncode == 0
    assert "runtime-governance-evidence" in completed.stdout
    assert "runtime-governance.json" in completed.stdout
