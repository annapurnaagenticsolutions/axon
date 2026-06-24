"""AXON Intermediate Representation (IR) compiler.

Transforms `.ax` source files into portable `.axonir` JSON by walking
the parser AST and emitting a faithful IR representation.

Also provides IR-to-AST conversion so the Python runtime can consume IR
without a massive refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axon.ir_schema import (
    AgentDef,
    Annotation,
    AxonIR,
    FlowDef,
    FlowEdge,
    ImportDef,
    MemoryDecl,
    MethodDef,
    Param,
    PromptDef,
    ProviderRef,
    RagDef,
    StageDef,
    ToolDef,
    TypeAliasDef,
)


class IRCompileError(Exception):
    """Compilation from AXON source to IR failed."""
    pass


def compile_to_ir(source: Path) -> AxonIR:
    """Compile an AXON source file into IR.

    Args:
        source: Path to the `.ax` source file.

    Returns:
        Populated ``AxonIR`` instance.

    Raises:
        IRCompileError: On parse or validation failure.
    """
    text = source.read_text(encoding="utf-8")

    from axon.parser import parse
    from axon.validator import validate

    try:
        declarations = parse(text)
    except SyntaxError as exc:
        raise IRCompileError(f"Parse error in {source}: {exc}") from exc

    diagnostics = validate(declarations)
    errors = [d for d in diagnostics if d.severity == "error"]
    if errors:
        msgs = "\n".join(str(e) for e in errors)
        raise IRCompileError(f"Validation failed:\n{msgs}")

    ir = AxonIR(version="0.2.0")
    _extract_imports(declarations, ir)
    _extract_type_aliases(declarations, ir)
    _extract_rags(declarations, ir)
    _extract_prompts(declarations, ir)
    _extract_tools(declarations, ir)
    _extract_agents(declarations, ir)
    _extract_flows(declarations, ir)
    return ir


# ---------------------------------------------------------------------------
# Extraction helpers — one per AST node type
# ---------------------------------------------------------------------------


def _annotations_from_ast(annotations: list[Any]) -> list[Annotation]:
    return [
        Annotation(name=a.name, args=dict(a.args))
        for a in annotations
    ]


def _param_from_ast(p: Any) -> Param:
    return Param(
        name=p.name,
        type_str=p.type_str,
        default=p.default,
    )


def _method_from_ast(m: Any) -> MethodDef:
    return MethodDef(
        name=m.name,
        params=[_param_from_ast(p) for p in m.params],
        return_type=m.return_type,
        body=m.body,
        annotations=_annotations_from_ast(m.annotations),
    )


def _extract_imports(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import ImportDecl
    for decl in declarations:
        if isinstance(decl, ImportDecl):
            ir.imports.append(ImportDef(
                names=list(decl.names),
                source=decl.source,
            ))


def _extract_type_aliases(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import TypeAliasDecl
    for decl in declarations:
        if isinstance(decl, TypeAliasDecl):
            ir.type_aliases.append(TypeAliasDef(
                name=decl.name,
                type_params=list(decl.type_params),
                value=decl.value,
                fields=[_param_from_ast(p) for p in decl.fields],
            ))


def _extract_rags(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import RagDecl
    for decl in declarations:
        if isinstance(decl, RagDecl):
            ir.rags.append(RagDef(
                name=decl.name,
                source=decl.source,
                chunker=decl.chunker,
                embedder=decl.embedder,
                store=decl.store,
                methods=[_method_from_ast(m) for m in decl.methods],
                annotations=_annotations_from_ast(decl.annotations),
            ))


def _extract_prompts(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import PromptDecl
    for decl in declarations:
        if isinstance(decl, PromptDecl):
            ir.prompts.append(PromptDef(
                name=decl.name,
                params=[_param_from_ast(p) for p in decl.params],
                return_type=decl.return_type,
                template=decl.template,
                annotations=_annotations_from_ast(decl.annotations),
            ))


def _extract_tools(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import ToolDecl
    for decl in declarations:
        if isinstance(decl, ToolDecl):
            ir.tools.append(ToolDef(
                name=decl.name,
                params=[_param_from_ast(p) for p in decl.params],
                return_type=decl.return_type,
                docstrings=list(decl.docstrings),
                body=decl.body,
                annotations=_annotations_from_ast(decl.annotations),
            ))


def _extract_agents(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import AgentDecl
    for decl in declarations:
        if isinstance(decl, AgentDecl):
            memory = None
            if decl.memory is not None:
                memory = MemoryDecl(
                    kind=decl.memory.kind,
                    options=dict(decl.memory.options),
                )

            ir.agents.append(AgentDef(
                name=decl.name,
                model=(decl.model or "").lstrip("@"),
                tools=list(decl.tools),
                memory=memory,
                methods=[_method_from_ast(m) for m in decl.methods],
                annotations=_annotations_from_ast(decl.annotations),
                workers=decl.workers,
            ))


def _extract_flows(declarations: list[Any], ir: AxonIR) -> None:
    from axon.ast_nodes import FlowDecl
    for decl in declarations:
        if isinstance(decl, FlowDecl):
            stages = [
                StageDef(
                    name=s.name,
                    params=[_param_from_ast(p) for p in s.params],
                    return_type=s.return_type,
                )
                for s in decl.stages
            ]

            edges: list[FlowEdge] = []
            # Parse arrow syntax from flow body, e.g. "Research -> Write"
            body = decl.body or ""
            for line in body.splitlines():
                line = line.strip()
                if "->" in line and not line.startswith("//"):
                    parts = line.split("->")
                    if len(parts) == 2:
                        from_stage = parts[0].strip()
                        to_stage = parts[1].strip()
                        if from_stage and to_stage:
                            edges.append(FlowEdge(
                                from_stage=from_stage,
                                to_stage=to_stage,
                            ))

            ir.flows.append(FlowDef(
                name=decl.name,
                params=[_param_from_ast(p) for p in decl.params],
                return_type=decl.return_type,
                stages=stages,
                edges=edges,
                annotations=_annotations_from_ast(decl.annotations),
            ))


# ---------------------------------------------------------------------------
# IR → AST conversion (enables runtime to consume .axonir files)
# ---------------------------------------------------------------------------


def _annotation_to_ast(a: Annotation) -> Any:
    from axon.ast_nodes import Annotation as ASTAnnotation
    return ASTAnnotation(name=a.name, args=dict(a.args))


def _param_to_ast(p: Param) -> Any:
    from axon.ast_nodes import Param as ASTParam
    return ASTParam(name=p.name, type_str=p.type_str, default=p.default)


def _method_to_ast(m: MethodDef) -> Any:
    from axon.ast_nodes import MethodDecl
    parsed_body = None
    if m.body.strip():
        try:
            from axon.expression_parser import parse_expression
            parsed_body = parse_expression(m.body)
        except Exception:
            pass  # fall back to None; runtime will use _infer_body_expr
    return MethodDecl(
        name=m.name,
        params=[_param_to_ast(p) for p in m.params],
        return_type=m.return_type,
        annotations=[_annotation_to_ast(a) for a in m.annotations],
        body=m.body,
        parsed_body=parsed_body,
    )


def ir_to_ast(ir: AxonIR) -> list[Any]:
    """Convert an IR document back into a list of AST declarations.

    This lets the Python runtime consume `.axonir` files without a massive
    refactor.  The resulting AST objects are functionally identical to what
    ``parse()`` would produce (minus ``line`` numbers and ``parsed_body``).
    """
    declarations: list[Any] = []

    from axon.ast_nodes import (
        AgentDecl,
        FlowDecl,
        ImportDecl,
        MemoryDecl,
        PromptDecl,
        RagDecl,
        StageDecl,
        ToolDecl,
        TypeAliasDecl,
    )

    for imp in ir.imports:
        declarations.append(ImportDecl(names=list(imp.names), source=imp.source))

    for ta in ir.type_aliases:
        declarations.append(TypeAliasDecl(
            name=ta.name,
            type_params=list(ta.type_params),
            value=ta.value,
            fields=[_param_to_ast(p) for p in ta.fields],
            line=0,
        ))

    for rag in ir.rags:
        declarations.append(RagDecl(
            name=rag.name,
            source=rag.source,
            chunker=rag.chunker,
            embedder=rag.embedder,
            store=rag.store,
            annotations=[_annotation_to_ast(a) for a in rag.annotations],
            methods=[_method_to_ast(m) for m in rag.methods],
            line=0,
        ))

    for prompt in ir.prompts:
        declarations.append(PromptDecl(
            name=prompt.name,
            params=[_param_to_ast(p) for p in prompt.params],
            return_type=prompt.return_type,
            template=prompt.template,
            annotations=[_annotation_to_ast(a) for a in prompt.annotations],
            line=0,
        ))

    for tool in ir.tools:
        declarations.append(ToolDecl(
            name=tool.name,
            params=[_param_to_ast(p) for p in tool.params],
            return_type=tool.return_type,
            docstrings=list(tool.docstrings),
            body=tool.body,
            annotations=[_annotation_to_ast(a) for a in tool.annotations],
            line=0,
            parsed_body=None,
        ))

    for agent in ir.agents:
        memory = None
        if agent.memory is not None:
            memory = MemoryDecl(kind=agent.memory.kind, options=dict(agent.memory.options))

        declarations.append(AgentDecl(
            name=agent.name,
            model=agent.model,
            tools=list(agent.tools),
            memory=memory,
            annotations=[_annotation_to_ast(a) for a in agent.annotations],
            methods=[_method_to_ast(m) for m in agent.methods],
            workers=agent.workers,
            line=0,
        ))

    for flow in ir.flows:
        # Reconstruct arrow body from edges
        arrow_lines = [f"{e.from_stage} -> {e.to_stage}" for e in flow.edges]
        body = "\n".join(arrow_lines)

        declarations.append(FlowDecl(
            name=flow.name,
            params=[_param_to_ast(p) for p in flow.params],
            return_type=flow.return_type,
            annotations=[_annotation_to_ast(a) for a in flow.annotations],
            stages=[StageDecl(
                name=s.name,
                params=[_param_to_ast(p) for p in s.params],
                return_type=s.return_type,
                line=0,
            ) for s in flow.stages],
            body=body,
            parsed_body=None,
            line=0,
        ))

    return declarations


def load_ir(source: Path) -> AxonIR:
    """Load an ``.axonir`` JSON file into an ``AxonIR`` instance."""
    import json
    text = source.read_text(encoding="utf-8")
    data = json.loads(text)
    return AxonIR.from_dict(data)
