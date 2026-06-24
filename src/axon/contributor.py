"""Contributor workflow helpers for AXON.

This module provides a deterministic, non-executing task ticket template so AXON
work can be handed to humans or LLM implementers without relying on hidden chat
context. It intentionally contains no provider calls, no runtime execution, and
no dependencies beyond the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Sequence


DEFAULT_SECTIONS = [
    "BACKGROUND",
    "WHAT TO BUILD",
    "INTERFACE",
    "AXON SYNTAX REFERENCE",
    "INPUT -> OUTPUT EXAMPLES",
    "RULES & CONSTRAINTS",
    "DEPENDENCIES",
    "TEST CASES",
    "DELIVERABLES",
    "VALIDATION COMMANDS",
]

DEFAULT_WHAT_TO_BUILD = "Describe the exact files, functions, classes, and behavior to build."

DEFAULT_RULES = [
    "Keep the task scope narrow and do not implement future milestones.",
    "Use Python standard library only unless this ticket explicitly allows a dependency.",
    "Do not call providers, execute AXON agent bodies, or resolve secrets.",
    "Preserve compatibility with all previous AXON tasks and tests.",
    "Add or update tests for every behavior changed by this task.",
    "Prefer clear errors and deterministic output over clever behavior.",
]

DEFAULT_VALIDATION_COMMANDS = [
    "python -m compileall -q src tests",
    "python -m pytest",
    "python -m axon deps .",
    "python -m axon hygiene .",
    "python -m axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke",
]


@dataclass(frozen=True)
class TaskTicket:
    """Structured AXON implementation ticket suitable for human/LLM handoff."""

    number: int | None = None
    title: str = "Untitled AXON Task"
    module: str | None = None
    background: str = (
        "AXON is an AI-native language prototype for defining, validating, tracing, "
        "and generating infrastructure for agentic systems. This ticket must be "
        "implemented without hidden context beyond the repository and this document."
    )
    what_to_build: str = DEFAULT_WHAT_TO_BUILD
    interface: str = "Paste copy-ready function signatures, dataclasses, CLI commands, or schemas here."
    syntax_reference: str = "Include only the AXON syntax patterns this task must handle."
    examples: str = "Provide concrete input -> output examples."
    rules: list[str] = field(default_factory=lambda: list(DEFAULT_RULES))
    dependencies: str = "Python 3.11+ standard library only unless stated otherwise."
    tests: str = "List required pytest cases and edge cases."
    deliverables: list[str] = field(default_factory=lambda: ["Updated source files", "Updated tests", "Updated docs if CLI or user behavior changes"])
    validation_commands: list[str] = field(default_factory=lambda: list(DEFAULT_VALIDATION_COMMANDS))

    @property
    def heading(self) -> str:
        """Return the ticket heading."""
        if self.number is None:
            return f"AXON Task — {self.title}"
        return f"AXON Task #{self.number:02d} — {self.title}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "number": self.number,
            "title": self.title,
            "module": self.module,
            "heading": self.heading,
            "background": self.background,
            "what_to_build": self.what_to_build,
            "interface": self.interface,
            "syntax_reference": self.syntax_reference,
            "examples": self.examples,
            "rules": list(self.rules),
            "dependencies": self.dependencies,
            "tests": self.tests,
            "deliverables": list(self.deliverables),
            "validation_commands": list(self.validation_commands),
        }


def build_task_ticket(
    *,
    number: int | None = None,
    title: str = "Untitled AXON Task",
    module: str | None = None,
    what_to_build: str | None = None,
    deliverables: Sequence[str] | None = None,
    validation_commands: Sequence[str] | None = None,
) -> TaskTicket:
    """Build a task ticket with conservative AXON defaults."""
    return TaskTicket(
        number=number,
        title=title,
        module=module,
        what_to_build=what_to_build or DEFAULT_WHAT_TO_BUILD,
        deliverables=list(deliverables) if deliverables is not None else [
            "Updated source files",
            "Updated tests",
            "Updated docs if CLI or user behavior changes",
        ],
        validation_commands=list(validation_commands) if validation_commands is not None else list(DEFAULT_VALIDATION_COMMANDS),
    )


def format_task_ticket(ticket: TaskTicket) -> str:
    """Render a task ticket as Markdown."""
    lines: list[str] = [f"# {ticket.heading}", "> Self-contained implementation ticket for AXON contributors and LLM coding agents.", ""]
    if ticket.module:
        lines.extend([f"**Suggested module:** `{ticket.module}`", ""])

    lines.extend([
        "---",
        "",
        "## BACKGROUND",
        "",
        ticket.background,
        "",
        "## WHAT TO BUILD",
        "",
        ticket.what_to_build,
        "",
        "## INTERFACE",
        "",
        "```python",
        ticket.interface,
        "```",
        "",
        "## AXON SYNTAX REFERENCE",
        "",
        "```axon",
        ticket.syntax_reference,
        "```",
        "",
        "## INPUT -> OUTPUT EXAMPLES",
        "",
        ticket.examples,
        "",
        "## RULES & CONSTRAINTS",
        "",
    ])
    lines.extend(f"{index}. {rule}" for index, rule in enumerate(ticket.rules, start=1))
    lines.extend([
        "",
        "## DEPENDENCIES",
        "",
        "```text",
        ticket.dependencies,
        "```",
        "",
        "## TEST CASES",
        "",
        ticket.tests,
        "",
        "## DELIVERABLES",
        "",
    ])
    lines.extend(f"- {item}" for item in ticket.deliverables)
    lines.extend([
        "",
        "## VALIDATION COMMANDS",
        "",
        "Run the narrowest relevant subset first, then the broader checks when the task is ready:",
        "",
        "```bash",
    ])
    lines.extend(ticket.validation_commands)
    lines.extend([
        "```",
        "",
        "## REVIEW NOTES",
        "",
        "- State exactly what changed.",
        "- State which commands passed.",
        "- State any known limitations or intentionally deferred scope.",
        "- Do not claim full-suite validation unless it actually completed.",
        "",
    ])
    return "\n".join(lines)


def task_ticket_to_json(ticket: TaskTicket) -> str:
    """Render a task ticket as stable JSON."""
    return json.dumps(ticket.to_dict(), indent=2, sort_keys=True)


def write_task_ticket(path: str | Path, ticket: TaskTicket, *, json_output: bool = False) -> Path:
    """Write a task ticket to disk and return the resolved destination path."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = task_ticket_to_json(ticket) if json_output else format_task_ticket(ticket)
    destination.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return destination
