"""Non-executing AXON runtime plan data model.

This module implements the first concrete artifact from Runtime RFC #001: a
validated, inspection-only plan built from parsed AXON declarations. It does not
execute AXON method bodies, call providers, dispatch tools, mutate memory, index
RAG stores, execute flows, replay traces, resolve secrets, or import FastMCP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from axon.ast_nodes import (
    AgentDecl,
    Annotation,
    FlowDecl,
    ImportDecl,
    MethodDecl,
    Param,
    PromptDecl,
    RagDecl,
    StageDecl,
    ToolDecl,
    TypeAliasDecl,
)
from axon.parser import parse
from axon.validator import validate_or_raise

DEFAULT_ENCODING = "utf-8"


@dataclass(frozen=True)
class RuntimeCapability:
    """One runtime capability and whether it is currently enabled."""

    name: str
    enabled: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RuntimeParamPlan:
    """Inspection-safe summary of an AXON parameter or field."""

    name: str
    type_str: str
    default: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_str,
            "default": self.default,
        }


@dataclass(frozen=True)
class RuntimeMethodPlan:
    """Inspection-safe summary of an AXON method body."""

    name: str
    params: list[RuntimeParamPlan]
    return_type: str
    annotations: list[str]
    body_line_count: int
    has_body: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": [param.to_dict() for param in self.params],
            "return_type": self.return_type,
            "annotations": list(self.annotations),
            "body_line_count": self.body_line_count,
            "has_body": self.has_body,
        }


@dataclass(frozen=True)
class RuntimeToolPlan:
    """Inspection-safe summary of an AXON tool declaration."""

    name: str
    params: list[RuntimeParamPlan]
    return_type: str
    docstring_count: int
    annotations: list[str]
    body_line_count: int
    has_body: bool
    executable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": [param.to_dict() for param in self.params],
            "return_type": self.return_type,
            "docstring_count": self.docstring_count,
            "annotations": list(self.annotations),
            "body_line_count": self.body_line_count,
            "has_body": self.has_body,
            "executable": self.executable,
        }


@dataclass(frozen=True)
class RuntimePromptPlan:
    """Inspection-safe summary of a typed prompt declaration."""

    name: str
    params: list[RuntimeParamPlan]
    return_type: str
    annotations: list[str]
    template_line_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": [param.to_dict() for param in self.params],
            "return_type": self.return_type,
            "annotations": list(self.annotations),
            "template_line_count": self.template_line_count,
        }


@dataclass(frozen=True)
class RuntimeTypeAliasPlan:
    """Inspection-safe summary of a type alias declaration."""

    name: str
    type_params: list[str]
    value: str
    field_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type_params": list(self.type_params),
            "value": self.value,
            "field_count": self.field_count,
        }


@dataclass(frozen=True)
class RuntimeAgentPlan:
    """Inspection-safe summary of an AXON agent declaration."""

    name: str
    model: str
    tools: list[str]
    memory_kind: str | None
    memory_options: dict[str, str]
    annotations: list[str]
    methods: list[RuntimeMethodPlan]
    executable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "tools": list(self.tools),
            "memory_kind": self.memory_kind,
            "memory_options": dict(self.memory_options),
            "annotations": list(self.annotations),
            "methods": [method.to_dict() for method in self.methods],
            "executable": self.executable,
        }


@dataclass(frozen=True)
class RuntimeRagPlan:
    """Inspection-safe summary of a RAG declaration."""

    name: str
    source: str
    chunker: str
    embedder: str
    store: str
    annotations: list[str]
    methods: list[RuntimeMethodPlan]
    indexing_enabled: bool = False
    retrieval_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "chunker": self.chunker,
            "embedder": self.embedder,
            "store": self.store,
            "annotations": list(self.annotations),
            "methods": [method.to_dict() for method in self.methods],
            "indexing_enabled": self.indexing_enabled,
            "retrieval_enabled": self.retrieval_enabled,
        }


@dataclass(frozen=True)
class RuntimeStagePlan:
    """Inspection-safe summary of a flow stage declaration."""

    name: str
    params: list[RuntimeParamPlan]
    return_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": [param.to_dict() for param in self.params],
            "return_type": self.return_type,
        }


@dataclass(frozen=True)
class RuntimeFlowPlan:
    """Inspection-safe summary of a flow declaration."""

    name: str
    params: list[RuntimeParamPlan]
    return_type: str
    annotations: list[str]
    stages: list[RuntimeStagePlan]
    body_line_count: int
    executable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": [param.to_dict() for param in self.params],
            "return_type": self.return_type,
            "annotations": list(self.annotations),
            "stages": [stage.to_dict() for stage in self.stages],
            "body_line_count": self.body_line_count,
            "executable": self.executable,
        }


@dataclass(frozen=True)
class RuntimePlan:
    """Validated, non-executing runtime plan for parsed AXON declarations."""

    source_path: str | None
    imports: list[dict[str, Any]] = field(default_factory=list)
    type_aliases: list[RuntimeTypeAliasPlan] = field(default_factory=list)
    prompts: list[RuntimePromptPlan] = field(default_factory=list)
    tools: list[RuntimeToolPlan] = field(default_factory=list)
    agents: list[RuntimeAgentPlan] = field(default_factory=list)
    rags: list[RuntimeRagPlan] = field(default_factory=list)
    flows: list[RuntimeFlowPlan] = field(default_factory=list)
    capabilities: list[RuntimeCapability] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """Return deterministic declaration counts for the plan."""
        return {
            "imports": len(self.imports),
            "type_aliases": len(self.type_aliases),
            "prompts": len(self.prompts),
            "tools": len(self.tools),
            "agents": len(self.agents),
            "rags": len(self.rags),
            "flows": len(self.flows),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable, secret-safe representation."""
        return {
            "source_path": self.source_path,
            "counts": self.counts(),
            "imports": list(self.imports),
            "type_aliases": [item.to_dict() for item in self.type_aliases],
            "prompts": [item.to_dict() for item in self.prompts],
            "tools": [item.to_dict() for item in self.tools],
            "agents": [item.to_dict() for item in self.agents],
            "rags": [item.to_dict() for item in self.rags],
            "flows": [item.to_dict() for item in self.flows],
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "notes": list(self.notes),
        }


