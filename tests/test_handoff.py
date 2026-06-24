from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from axon.handoff import (
    build_handoff_checklist,
    format_handoff_checklist,
    handoff_checklist_to_json,
    write_handoff_checklist,
)

ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def test_build_handoff_checklist_contains_core_commands():
    checklist = build_handoff_checklist(ROOT)
    shells = [command.shell for command in checklist.commands]

    assert any(shell.startswith("axon version") for shell in shells)
    assert any(shell.startswith("axon info") for shell in shells)
    assert any(shell.startswith("axon project-info") for shell in shells)
    assert any(shell.startswith("axon foundation-audit") for shell in shells)
    assert any(shell.startswith("axon deps") for shell in shells)
    assert any(shell.startswith("axon hygiene") for shell in shells)
    assert any(shell.startswith("axon check-project") for shell in shells)
    assert any(shell.startswith("axon precommit run") for shell in shells)
    assert any(shell.startswith("axon runtime-governance-evidence") for shell in shells)
    assert any("runtime-governance.json" in shell for shell in shells)
    assert any("RUNTIME_GOVERNANCE_EVIDENCE.md" in shell for shell in shells)
    assert any(shell.startswith("axon release-bundle-manifest") for shell in shells)
    assert any("release-bundle-manifest.json" in shell for shell in shells)
    assert any("RELEASE_BUNDLE_MANIFEST.md" in shell for shell in shells)
    assert any(shell.startswith("axon release-notes") for shell in shells)
    assert any("--no-smoke" in shell for shell in shells)


def test_full_handoff_checklist_uses_smoke_enabled_commands():
    checklist = build_handoff_checklist(ROOT, full=True)
    shells = [command.shell for command in checklist.commands]

    assert any(shell.startswith("axon check-project") and "--no-smoke" not in shell for shell in shells)
    assert any(shell.startswith("axon precommit run") and "--full" in shell for shell in shells)


def test_handoff_json_is_stable_and_secret_safe():
    checklist = build_handoff_checklist(ROOT)
    payload = json.loads(handoff_checklist_to_json(checklist))

    assert payload["project_path"] == str(ROOT.resolve())
    assert payload["full"] is False
    assert payload["commands"]
    rendered = json.dumps(payload)
    assert "api_key" not in rendered.lower()
    assert "ANTHROPIC_API_KEY" not in rendered


def test_format_handoff_checklist_human_output():
    output = format_handoff_checklist(build_handoff_checklist(ROOT))

    assert "AXON release handoff checklist" in output
    assert "Commands to run and record:" in output
    assert "Documents to review/update:" in output
    assert "axon project-info" in output
    assert "axon foundation-audit" in output
    assert "docs/HANDOFF.md" in output
    assert "docs/FOUNDATION_AUDIT.md" in output
    assert "docs/RUNTIME_GOVERNANCE_EVIDENCE.md" in output
    assert "docs/RELEASE_BUNDLE.md" in output
    assert "runtime-governance.json" in output
    assert "release-bundle-manifest.json" in output


def test_write_handoff_checklist_text_and_json(tmp_path: Path):
    checklist = build_handoff_checklist(ROOT)
    text_path = tmp_path / "HANDOFF_CHECKLIST.md"
    json_path = tmp_path / "handoff.json"

    write_handoff_checklist(text_path, checklist)
    write_handoff_checklist(json_path, checklist, json_output=True)

    assert "AXON release handoff checklist" in text_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["commands"]


def test_handoff_cli_outputs_text():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "handoff", str(ROOT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )

    assert completed.returncode == 0
    assert "AXON release handoff checklist" in completed.stdout
    assert "axon check-project" in completed.stdout


def test_handoff_cli_outputs_json():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "handoff", str(ROOT), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["commands"]


def test_handoff_cli_writes_output_file(tmp_path: Path):
    destination = tmp_path / "handoff.md"
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "handoff", str(ROOT), "--output", str(destination)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )

    assert completed.returncode == 0
    assert destination.exists()
    assert "Wrote AXON handoff checklist" in completed.stdout
    assert "AXON release handoff checklist" in destination.read_text(encoding="utf-8")
