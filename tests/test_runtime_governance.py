from __future__ import annotations

import json
from pathlib import Path

from axon.runtime_governance import (
    NON_EXECUTION_GUARANTEE,
    check_runtime_governance,
    format_runtime_governance_report,
    runtime_governance_report_to_json,
)

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_governance_gate_passes_with_corpus():
    report = check_runtime_governance(ROOT)
    assert report.passed
    names = [step.name for step in report.steps]
    assert names == [
        "runtime-plan-review",
        "runtime-plan-review-check",
        "runtime-plan-corpus",
        "deps",
        "hygiene",
    ]
    assert NON_EXECUTION_GUARANTEE in report.non_execution_guarantee


def test_runtime_governance_gate_can_skip_corpus():
    report = check_runtime_governance(ROOT, skip_corpus=True)
    assert report.passed
    corpus_step = next(step for step in report.steps if step.name == "runtime-plan-corpus")
    assert corpus_step.details["skipped"] is True


def test_runtime_governance_json_is_stable():
    report = check_runtime_governance(ROOT, skip_corpus=True)
    data = json.loads(runtime_governance_report_to_json(report))
    assert data["passed"] is True
    assert data["summary"]["total"] == 5
    assert "axon runtime-plan-review" in data["required_commands"]
    assert "provider" in data["non_execution_guarantee"]


def test_runtime_governance_human_format_mentions_commands():
    report = check_runtime_governance(ROOT, skip_corpus=True)
    text = format_runtime_governance_report(report)
    assert "AXON runtime governance gate: passed" in text
    assert "axon runtime-plan-review-check ." in text
    assert "axon deps ." in text