def build_runtime_plan(declarations: list[Any], *, source_path: str | Path | None = None) -> RuntimePlan:
    """Build a non-executing runtime plan from parsed declarations.

    The caller is expected to pass declarations that already parsed correctly.
    This function performs only inspection and serialization-friendly summary
    construction. It deliberately does not validate, execute, dispatch, import
    provider SDKs, resolve secrets, or import FastMCP.
    """
    imports: list[dict[str, Any]] = []
    type_aliases: list[RuntimeTypeAliasPlan] = []
    prompts: list[RuntimePromptPlan] = []
    tools: list[RuntimeToolPlan] = []
    agents: list[RuntimeAgentPlan] = []
    rags: list[RuntimeRagPlan] = []
    flows: list[RuntimeFlowPlan] = []

    for declaration in declarations:
        if isinstance(declaration, ImportDecl):
            imports.append({"names": list(declaration.names), "source": declaration.source})
        elif isinstance(declaration, TypeAliasDecl):
            type_aliases.append(
                RuntimeTypeAliasPlan(
                    name=declaration.name,
                    type_params=list(declaration.type_params),
                    value=declaration.value,
                    field_count=len(declaration.fields),
                )
            )
        elif isinstance(declaration, PromptDecl):
            prompts.append(_prompt_plan(declaration))
        elif isinstance(declaration, ToolDecl):
            tools.append(_tool_plan(declaration))
        elif isinstance(declaration, AgentDecl):
            agents.append(_agent_plan(declaration))
        elif isinstance(declaration, RagDecl):
            rags.append(_rag_plan(declaration))
        elif isinstance(declaration, FlowDecl):
            flows.append(_flow_plan(declaration))

    return RuntimePlan(
        source_path=str(source_path) if source_path is not None else None,
        imports=imports,
        type_aliases=type_aliases,
        prompts=prompts,
        tools=tools,
        agents=agents,
        rags=rags,
        flows=flows,
        capabilities=default_runtime_capabilities(),
        notes=[
            "runtime plan is inspection-only",
            "all executable capabilities remain disabled by Runtime RFC #001",
        ],
    )


def build_runtime_plan_from_source(source: str, *, source_path: str | Path | None = None) -> RuntimePlan:
    """Parse, validate, and summarize AXON source without executing it."""
    declarations = parse(source)
    validate_or_raise(declarations)
    return build_runtime_plan(declarations, source_path=source_path)


def build_runtime_plan_from_file(path: str | Path) -> RuntimePlan:
    """Read an AXON file and build a validated non-executing runtime plan."""
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"source file not found: {source_path}")
    if not source_path.is_file():
        raise IsADirectoryError(f"source path is not a file: {source_path}")
    return build_runtime_plan_from_source(
        source_path.read_text(encoding=DEFAULT_ENCODING),
        source_path=source_path,
    )


def runtime_plan_to_json(plan: RuntimePlan) -> str:
    """Render a runtime plan as stable JSON."""
    return json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"


def format_runtime_plan(plan: RuntimePlan) -> str:
    """Render a runtime plan for humans."""
    counts = plan.counts()
    lines = [
        "AXON runtime plan (non-executing)",
        f"Source: {plan.source_path if plan.source_path else '<memory>'}",
        "Declarations:",
        f"  Imports: {counts['imports']}",
        f"  Type aliases: {counts['type_aliases']}",
        f"  Prompts: {counts['prompts']}",
        f"  Tools: {counts['tools']}",
        f"  Agents: {counts['agents']}",
        f"  RAG blocks: {counts['rags']}",
        f"  Flows: {counts['flows']}",
    ]

    if plan.agents:
        lines.append("Agents:")
        for agent in plan.agents:
            memory = agent.memory_kind if agent.memory_kind else "<none>"
            tools = ", ".join(agent.tools) if agent.tools else "<none>"
            lines.append(f"  - {agent.name}: model={agent.model}, tools={tools}, memory={memory}, methods={len(agent.methods)}")

    if plan.tools:
        lines.append("Tools:")
        for tool in plan.tools:
            lines.append(f"  - {tool.name}: params={len(tool.params)}, return={tool.return_type}, executable=no")

    if plan.rags:
        lines.append("RAG blocks:")
        for rag in plan.rags:
            lines.append(f"  - {rag.name}: indexing=disabled, retrieval=disabled, methods={len(rag.methods)}")

    if plan.flows:
        lines.append("Flows:")
        for flow in plan.flows:
            lines.append(f"  - {flow.name}: stages={len(flow.stages)}, executable=no")

    lines.append("Capabilities:")
    for capability in plan.capabilities:
        status = "enabled" if capability.enabled else "disabled"
        lines.append(f"  - {capability.name}: {status} — {capability.reason}")

    if plan.notes:
        lines.append("Notes:")
        lines.extend(f"  - {note}" for note in plan.notes)

    return "\n".join(lines)


