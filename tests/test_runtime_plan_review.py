from __future__ import annotations

import json
from pathlib import Path

from axon.runtime_plan_review import (
    build_runtime_plan_review_checklist,
    format_runtime_plan_review_checklist,
    runtime_plan_review_checklist_to_json,
    write_runtime_plan_review_checklist,
)
from axon.cli import main


def test_build_runtime_plan_review_checklist_contains_boundary_items():
    checklist = build_runtime_plan_review_checklist(change="schema update")
    assert checklist.change == "schema update"
    assert "inspection-only" in checklist.boundary_statement
    assert "method_execution" in checklist.escalation_rule
    assert "axon runtime-plan-corpus ." in checklist.required_commands

    data = checklist.to_dict()
    text = json.dumps(data)
    for phrase in [
        "declaration_inspection",
        "provider_calls",
        "tool_dispatch",
        "memory_mutation",
        "rag_indexing",
        "flow_execution",
        "trace_replay",
        "secret_resolution",
        "fastmcp_runtime_import",
        "Runtime RFC",
    ]:
        assert phrase in text


def test_runtime_plan_review_json_is_stable_and_machine_readable():
    checklist = build_runtime_plan_review_checklist()
    payload = json.loads(runtime_plan_review_checklist_to_json(checklist))
    assert payload["title"] == "AXON Runtime Plan Reviewer Checklist"
    assert payload["sections"]
    assert payload["required_commands"]
    assert payload["sections"][0]["items"][0]["required"] is True


def test_runtime_plan_review_markdown_has_checkboxes_and_evidence():
    rendered = format_runtime_plan_review_checklist(build_runtime_plan_review_checklist())
    assert "# AXON Runtime Plan Reviewer Checklist" in rendered
    assert "- [ ] **scope-001**" in rendered
    assert "Evidence:" in rendered
    assert "Required Validation Commands" in rendered
    assert "axon deps ." in rendered


def test_write_runtime_plan_review_checklist_markdown_and_json(tmp_path: Path):
    checklist = build_runtime_plan_review_checklist(change="snapshot diff")
    md_path = write_runtime_plan_review_checklist(tmp_path / "review.md", checklist)
    json_path = write_runtime_plan_review_checklist(tmp_path / "review.json", checklist, json_output=True)

    assert md_path.read_text(encoding="utf-8").startswith("# AXON Runtime Plan Reviewer Checklist")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["change"] == "snapshot diff"


def test_cli_runtime_plan_review_outputs_markdown(capsys):
    code = main(["runtime-plan-review", "--change", "boundary wording update"])
    assert code == 0
    output = capsys.readouterr().out
    assert "AXON Runtime Plan Reviewer Checklist" in output
    assert "boundary wording update" in output
    assert "axon runtime-plan-corpus ." in output


def test_cli_runtime_plan_review_outputs_json(capsys):
    code = main(["runtime-plan-review", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "AXON Runtime Plan Reviewer Checklist"


def test_cli_runtime_plan_review_writes_file(tmp_path: Path, capsys):
    destination = tmp_path / "runtime-plan-review.md"
    code = main(["runtime-plan-review", "--output", str(destination)])
    assert code == 0
    assert destination.exists()
    assert "Wrote runtime-plan review checklist" in capsys.readouterr().out
    assert "Runtime Boundary" in destination.read_text(encoding="utf-8")
