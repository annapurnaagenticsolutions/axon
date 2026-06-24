from __future__ import annotations

import json
from pathlib import Path

from axon.runtime_plan_review_consistency import (
    check_runtime_plan_review_consistency,
    disabled_runtime_capabilities,
    enabled_runtime_capabilities,
    format_runtime_plan_review_consistency_report,
    runtime_plan_review_consistency_report_to_json,
)
from axon.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_plan_review_consistency_passes_for_project_without_corpus():
    report = check_runtime_plan_review_consistency(ROOT, skip_corpus=True)
    assert report.passed
    assert report.checks
    assert any(check.name == "doc-exists" for check in report.checks)
    assert any(check.name == "review-doc-required-command" for check in report.checks)
    assert any(check.name == "runtime-plan-corpus" and check.passed for check in report.checks)


def test_runtime_plan_review_consistency_passes_with_corpus():
    report = check_runtime_plan_review_consistency(ROOT)
    assert report.passed
    assert any(check.name == "runtime-plan-corpus" and "passed" in check.message for check in report.checks)


def test_runtime_plan_review_consistency_json_is_stable():
    report = check_runtime_plan_review_consistency(ROOT, skip_corpus=True)
    payload = json.loads(runtime_plan_review_consistency_report_to_json(report))
    assert payload["passed"] is True
    assert payload["summary"]["failed"] == 0
    assert payload["checks"]


def test_runtime_plan_review_consistency_format_mentions_status_and_commands():
    rendered = format_runtime_plan_review_consistency_report(
        check_runtime_plan_review_consistency(ROOT, skip_corpus=True)
    )
    assert "AXON runtime-plan review consistency: passed" in rendered
    assert "review-doc-required-command" in rendered
    assert "runtime-plan-corpus" in rendered


def test_runtime_plan_review_consistency_detects_missing_docs(tmp_path: Path):
    # A minimal empty project should fail because required docs and corpus files are absent.
    report = check_runtime_plan_review_consistency(tmp_path, skip_corpus=True)
    assert not report.passed
    assert any(check.name == "doc-exists" and not check.passed for check in report.checks)


def test_runtime_plan_review_capability_helpers_follow_runtime_plan_boundary():
    assert enabled_runtime_capabilities() == ["declaration_inspection"]
    disabled = disabled_runtime_capabilities()
    for capability in [
        "method_execution",
        "provider_calls",
        "tool_dispatch",
        "memory_mutation",
        "rag_indexing",
        "rag_retrieval",
        "flow_execution",
        "trace_replay",
        "secret_resolution",
        "fastmcp_runtime_import",
    ]:
        assert capability in disabled


def test_cli_runtime_plan_review_check_outputs_text(capsys):
    code = main(["runtime-plan-review-check", str(ROOT), "--skip-corpus"])
    assert code == 0
    output = capsys.readouterr().out
    assert "AXON runtime-plan review consistency: passed" in output
    assert "runtime-plan-corpus" in output


def test_cli_runtime_plan_review_check_outputs_json(capsys):
    code = main(["runtime-plan-review-check", str(ROOT), "--skip-corpus", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["summary"]["failed"] == 0
