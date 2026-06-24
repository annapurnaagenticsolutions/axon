"""Reviewer checklist for runtime-plan and runtime-boundary changes.

The checklist is intentionally non-executing. It helps reviewers verify that
changes touching runtime-plan output, runtime-plan snapshots, or runtime-boundary
documentation remain aligned with Runtime RFC #001 before any runtime behavior is
implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

DEFAULT_ENCODING = "utf-8"


@dataclass(frozen=True)
class RuntimePlanReviewItem:
    """One checklist item for a runtime-plan-adjacent review."""

    id: str
    text: str
    evidence: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "evidence": self.evidence,
            "required": self.required,
        }


@dataclass(frozen=True)
class RuntimePlanReviewSection:
    """A named checklist section."""

    title: str
    purpose: str
    items: list[RuntimePlanReviewItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "purpose": self.purpose,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class RuntimePlanReviewChecklist:
    """Complete review checklist for runtime-plan changes."""

    title: str
    change: str
    boundary_statement: str
    sections: list[RuntimePlanReviewSection]
    required_commands: list[str]
    escalation_rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "change": self.change,
            "boundary_statement": self.boundary_statement,
            "sections": [section.to_dict() for section in self.sections],
            "required_commands": list(self.required_commands),
            "escalation_rule": self.escalation_rule,
        }


def build_runtime_plan_review_checklist(change: str = "runtime-plan-adjacent change") -> RuntimePlanReviewChecklist:
    """Build the standard runtime-plan reviewer checklist."""
    boundary_statement = (
        "Runtime-plan review is inspection-only. The change must not execute AXON "
        "method bodies, call providers, dispatch tools, mutate memory, index or retrieve "
        "RAG data, execute flows, replay traces, resolve secrets, or import FastMCP at "
        "compiler-core runtime."
    )

    sections = [
        RuntimePlanReviewSection(
            title="Scope classification",
            purpose="Confirm whether the change touches runtime planning, snapshots, corpus checks, or runtime-boundary documentation.",
            items=[
                RuntimePlanReviewItem(
                    id="scope-001",
                    text="Identify every touched runtime-plan file, snapshot, test, or documentation page.",
                    evidence="List files such as src/axon/runtime_plan.py, runtime_plan_snapshot.py, runtime_plan_corpus.py, docs/RUNTIME_PLAN.md, docs/RUNTIME_BOUNDARY.md, or tests/snapshots/runtime_plan/.",
                ),
                RuntimePlanReviewItem(
                    id="scope-002",
                    text="State whether the change is schema-only, documentation-only, snapshot-only, validator-related, or runtime-boundary-affecting.",
                    evidence="Reviewer note in PR or handoff summary.",
                ),
            ],
        ),
        RuntimePlanReviewSection(
            title="Runtime boundary preservation",
            purpose="Verify that Runtime RFC #001 remains respected unless a later accepted RFC explicitly changes the boundary.",
            items=[
                RuntimePlanReviewItem(
                    id="boundary-001",
                    text="Confirm declaration_inspection is the only enabled runtime capability.",
                    evidence="axon runtime-plan examples/hello.ax --json",
                ),
                RuntimePlanReviewItem(
                    id="boundary-002",
                    text="Confirm executable capabilities remain disabled: method_execution, provider_calls, tool_dispatch, memory_mutation, rag_indexing, rag_retrieval, flow_execution, trace_replay, secret_resolution, and fastmcp_runtime_import.",
                    evidence="axon runtime-plan-corpus .",
                ),
                RuntimePlanReviewItem(
                    id="boundary-003",
                    text="Confirm compiler core still does not import FastMCP, OpenAI, Anthropic, Google, Cohere, Ollama client SDKs, or other provider/runtime SDKs.",
                    evidence="axon deps .",
                ),
                RuntimePlanReviewItem(
                    id="boundary-004",
                    text="Confirm no code path resolves or prints provider API keys or environment secrets.",
                    evidence="axon config --config axon.toml --json and reviewer inspection of changed code.",
                ),
            ],
        ),
        RuntimePlanReviewSection(
            title="Snapshot and corpus evidence",
            purpose="Ensure runtime-plan output changes are intentional, stable, and corpus-tested.",
            items=[
                RuntimePlanReviewItem(
                    id="snapshot-001",
                    text="If runtime-plan JSON structure changed, update snapshots deliberately and review the diff.",
                    evidence="axon runtime-plan <source.ax> --write <snapshot> --root . plus git diff of tests/snapshots/runtime_plan/.",
                ),
                RuntimePlanReviewItem(
                    id="snapshot-002",
                    text="Confirm every example runtime-plan snapshot matches current output and no orphan snapshots exist.",
                    evidence="axon runtime-plan-corpus .",
                ),
                RuntimePlanReviewItem(
                    id="snapshot-003",
                    text="Confirm project syntax, semantic validation, and AST snapshots still pass for examples.",
                    evidence="axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke",
                ),
            ],
        ),
        RuntimePlanReviewSection(
            title="Documentation and RFC alignment",
            purpose="Keep runtime-plan behavior, runtime boundary, and RFC documentation synchronized.",
            items=[
                RuntimePlanReviewItem(
                    id="docs-001",
                    text="Update docs/RUNTIME_PLAN.md when user-visible runtime-plan commands, fields, or workflow change.",
                    evidence="Documentation diff and tests/test_runtime_plan_docs.py.",
                ),
                RuntimePlanReviewItem(
                    id="docs-002",
                    text="Update docs/RUNTIME_BOUNDARY.md and docs/runtime-rfcs/0001-minimal-non-executing-runtime.md if the boundary wording changes.",
                    evidence="Documentation diff and runtime-boundary doc tests.",
                ),
                RuntimePlanReviewItem(
                    id="docs-003",
                    text="Update README.md, docs/CLI_REFERENCE.md, and docs/HANDOFF.md when commands or handoff evidence change.",
                    evidence="CLI/help/docs tests and rendered docs review.",
                ),
            ],
        ),
        RuntimePlanReviewSection(
            title="Escalation gate",
            purpose="Prevent accidental runtime execution work from entering through runtime-plan changes.",
            items=[
                RuntimePlanReviewItem(
                    id="escalation-001",
                    text="If the change enables any execution capability, stop implementation and require a dedicated Runtime RFC first.",
                    evidence="Accepted Runtime RFC number and explicit acceptance criteria.",
                ),
                RuntimePlanReviewItem(
                    id="escalation-002",
                    text="If the change touches provider calls, tool dispatch, memory mutation, RAG execution, flow execution, or trace replay, classify it as runtime work, not runtime-plan inspection work.",
                    evidence="Reviewer note linking to the relevant Runtime RFC or deferring the change.",
                ),
            ],
        ),
    ]

    required_commands = [
        "python -m compileall -q src tests",
        "axon runtime-plan examples/hello.ax",
        "axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root .",
        "axon runtime-plan-corpus .",
        "axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke",
        "axon deps .",
        "axon hygiene .",
    ]

    escalation_rule = (
        "Any change that enables method_execution, provider_calls, tool_dispatch, "
        "memory_mutation, rag_indexing/rag_retrieval, flow_execution, trace_replay, "
        "secret_resolution, or fastmcp_runtime_import must be preceded by an accepted "
        "Runtime RFC."
    )

    return RuntimePlanReviewChecklist(
        title="AXON Runtime Plan Reviewer Checklist",
        change=change,
        boundary_statement=boundary_statement,
        sections=sections,
        required_commands=required_commands,
        escalation_rule=escalation_rule,
    )


def runtime_plan_review_checklist_to_json(checklist: RuntimePlanReviewChecklist) -> str:
    """Serialize a runtime-plan review checklist to stable JSON."""
    return json.dumps(checklist.to_dict(), indent=2, sort_keys=True) + "\n"


def format_runtime_plan_review_checklist(checklist: RuntimePlanReviewChecklist) -> str:
    """Render a runtime-plan review checklist as Markdown."""
    lines = [f"# {checklist.title}", "", f"Change: {checklist.change}", "", "## Runtime Boundary", "", checklist.boundary_statement, ""]
    for section in checklist.sections:
        lines.extend([f"## {section.title}", "", section.purpose, ""])
        for item in section.items:
            required = "required" if item.required else "optional"
            lines.append(f"- [ ] **{item.id}** ({required}) {item.text}")
            lines.append(f"      Evidence: {item.evidence}")
        lines.append("")
    lines.extend(["## Required Validation Commands", ""])
    for command in checklist.required_commands:
        lines.append(f"```bash\n{command}\n```")
    lines.extend(["", "## Escalation Rule", "", checklist.escalation_rule, ""])
    return "\n".join(lines)


def write_runtime_plan_review_checklist(
    path: str | Path,
    checklist: RuntimePlanReviewChecklist,
    *,
    json_output: bool = False,
) -> Path:
    """Write a runtime-plan review checklist to Markdown or JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = runtime_plan_review_checklist_to_json(checklist) if json_output else format_runtime_plan_review_checklist(checklist)
    destination.write_text(content, encoding=DEFAULT_ENCODING)
    return destination
