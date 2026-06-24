"""AXON Intermediate Representation (IR) schema v0.2.

This module defines the portable, language-agnostic IR that all AXON
runtimes consume. After deep analysis of the parser, AST, runtime, and
all example files, the IR is a *faithful serialization of the AST* —
every language construct has an IR counterpart.

Design principles:
- IR is fully serializable to JSON
- No construct is simplified or omitted (lossless AST → IR)
- Security policies are first-class (not runtime-specific)
- Backends are referenced by ID, resolved at runtime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JSONValue = str | int | float | bool | None | list[Any] | dict[str, Any]


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

@dataclass
class Annotation:
    """Top-level or declaration annotation, e.g. @budget(tokens: 900)."""

    name: str = ""
    args: dict[str, str] = field(default_factory=dict)


@dataclass
class Param:
    """Typed parameter with optional default value."""

    name: str = ""
    type_str: str = ""  # raw AXON type string, e.g. "Str", "List<Int> = 5"
    default: str | None = None


@dataclass
class MethodDef:
    """Method / function definition inside an agent, RAG, or standalone."""

    name: str = ""
    params: list[Param] = field(default_factory=list)
    return_type: str = ""
    body: str = ""  # raw expression body text
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class MemoryDecl:
    """Memory declaration, e.g. Memory<Semantic>."""

    kind: str = ""
    options: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Import & Type Alias
# ---------------------------------------------------------------------------

@dataclass
class ImportDef:
    """Import declaration: import { Names } from "source"."""

    kind: str = "import"
    names: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class TypeAliasDef:
    """Type alias declaration: type Name<T> = { ... }."""

    kind: str = "type_alias"
    name: str = ""
    type_params: list[str] = field(default_factory=list)
    value: str = ""  # raw right-hand side
    fields: list[Param] = field(default_factory=list)


# ---------------------------------------------------------------------------
# RAG Definition
# ---------------------------------------------------------------------------

@dataclass
class RagDef:
    """RAG pipeline declaration with source, chunker, embedder, store, methods."""

    kind: str = "rag"
    name: str = ""
    source: str = ""  # raw source expression
    chunker: str = ""  # raw chunker expression
    embedder: str = ""  # raw embedder expression
    store: str = ""  # raw store expression
    methods: list[MethodDef] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt Definition
# ---------------------------------------------------------------------------

@dataclass
class PromptDef:
    """Prompt template declaration with typed inputs and triple-quoted body."""

    kind: str = "prompt"
    name: str = ""
    params: list[Param] = field(default_factory=list)
    return_type: str = ""
    template: str = ""  # dedented template body
    annotations: list[Annotation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool Definition
# ---------------------------------------------------------------------------

@dataclass
class ToolDef:
    """Tool declaration with params, return type, docstrings, and body."""

    kind: str = "tool"
    name: str = ""
    params: list[Param] = field(default_factory=list)
    return_type: str = ""
    docstrings: list[str] = field(default_factory=list)
    body: str = ""
    annotations: list[Annotation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent Definition
# ---------------------------------------------------------------------------

@dataclass
class ProviderRef:
    """Reference to a provider backend, resolved at runtime."""

    id: str = ""  # e.g. "anthropic/claude-4" (without @ prefix)
    config: dict[str, JSONValue] = field(default_factory=dict)


@dataclass
class AgentDef:
    """Agent declaration with model, tools, memory, methods, annotations."""

    kind: str = "agent"
    name: str = ""
    model: str = ""  # e.g. "anthropic/claude-4" (without @ prefix)
    tools: list[str] = field(default_factory=list)
    memory: MemoryDecl | None = None
    methods: list[MethodDef] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    workers: str | None = None


# ---------------------------------------------------------------------------
# Flow Definition
# ---------------------------------------------------------------------------

@dataclass
class StageDef:
    """Stage inside a flow declaration."""

    name: str = ""
    params: list[Param] = field(default_factory=list)
    return_type: str = ""


@dataclass
class FlowEdge:
    """Directed edge between stages in a flow."""

    from_stage: str = ""
    to_stage: str = ""


@dataclass
class FlowDef:
    """Flow declaration: a DAG of stages with param types and edges."""

    kind: str = "flow"
    name: str = ""
    params: list[Param] = field(default_factory=list)
    return_type: str = ""
    stages: list[StageDef] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

@dataclass
class CapabilityRule:
    """Capability-based access rule."""

    resource: str = ""
    action: str = ""  # "allow" | "deny"


@dataclass
class ApprovalGate:
    """Human-in-the-loop approval requirement."""

    tool_id: str = ""
    timeout_seconds: int = 300
    approver_role: str | None = None


@dataclass
class SecurityPolicy:
    """Security policy attached to an agent or global scope."""

    capabilities: list[CapabilityRule] = field(default_factory=list)
    approval_gates: list[ApprovalGate] = field(default_factory=list)
    max_token_budget: int | None = None
    max_cost_budget_usd: float | None = None


# ---------------------------------------------------------------------------
# Top-level IR Document
# ---------------------------------------------------------------------------

@dataclass
class AxonIR:
    """Top-level AXON Intermediate Representation document (v0.2)."""

    version: str = "0.2.0"
    imports: list[ImportDef] = field(default_factory=list)
    type_aliases: list[TypeAliasDef] = field(default_factory=list)
    rags: list[RagDef] = field(default_factory=list)
    prompts: list[PromptDef] = field(default_factory=list)
    tools: list[ToolDef] = field(default_factory=list)
    agents: list[AgentDef] = field(default_factory=list)
    flows: list[FlowDef] = field(default_factory=list)
    global_security: SecurityPolicy = field(default_factory=SecurityPolicy)
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize IR to a plain dict (JSON-ready)."""
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AxonIR":
        """Deserialize IR from a plain dict.

        Explicit reconstruction without type introspection (avoids issues
        with ``from __future__ import annotations`` string annotations).
        """

        def _annotation(d: dict[str, Any]) -> Annotation:
            return Annotation(name=d.get("name", ""), args=d.get("args", {}))

        def _param(d: dict[str, Any]) -> Param:
            return Param(
                name=d.get("name", ""),
                type_str=d.get("type_str", ""),
                default=d.get("default"),
            )

        def _method_def(d: dict[str, Any]) -> MethodDef:
            return MethodDef(
                name=d.get("name", ""),
                params=[_param(p) for p in d.get("params", [])],
                return_type=d.get("return_type", ""),
                body=d.get("body", ""),
                annotations=[_annotation(a) for a in d.get("annotations", [])],
            )

        def _memory_decl(d: dict[str, Any] | None) -> MemoryDecl | None:
            if d is None:
                return None
            return MemoryDecl(kind=d.get("kind", ""), options=d.get("options", {}))

        def _import_def(d: dict[str, Any]) -> ImportDef:
            return ImportDef(
                kind=d.get("kind", "import"),
                names=d.get("names", []),
                source=d.get("source", ""),
            )

        def _type_alias_def(d: dict[str, Any]) -> TypeAliasDef:
            return TypeAliasDef(
                kind=d.get("kind", "type_alias"),
                name=d.get("name", ""),
                type_params=d.get("type_params", []),
                value=d.get("value", ""),
                fields=[_param(p) for p in d.get("fields", [])],
            )

        def _rag_def(d: dict[str, Any]) -> RagDef:
            return RagDef(
                kind=d.get("kind", "rag"),
                name=d.get("name", ""),
                source=d.get("source", ""),
                chunker=d.get("chunker", ""),
                embedder=d.get("embedder", ""),
                store=d.get("store", ""),
                methods=[_method_def(m) for m in d.get("methods", [])],
                annotations=[_annotation(a) for a in d.get("annotations", [])],
            )

        def _prompt_def(d: dict[str, Any]) -> PromptDef:
            return PromptDef(
                kind=d.get("kind", "prompt"),
                name=d.get("name", ""),
                params=[_param(p) for p in d.get("params", [])],
                return_type=d.get("return_type", ""),
                template=d.get("template", ""),
                annotations=[_annotation(a) for a in d.get("annotations", [])],
            )

        def _tool_def(d: dict[str, Any]) -> ToolDef:
            return ToolDef(
                kind=d.get("kind", "tool"),
                name=d.get("name", ""),
                params=[_param(p) for p in d.get("params", [])],
                return_type=d.get("return_type", ""),
                docstrings=d.get("docstrings", []),
                body=d.get("body", ""),
                annotations=[_annotation(a) for a in d.get("annotations", [])],
            )

        def _provider_ref(d: dict[str, Any] | None) -> ProviderRef | None:
            if d is None:
                return None
            return ProviderRef(id=d.get("id", ""), config=d.get("config", {}))

        def _agent_def(d: dict[str, Any]) -> AgentDef:
            return AgentDef(
                kind=d.get("kind", "agent"),
                name=d.get("name", ""),
                model=d.get("model", ""),
                tools=d.get("tools", []),
                memory=_memory_decl(d.get("memory")),
                methods=[_method_def(m) for m in d.get("methods", [])],
                annotations=[_annotation(a) for a in d.get("annotations", [])],
                workers=d.get("workers"),
            )

        def _stage_def(d: dict[str, Any]) -> StageDef:
            return StageDef(
                name=d.get("name", ""),
                params=[_param(p) for p in d.get("params", [])],
                return_type=d.get("return_type", ""),
            )

        def _flow_edge(d: dict[str, Any]) -> FlowEdge:
            return FlowEdge(
                from_stage=d.get("from_stage", ""),
                to_stage=d.get("to_stage", ""),
            )

        def _flow_def(d: dict[str, Any]) -> FlowDef:
            return FlowDef(
                kind=d.get("kind", "flow"),
                name=d.get("name", ""),
                params=[_param(p) for p in d.get("params", [])],
                return_type=d.get("return_type", ""),
                stages=[_stage_def(s) for s in d.get("stages", [])],
                edges=[_flow_edge(e) for e in d.get("edges", [])],
                annotations=[_annotation(a) for a in d.get("annotations", [])],
            )

        def _cap_rule(d: dict[str, Any]) -> CapabilityRule:
            return CapabilityRule(resource=d.get("resource", ""), action=d.get("action", ""))

        def _approval_gate(d: dict[str, Any]) -> ApprovalGate:
            return ApprovalGate(
                tool_id=d.get("tool_id", ""),
                timeout_seconds=d.get("timeout_seconds", 300),
                approver_role=d.get("approver_role"),
            )

        def _security_policy(d: dict[str, Any]) -> SecurityPolicy:
            return SecurityPolicy(
                capabilities=[_cap_rule(c) for c in d.get("capabilities", [])],
                approval_gates=[_approval_gate(a) for a in d.get("approval_gates", [])],
                max_token_budget=d.get("max_token_budget"),
                max_cost_budget_usd=d.get("max_cost_budget_usd"),
            )

        return cls(
            version=data.get("version", "0.2.0"),
            imports=[_import_def(i) for i in data.get("imports", [])],
            type_aliases=[_type_alias_def(t) for t in data.get("type_aliases", [])],
            rags=[_rag_def(r) for r in data.get("rags", [])],
            prompts=[_prompt_def(p) for p in data.get("prompts", [])],
            tools=[_tool_def(t) for t in data.get("tools", [])],
            agents=[_agent_def(a) for a in data.get("agents", [])],
            flows=[_flow_def(f) for f in data.get("flows", [])],
            global_security=_security_policy(data.get("global_security", {})),
            metadata=data.get("metadata", {}),
        )
