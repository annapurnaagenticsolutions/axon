from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from axon.runtime_rfc import (
    RuntimeRFC,
    build_runtime_rfc_template,
    format_runtime_rfc_template,
    runtime_rfc_to_json,
    write_runtime_rfc_template,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_runtime_rfc_template_defaults_are_safe():
    rfc = build_runtime_rfc_template(number=1, title="Minimal Provider Runtime", owner="AXON")
    assert isinstance(rfc, RuntimeRFC)
    assert rfc.heading == "AXON Runtime RFC #001 — Minimal Provider Runtime"
    assert rfc.status == "Draft"
    assert rfc.owner == "AXON"
    assert any("Do not call model providers" in rule for rule in rfc.runtime_rules)
    assert any("secret" in rule.lower() for rule in rfc.runtime_rules)


def test_format_runtime_rfc_template_contains_required_sections():
    rfc = build_runtime_rfc_template(number=38, title="Runtime Design RFC Template")
    text = format_runtime_rfc_template(rfc)
    for phrase in [
        "# AXON Runtime RFC #038 — Runtime Design RFC Template",
        "## CURRENT BOUNDARY CHECK",
        "## PROPOSED RUNTIME SCOPE",
        "## AXON SYNTAX EXECUTED",
        "## PROVIDER PLUGIN IMPACT",
        "## TOOL DISPATCH IMPACT",
        "## TRACE AND OBSERVABILITY GUARANTEES",
        "## SECURITY AND SECRET HANDLING",
        "## TESTING STRATEGY",
        "## ACCEPTANCE CRITERIA",
        "docs/RUNTIME_BOUNDARY.md",
    ]:
        assert phrase in text


def test_runtime_rfc_json_is_stable_and_secret_safe():
    rfc = build_runtime_rfc_template(number=2, title="JSON Runtime RFC")
    payload = json.loads(runtime_rfc_to_json(rfc))
    assert payload["number"] == 2
    assert payload["title"] == "JSON Runtime RFC"
    assert "runtime_rules" in payload
    rendered = json.dumps(payload)
    assert "API_KEY" not in rendered
    assert "sk-" not in rendered


def test_write_runtime_rfc_template_markdown_and_json(tmp_path: Path):
    rfc = build_runtime_rfc_template(number=3, title="Write RFC")
    md_path = write_runtime_rfc_template(tmp_path / "rfc.md", rfc)
    json_path = write_runtime_rfc_template(tmp_path / "rfc.json", rfc, json_output=True)
    assert md_path.read_text(encoding="utf-8").startswith("# AXON Runtime RFC #003")
    assert json.loads(json_path.read_text(encoding="utf-8"))["heading"].startswith("AXON Runtime RFC #003")


def test_runtime_rfc_template_cli_outputs_markdown():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "axon",
            "runtime-rfc-template",
            "--number",
            "38",
            "--title",
            "Runtime Design RFC Template",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
    )
    assert completed.returncode == 0
    assert "AXON Runtime RFC #038" in completed.stdout
    assert "CURRENT BOUNDARY CHECK" in completed.stdout
    assert "SECURITY AND SECRET HANDLING" in completed.stdout


def test_runtime_rfc_template_cli_writes_json(tmp_path: Path):
    output = tmp_path / "runtime_rfc.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "axon",
            "runtime-rfc-template",
            "--number",
            "39",
            "--title",
            "JSON Runtime RFC",
            "--json",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
    )
    assert completed.returncode == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["number"] == 39
