"""Runtime RFC template helpers for AXON.

AXON runtime work must be proposed before implementation because it can cross
important safety boundaries: provider calls, tool dispatch, memory mutation,
RAG indexing, flow execution, and trace replay. This module provides a stable,
secret-safe RFC template for those proposals. It intentionally performs no
runtime execution and uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
from typing import Any, Sequence


DEFAULT_RUNTIME_RFC_SECTIONS = [
    "SUMMARY",
    "PROBLEM / MOTIVATION",
    "CURRENT BOUNDARY CHECK",
    "PROPOSED RUNTIME SCOPE",
    "NON-GOALS",
    "AXON SYNTAX EXECUTED",
    "PROVIDER PLUGIN IMPACT",
    "TOOL DISPATCH IMPACT",
    "MEMORY / RAG / FLOW IMPACT",
    "TRACE AND OBSERVABILITY GUARANTEES",
    "SECURITY AND SECRET HANDLING",
    "TESTING STRATEGY",
    "ROLLBACK PLAN",
    "ACCEPTANCE CRITERIA",
    "OPEN QUESTIONS",
]

DEFAULT_RUNTIME_RULES = [
    "Do not execute AXON agent bodies until the accepted RFC explicitly allows it.",
    "Do not call model providers from compiler-core modules.",
    "Do not dispatch `act` calls to real tools without a permission and mocking design.",
    "Do not resolve, print, or snapshot API keys or other secrets.",
    "Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.",
    "Define deterministic test doubles before adding live provider or tool behavior.",
    "Document exactly which AXON syntax subset the runtime will execute.",
    "State trace emission guarantees before runtime actions are implemented.",
]

DEFAULT_TESTING_CHECKLIST = [
    "unit tests for each runtime component",
    "provider calls mocked by default",
    "tool dispatch mocked by default",
    "secret redaction tests",
    "trace emission tests",
    "failure-path tests for provider/tool/memory errors",
    "no accidental network calls in compiler-core tests",
    "docs updated with runtime boundary changes",
]


@dataclass(frozen=True)
class RuntimeRFC:
    """Structured runtime design proposal template."""

    number: int | None = None
    title: str = "Untitled AXON Runtime RFC"
    status: str = "Draft"
    created: str = field(default_factory=lambda: date.today().isoformat())
    owner: str = "TBD"
    summary: str = "Briefly describe the runtime capability being proposed."
    motivation: str = "Explain why this runtime behavior is needed now."
    proposed_scope: str = "Describe the narrow runtime behavior this RFC would permit."
    non_goals: list[str] = field(default_factory=lambda: [
        "Do not implement unrelated runtime subsystems.",
        "Do not broaden provider/tool/memory behavior beyond this RFC.",
    ])
    runtime_rules: list[str] = field(default_factory=lambda: list(DEFAULT_RUNTIME_RULES))
    testing_checklist: list[str] = field(default_factory=lambda: list(DEFAULT_TESTING_CHECKLIST))
    sections: list[str] = field(default_factory=lambda: list(DEFAULT_RUNTIME_RFC_SECTIONS))

    @property
    def heading(self) -> str:
        """Return a stable RFC heading."""
        if self.number is None:
            return f"AXON Runtime RFC — {self.title}"
        return f"AXON Runtime RFC #{self.number:03d} — {self.title}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "number": self.number,
            "title": self.title,
            "status": self.status,
            "created": self.created,
            "owner": self.owner,
            "heading": self.heading,
            "summary": self.summary,
            "motivation": self.motivation,
            "proposed_scope": self.proposed_scope,
            "non_goals": list(self.non_goals),
            "runtime_rules": list(self.runtime_rules),
            "testing_checklist": list(self.testing_checklist),
            "sections": list(self.sections),
        }


def build_runtime_rfc_template(
    *,
    number: int | None = None,
    title: str = "Untitled AXON Runtime RFC",
    owner: str = "TBD",
    status: str = "Draft",
    created: str | None = None,
    proposed_scope: str | None = None,
    non_goals: Sequence[str] | None = None,
) -> RuntimeRFC:
    """Build a runtime RFC template with conservative AXON defaults."""
    return RuntimeRFC(
        number=number,
        title=title,
        status=status,
        created=created or date.today().isoformat(),
        owner=owner,
        proposed_scope=proposed_scope or "Describe the narrow runtime behavior this RFC would permit.",
        non_goals=list(non_goals) if non_goals is not None else [
            "Do not implement unrelated runtime subsystems.",
            "Do not broaden provider/tool/memory behavior beyond this RFC.",
        ],
    )


def format_runtime_rfc_template(rfc: RuntimeRFC) -> str:
    """Render a runtime RFC as Markdown."""
    lines: list[str] = [
        f"# {rfc.heading}",
        "",
        f"**Status:** {rfc.status}",
        f"**Created:** {rfc.created}",
        f"**Owner:** {rfc.owner}",
        "",
        "> Runtime work must be proposed before implementation. This template is intentionally strict because runtime behavior can call providers, dispatch tools, mutate memory, index RAG data, execute flows, or replay traces.",
        "",
        "---",
        "",
        "## SUMMARY",
        "",
        rfc.summary,
        "",
        "## PROBLEM / MOTIVATION",
        "",
        rfc.motivation,
        "",
        "## CURRENT BOUNDARY CHECK",
        "",
        "Confirm the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md` and state exactly what this RFC proposes to change.",
        "",
        "Required confirmations:",
        "",
    ]
    lines.extend(f"- [ ] {rule}" for rule in rfc.runtime_rules)
    lines.extend([
        "",
        "## PROPOSED RUNTIME SCOPE",
        "",
        rfc.proposed_scope,
        "",
        "## NON-GOALS",
        "",
    ])
    lines.extend(f"- {item}" for item in rfc.non_goals)
    lines.extend([
        "",
        "## AXON SYNTAX EXECUTED",
        "",
        "List the exact AXON constructs this runtime change will execute. Examples: `act`, `think`, `observe`, `store`, `@plan`, `memory.recall`, `flow`, or `rag`.",
        "",
        "```axon",
        "// Example syntax subset intentionally permitted by this RFC",
        "think \"...\"",
        "let result = act SomeTool(input: value)?",
        "observe result: result",
        "store memory.working[\"key\"] = result",
        "```",
        "",
        "## PROVIDER PLUGIN IMPACT",
        "",
        "Describe whether model providers are called. Define plugin protocol changes, mock provider behavior, timeout behavior, cost tracking, and redaction rules.",
        "",
        "## TOOL DISPATCH IMPACT",
        "",
        "Describe whether tools are dispatched. Define permission boundaries, mock dispatch, error handling, result schemas, and audit logs.",
        "",
        "## MEMORY / RAG / FLOW IMPACT",
        "",
        "State whether memory is mutated, RAG indexes are built/read, or flow DAGs are executed. Keep each subsystem separately scoped.",
        "",
        "## TRACE AND OBSERVABILITY GUARANTEES",
        "",
        "Define the exact AEL trace events emitted, required fields, ordering guarantees, replay boundaries, and what is intentionally not recorded.",
        "",
        "## SECURITY AND SECRET HANDLING",
        "",
        "State how API keys, environment variables, files, network access, provider responses, and generated traces are protected from leakage.",
        "",
        "## TESTING STRATEGY",
        "",
    ])
    lines.extend(f"- [ ] {item}" for item in rfc.testing_checklist)
    lines.extend([
        "",
        "## ROLLBACK PLAN",
        "",
        "Describe how this runtime behavior can be disabled or reverted without breaking existing parser, validator, codegen, formatter, and docs workflows.",
        "",
        "## ACCEPTANCE CRITERIA",
        "",
        "- [ ] Runtime boundary documentation updated.",
        "- [ ] New behavior is behind explicit CLI/runtime entrypoints.",
        "- [ ] Provider/tool calls are mocked in deterministic tests.",
        "- [ ] No secrets are printed, snapshotted, or included in traces.",
        "- [ ] Existing non-runtime commands remain non-executing.",
        "- [ ] Relevant docs and handoff commands are updated.",
        "",
        "## OPEN QUESTIONS",
        "",
        "- What remains intentionally deferred?",
        "- Which future RFC should handle the next runtime boundary?",
        "",
    ])
    return "\n".join(lines)


def runtime_rfc_to_json(rfc: RuntimeRFC) -> str:
    """Render a runtime RFC template as stable JSON."""
    return json.dumps(rfc.to_dict(), indent=2, sort_keys=True)


def write_runtime_rfc_template(path: str | Path, rfc: RuntimeRFC, *, json_output: bool = False) -> Path:
    """Write a runtime RFC template to disk and return the resolved destination."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = runtime_rfc_to_json(rfc) if json_output else format_runtime_rfc_template(rfc)
    destination.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return destination
