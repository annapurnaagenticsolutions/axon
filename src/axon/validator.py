"""Static validation for AXON Phase 1 declarations.

The parser intentionally preserves many AXON constructs as raw text. This module
performs lightweight semantic checks across the parsed declaration list before
code generation or runtime execution. It is deliberately conservative: it catches
clear project mistakes without pretending to be a full type checker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Iterable, Literal

from axon.ast_nodes import (
    AgentDecl,
    Annotation,
    FlowDecl,
    ImportDecl,
    PromptDecl,
    RagDecl,
    ToolDecl,
    TypeAliasDecl,
)

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Diagnostic:
    """A user-facing validation finding."""

    severity: Severity
    message: str
    line: int = 0
    code: str = ""
    hint: str = ""  # Fix-it hint or suggestion
    related: list[str] = field(default_factory=list)  # Related information

    def format(self) -> str:
        """Return a stable human-readable representation."""
        location = f"line {self.line}: " if self.line else ""
        code = f" [{self.code}]" if self.code else ""
        hint = f"\n  hint: {self.hint}" if self.hint else ""
        related = "\n  " + "\n  ".join(self.related) if self.related else ""
        return f"{self.severity}: {location}{self.message}{code}{hint}{related}"

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "code": self.code,
            "hint": self.hint,
            "related": self.related,
        }


class AxonValidationError(Exception):
    """Raised when validation produces one or more errors."""

    def __init__(self, diagnostics: Iterable[Diagnostic]):
        self.diagnostics = list(diagnostics)
        message = "AXON validation failed"
        if self.diagnostics:
            message += ":\n" + "\n".join(d.format() for d in self.diagnostics)
        super().__init__(message)


def validate(declarations: list, enable_type_check: bool = False, enable_token_budget: bool = True) -> list[Diagnostic]:
    """Validate parsed AXON declarations and return diagnostics.

    The function never raises for normal validation failures. Use
    ``validate_or_raise`` when a failing build should stop immediately.
    
    Args:
        declarations: Parsed AXON declaration list
        enable_type_check: If True, run type checker (default False for backward compatibility)
        enable_token_budget: If True, run token budget estimator (default True)
    """
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_duplicate_top_level_declarations(declarations))
    diagnostics.extend(_validate_imports(declarations))
    diagnostics.extend(_validate_tools(declarations))
    diagnostics.extend(_validate_agents(declarations))
    diagnostics.extend(_validate_prompts(declarations))
    diagnostics.extend(_validate_rags(declarations))
    diagnostics.extend(_validate_flows(declarations))
    
    if enable_type_check:
        try:
            from axon.type_checker import check_types
            diagnostics.extend(check_types(declarations))
        except ImportError:
            # Type checker is optional for backward compatibility
            pass
    
    if enable_token_budget:
        try:
            from axon.token_budget import check_token_budgets
            diagnostics.extend(check_token_budgets(declarations))
        except ImportError:
            # Token budget estimator is optional for backward compatibility
            pass
    
    return diagnostics


def validate_or_raise(declarations: list, warnings_as_errors: bool = False) -> None:
    """Validate declarations and raise AxonValidationError on failure."""
    diagnostics = validate(declarations)
    failing = [
        d
        for d in diagnostics
        if d.severity == "error" or (warnings_as_errors and d.severity == "warning")
    ]
    if failing:
        raise AxonValidationError(failing)


def diagnostics_to_json(diagnostics: Iterable[Diagnostic]) -> str:
    """Serialize diagnostics for CLI/tooling output."""
    return json.dumps([d.to_dict() for d in diagnostics], indent=2)


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    """Return True if any diagnostic is an error."""
    return any(d.severity == "error" for d in diagnostics)


def _validate_duplicate_top_level_declarations(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    seen: dict[str, tuple[str, int]] = {}

    for decl in declarations:
        name = _top_level_name(decl)
        if not name:
            continue
        kind = type(decl).__name__.replace("Decl", "")
        line = getattr(decl, "line", 0)
        previous = seen.get(name)
        if previous:
            prev_kind, prev_line = previous
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=(
                        f"duplicate declaration '{name}' conflicts with "
                        f"previous {prev_kind} declaration at line {prev_line}"
                    ),
                    line=line,
                    code="duplicate-declaration",
                    hint=f"Rename one of the '{name}' declarations to avoid the conflict.",
                )
            )
        else:
            seen[name] = (kind, line)

    return diagnostics


def _validate_imports(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    imported: dict[str, int] = {}

    for decl in declarations:
        if not isinstance(decl, ImportDecl):
            continue
        for name in decl.names:
            if name in imported:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        message=f"import '{name}' appears more than once",
                        line=0,
                        code="duplicate-import",
                    )
                )
            else:
                imported[name] = 0

    return diagnostics


def _validate_tools(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for tool in _of_type(declarations, ToolDecl):
        if not tool.docstrings:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=f"tool '{tool.name}' must include at least one /// docstring line",
                    line=tool.line,
                    code="missing-tool-docstring",
                    hint='Add a docstring using /// before the tool body, e.g., /// "Does something useful."',
                )
            )
        if any(not line.strip() for line in tool.docstrings):
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    message=f"tool '{tool.name}' contains an empty docstring line",
                    line=tool.line,
                    code="empty-tool-docstring-line",
                    hint="Remove empty /// lines or add descriptive text.",
                )
            )
        diagnostics.extend(_validate_annotations(tool.annotations, f"tool '{tool.name}'", tool.line))
    return diagnostics


def _validate_agents(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    known_tools = _known_tool_references(declarations)

    for agent in _of_type(declarations, AgentDecl):
        diagnostics.extend(_validate_annotations(agent.annotations, f"agent '{agent.name}'", agent.line))

        if not agent.model.strip():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=f"agent '{agent.name}' must declare a model",
                    line=agent.line,
                    code="missing-agent-model",
                    hint='Add a model declaration, e.g., model: @anthropic/claude-4',
                )
            )

        if not agent.methods:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=f"agent '{agent.name}' must define at least one method",
                    line=agent.line,
                    code="missing-agent-method",
                    hint='Add a method, e.g., fn run(query: Str) -> Str { ... }',
                )
            )

        seen_tool_refs: set[str] = set()
        for tool_ref in agent.tools:
            if tool_ref in seen_tool_refs:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        message=f"agent '{agent.name}' lists tool '{tool_ref}' more than once",
                        line=agent.line,
                        code="duplicate-agent-tool",
                    )
                )
            seen_tool_refs.add(tool_ref)

            if tool_ref not in known_tools:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message=f"agent '{agent.name}' references unknown tool '{tool_ref}'",
                        line=agent.line,
                        code="unknown-agent-tool",
                        hint=f"Define a tool named '{tool_ref}' or import it from axon:tools/",
                        related=[f"Available tools: {', '.join(sorted(known_tools))}"] if known_tools else [],
                    )
                )

        method_names: dict[str, int] = {}
        for method in agent.methods:
            if method.name in method_names:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message=(
                            f"agent '{agent.name}' has duplicate method '{method.name}' "
                            f"previously declared in the same agent"
                        ),
                        line=agent.line,
                        code="duplicate-agent-method",
                    )
                )
            else:
                method_names[method.name] = agent.line
            diagnostics.extend(
                _validate_annotations(method.annotations, f"method '{agent.name}.{method.name}'", agent.line)
            )

    return diagnostics


def _validate_prompts(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for prompt in _of_type(declarations, PromptDecl):
        diagnostics.extend(_validate_annotations(prompt.annotations, f"prompt '{prompt.name}'", prompt.line))
        diagnostics.extend(_validate_prompt_budget(prompt))
        diagnostics.extend(_validate_prompt_interpolations(prompt))

    return diagnostics


def _validate_rags(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for rag in _of_type(declarations, RagDecl):
        diagnostics.extend(_validate_annotations(rag.annotations, f"rag '{rag.name}'", rag.line))
        method_names: set[str] = set()
        for method in rag.methods:
            if method.name in method_names:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message=f"rag '{rag.name}' has duplicate method '{method.name}'",
                        line=rag.line,
                        code="duplicate-rag-method",
                    )
                )
            method_names.add(method.name)
            diagnostics.extend(
                _validate_annotations(method.annotations, f"method '{rag.name}.{method.name}'", rag.line)
            )

    return diagnostics


def _validate_flows(declarations: list) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for flow in _of_type(declarations, FlowDecl):
        diagnostics.extend(_validate_annotations(flow.annotations, f"flow '{flow.name}'", flow.line))

        stage_names: dict[str, int] = {}
        for stage in flow.stages:
            if stage.name in stage_names:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message=f"flow '{flow.name}' has duplicate stage '{stage.name}'",
                        line=stage.line or flow.line,
                        code="duplicate-flow-stage",
                    )
                )
            else:
                stage_names[stage.name] = stage.line or flow.line

        # Only validate simple arrow references. Complex expressions are preserved
        # for later phases and should not create noisy false positives yet.
        for ref in _simple_flow_stage_references(flow.body):
            if ref not in stage_names:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        message=f"flow '{flow.name}' references undeclared stage '{ref}'",
                        line=flow.line,
                        code="unknown-flow-stage",
                    )
                )

    return diagnostics


def _validate_prompt_budget(prompt: PromptDecl) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for annotation in prompt.annotations:
        if annotation.name != "budget":
            continue
        tokens = annotation.args.get("tokens")
        if tokens is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=f"prompt '{prompt.name}' @budget annotation requires tokens: N",
                    line=prompt.line,
                    code="missing-budget-tokens",
                )
            )
            continue
        if not re.fullmatch(r"[1-9][0-9]*", tokens.strip()):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=f"prompt '{prompt.name}' @budget tokens must be a positive integer",
                    line=prompt.line,
                    code="invalid-budget-tokens",
                )
            )
    return diagnostics


def _validate_prompt_interpolations(prompt: PromptDecl) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    param_names = {param.name for param in prompt.params}

    for expr in _template_interpolations(prompt.template):
        # Validate simple identifiers and dotted property paths. Ignore complex
        # expressions for now because AXON does not yet have an expression parser.
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\.[A-Za-z_][A-Za-z0-9_]*)*$", expr)
        if not match:
            continue
        root_name = match.group(1)
        if root_name not in param_names:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=(
                        f"prompt '{prompt.name}' references unknown template variable "
                        f"'{{{expr}}}'"
                    ),
                    line=prompt.line,
                    code="unknown-prompt-variable",
                )
            )
    return diagnostics


def _validate_annotations(
    annotations: list[Annotation], context: str, line: int
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    known = {"budget", "schedule", "trace", "managed", "retry", "timeout", "cache"}
    for annotation in annotations:
        if annotation.name not in known:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    message=f"{context} uses unknown annotation '@{annotation.name}'",
                    line=line,
                    code="unknown-annotation",
                )
            )
    return diagnostics


def _known_tool_references(declarations: list) -> set[str]:
    known: set[str] = set()

    for decl in declarations:
        if isinstance(decl, ToolDecl):
            known.add(decl.name)
        elif isinstance(decl, ImportDecl):
            known.update(decl.names)
        elif isinstance(decl, RagDecl):
            for method in decl.methods:
                known.add(f"{decl.name}.{method.name}")

    return known


def _simple_flow_stage_references(body: str) -> set[str]:
    refs: set[str] = set()
    identifier = r"[A-Za-z_][A-Za-z0-9_]*"

    for left, right in re.findall(rf"([^\n]+?)\s*->\s*([^\n]+)", body):
        refs.update(_extract_stage_refs_from_arrow_side(left, identifier))
        # Only read the immediate stage target before match/brace syntax.
        right_target = right.split("match", 1)[0].strip()
        refs.update(_extract_stage_refs_from_arrow_side(right_target, identifier))

    return refs


def _extract_stage_refs_from_arrow_side(text: str, identifier_pattern: str) -> set[str]:
    text = text.strip()
    if not text:
        return set()
    if text.startswith("[") and "]" in text:
        inside = text[1 : text.find("]")]
        return {part.strip() for part in inside.split(",") if re.fullmatch(identifier_pattern, part.strip())}
    first = text.split()[0].strip().strip(",")
    if re.fullmatch(identifier_pattern, first):
        return {first}
    return set()


def _template_interpolations(template: str) -> list[str]:
    results: list[str] = []
    pos = 0
    while pos < len(template):
        open_pos = template.find("{", pos)
        if open_pos == -1:
            break
        # Treat doubled braces as escaped literal braces.
        if open_pos + 1 < len(template) and template[open_pos + 1] == "{":
            pos = open_pos + 2
            continue
        close_pos = template.find("}", open_pos + 1)
        if close_pos == -1:
            break
        expr = template[open_pos + 1 : close_pos].strip()
        if expr:
            results.append(expr)
        pos = close_pos + 1
    return results


def _top_level_name(decl: object) -> str | None:
    if isinstance(decl, (ToolDecl, AgentDecl, TypeAliasDecl, PromptDecl, RagDecl, FlowDecl)):
        return decl.name
    return None


def _of_type(declarations: list, cls: type) -> list:
    return [decl for decl in declarations if isinstance(decl, cls)]