def default_runtime_capabilities() -> list[RuntimeCapability]:
    """Return the Runtime RFC #001 capability boundary."""
    return [
        RuntimeCapability("declaration_inspection", True, "safe parsed declaration summaries are allowed"),
        RuntimeCapability("method_execution", False, "AXON method bodies are not executed yet"),
        RuntimeCapability("provider_calls", False, "model/provider calls require a future provider runtime RFC"),
        RuntimeCapability("tool_dispatch", False, "real tool dispatch requires a future tool runtime RFC"),
        RuntimeCapability("memory_mutation", False, "memory writes are not applied by the current runtime plan"),
        RuntimeCapability("rag_indexing", False, "RAG indexing is outside Runtime RFC #001"),
        RuntimeCapability("rag_retrieval", False, "RAG retrieval is outside Runtime RFC #001"),
        RuntimeCapability("flow_execution", False, "flow orchestration is outside Runtime RFC #001"),
        RuntimeCapability("trace_replay", False, "trace replay is outside Runtime RFC #001"),
        RuntimeCapability("secret_resolution", False, "environment secrets are not resolved by runtime planning"),
        RuntimeCapability("fastmcp_runtime_import", False, "FastMCP is not imported by compiler/runtime planning core"),
    ]


def _param_plan(param: Param) -> RuntimeParamPlan:
    return RuntimeParamPlan(name=param.name, type_str=param.type_str, default=param.default)


def _annotation_names(annotations: list[Annotation]) -> list[str]:
    return [annotation.name for annotation in annotations]


def _body_line_count(body: str) -> int:
    if not body.strip():
        return 0
    return len([line for line in body.splitlines() if line.strip()])


def _method_plan(method: MethodDecl) -> RuntimeMethodPlan:
    return RuntimeMethodPlan(
        name=method.name,
        params=[_param_plan(param) for param in method.params],
        return_type=method.return_type,
        annotations=_annotation_names(method.annotations),
        body_line_count=_body_line_count(method.body),
        has_body=bool(method.body.strip()),
    )


def _tool_plan(tool: ToolDecl) -> RuntimeToolPlan:
    return RuntimeToolPlan(
        name=tool.name,
        params=[_param_plan(param) for param in tool.params],
        return_type=tool.return_type,
        docstring_count=len(tool.docstrings),
        annotations=_annotation_names(tool.annotations),
        body_line_count=_body_line_count(tool.body),
        has_body=bool(tool.body.strip()),
    )


def _prompt_plan(prompt: PromptDecl) -> RuntimePromptPlan:
    return RuntimePromptPlan(
        name=prompt.name,
        params=[_param_plan(param) for param in prompt.params],
        return_type=prompt.return_type,
        annotations=_annotation_names(prompt.annotations),
        template_line_count=_body_line_count(prompt.template),
    )


def _agent_plan(agent: AgentDecl) -> RuntimeAgentPlan:
    return RuntimeAgentPlan(
        name=agent.name,
        model=agent.model,
        tools=list(agent.tools),
        memory_kind=agent.memory.kind if agent.memory else None,
        memory_options=dict(agent.memory.options) if agent.memory else {},
        annotations=_annotation_names(agent.annotations),
        methods=[_method_plan(method) for method in agent.methods],
    )


def _rag_plan(rag: RagDecl) -> RuntimeRagPlan:
    return RuntimeRagPlan(
        name=rag.name,
        source=rag.source,
        chunker=rag.chunker,
        embedder=rag.embedder,
        store=rag.store,
        annotations=_annotation_names(rag.annotations),
        methods=[_method_plan(method) for method in rag.methods],
    )


def _stage_plan(stage: StageDecl) -> RuntimeStagePlan:
    return RuntimeStagePlan(
        name=stage.name,
        params=[_param_plan(param) for param in stage.params],
        return_type=stage.return_type,
    )


def _flow_plan(flow: FlowDecl) -> RuntimeFlowPlan:
    return RuntimeFlowPlan(
        name=flow.name,
        params=[_param_plan(param) for param in flow.params],
        return_type=flow.return_type,
        annotations=_annotation_names(flow.annotations),
        stages=[_stage_plan(stage) for stage in flow.stages],
        body_line_count=_body_line_count(flow.body),
    )
