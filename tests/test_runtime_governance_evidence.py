from __future__ import annotations

import json
from pathlib import Path

from axon.runtime_governance_evidence import (
    build_runtime_governance_evidence,
    format_runtime_governance_evidence,
    runtime_governance_evidence_to_json,
    write_runtime_governance_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_runtime_governance_evidence_skip_corpus_is_secret_safe():
    evidence = build_runtime_governance_evidence(ROOT, skip_corpus=True)

    assert evidence.schema == "axon.runtime_governance_evidence.v1"
    assert evidence.evidence_kind == "runtime-governance"
    assert evidence.passed is True
    assert "does not execute AXON agents" in evidence.non_execution_guarantee
    assert "runtime-governance.json" in evidence.recommended_artifacts
    assert "axon runtime-plan-review" in evidence.recommended_commands

    rendered = runtime_governance_evidence_to_json(evidence)
    assert "ANTHROPIC_API_KEY" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "api_key" not in rendered.lower()


def test_runtime_governance_evidence_json_has_report_summary():
    evidence = build_runtime_governance_evidence(ROOT, skip_corpus=True)
    data = json.loads(runtime_governance_evidence_to_json(evidence))

    assert data["schema"] == "axon.runtime_governance_evidence.v1"
    assert data["passed"] is True
    assert data["report"]["summary"]["failed"] == 0
    assert data["report"]["summary"]["total"] >= 5
    assert data["report"]["steps"][0]["name"] == "runtime-plan-review"


def test_format_runtime_governance_evidence_markdown():
    evidence = build_runtime_governance_evidence(ROOT, skip_corpus=True)
    text = format_runtime_governance_evidence(evidence)

    assert text.startswith("# AXON Runtime Governance Evidence")
    assert "## Governance Steps" in text
    assert "runtime-plan-review" in text
    assert "## Non-Execution Guarantee" in text


def test_write_runtime_governance_evidence_json_and_markdown(tmp_path):
    evidence = build_runtime_governance_evidence(ROOT, skip_corpus=True)

    json_path = write_runtime_governance_evidence(tmp_path / "runtime-governance.json", evidence)
    md_path = write_runtime_governance_evidence(tmp_path / "RUNTIME_GOVERNANCE_EVIDENCE.md", evidence)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema"] == "axon.runtime_governance_evidence.v1"
    assert md_path.read_text(encoding="utf-8").startswith("# AXON Runtime Governance Evidence")
