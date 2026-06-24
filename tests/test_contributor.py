from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from axon.contributor import (
    TaskTicket,
    build_task_ticket,
    format_task_ticket,
    task_ticket_to_json,
    write_task_ticket,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_task_ticket_defaults_are_self_contained():
    ticket = build_task_ticket(number=36, title="Contributor Guide", module="src/axon/contributor.py")
    assert isinstance(ticket, TaskTicket)
    assert ticket.heading == "AXON Task #36 — Contributor Guide"
    assert ticket.module == "src/axon/contributor.py"
    assert any("Do not call providers" in rule for rule in ticket.rules)
    assert "python -m pytest" in ticket.validation_commands


def test_format_task_ticket_contains_required_sections():
    ticket = build_task_ticket(number=37, title="Focused Task")
    text = format_task_ticket(ticket)
    for section in [
        "# AXON Task #37 — Focused Task",
        "## BACKGROUND",
        "## WHAT TO BUILD",
        "## INTERFACE",
        "## AXON SYNTAX REFERENCE",
        "## INPUT -> OUTPUT EXAMPLES",
        "## RULES & CONSTRAINTS",
        "## VALIDATION COMMANDS",
        "## REVIEW NOTES",
    ]:
        assert section in text


def test_task_ticket_json_is_stable_and_safe():
    ticket = build_task_ticket(number=38, title="JSON Task")
    payload = json.loads(task_ticket_to_json(ticket))
    assert payload["number"] == 38
    assert payload["title"] == "JSON Task"
    assert "validation_commands" in payload
    rendered = json.dumps(payload)
    assert "API_KEY" not in rendered


def test_write_task_ticket_markdown_and_json(tmp_path: Path):
    ticket = build_task_ticket(number=39, title="Write Task")
    md_path = write_task_ticket(tmp_path / "task.md", ticket)
    json_path = write_task_ticket(tmp_path / "task.json", ticket, json_output=True)
    assert md_path.read_text(encoding="utf-8").startswith("# AXON Task #39")
    assert json.loads(json_path.read_text(encoding="utf-8"))["heading"].startswith("AXON Task #39")


def test_task_template_cli_outputs_markdown():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "axon",
            "task-template",
            "--number",
            "36",
            "--title",
            "Contributor Guide + Task Ticket Template",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=env,
    )
    assert completed.returncode == 0
    assert "AXON Task #36" in completed.stdout
    assert "VALIDATION COMMANDS" in completed.stdout


def test_task_template_cli_writes_json(tmp_path: Path):
    output = tmp_path / "ticket.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "axon",
            "task-template",
            "--number",
            "40",
            "--title",
            "JSON Ticket",
            "--json",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=env,
    )
    assert completed.returncode == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["number"] == 40
