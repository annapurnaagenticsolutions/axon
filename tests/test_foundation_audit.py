from __future__ import annotations

import json
from pathlib import Path

from axon.foundation_audit import (
    DISABLED_RUNTIME_CAPABILITIES,
    FOUNDATION_AREAS,
    audit_foundation,
    format_foundation_audit_report,
    foundation_audit_to_json,
)
from axon.cli import main


ROOT = Path(__file__).resolve().parents[1]


def test_foundation_audit_passes_for_repository():
    report = audit_foundation(ROOT)
    assert report.passed
    assert report.error_count == 0
    assert report.source_modules_checked > 20
    assert report.examples_checked >= 13
    assert report.ast_snapshot_count >= 13
    assert report.formatted_snapshot_count >= 13
    assert report.runtime_plan_snapshot_count >= 13
    assert set(FOUNDATION_AREAS).issubset(set(report.areas))


def test_foundation_audit_json_is_stable_and_safe():
    report = audit_foundation(ROOT)
    data = json.loads(foundation_audit_to_json(report))
    assert data["schema"] == "axon.foundation_audit.v1"
    assert data["passed"] is True
    assert "declaration_inspection" not in data["disabled_runtime_capabilities"]
    for capability in DISABLED_RUNTIME_CAPABILITIES:
        assert capability in data["disabled_runtime_capabilities"]
    assert "does not execute AXON agents" in data["non_execution_guarantee"]
    assert "call providers" in data["non_execution_guarantee"]


def test_foundation_audit_human_output_mentions_key_areas():
    output = format_foundation_audit_report(audit_foundation(ROOT))
    assert "AXON Phase 1 foundation audit" in output
    assert "Status: passed" in output
    assert "parser_ast" in output
    assert "runtime_governance" in output
    assert "method_execution" in output
    assert "No foundation audit issues found." in output


def test_foundation_audit_reports_missing_project_path(tmp_path):
    missing = tmp_path / "missing"
    try:
        audit_foundation(missing)
    except FileNotFoundError as exc:
        assert "project path not found" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected FileNotFoundError")


def test_foundation_audit_cli_human(capsys):
    code = main(["foundation-audit", str(ROOT)])
    captured = capsys.readouterr()
    assert code == 0
    assert "AXON Phase 1 foundation audit" in captured.out
    assert "Status: passed" in captured.out


def test_foundation_audit_cli_json(capsys):
    code = main(["foundation-audit", str(ROOT), "--json"])
    captured = capsys.readouterr()
    assert code == 0
    data = json.loads(captured.out)
    assert data["schema"] == "axon.foundation_audit.v1"
    assert data["passed"] is True
