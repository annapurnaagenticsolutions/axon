"""Canonical source formatting for AXON files.

The formatter is intentionally conservative for the Phase 1 prototype: it parses
AXON source into the existing AST and re-emits declarations in a stable,
human-readable style. It does not execute source, translate method bodies, or
attempt to preserve comments that are not part of the AST.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from axon.ast_nodes import (
    AgentDecl,
    Annotation,
    FlowDecl,
    ImportDecl,
    MemoryDecl,
    MethodDecl,
    Param,
    PromptDecl,
    RagDecl,
    StageDecl,
    ToolDecl,
    TypeAliasDecl,
)
from axon.parser import parse

DEFAULT_ENCODING = "utf-8"


@dataclass(frozen=True)
class FormatCheckResult:
    """Result of comparing AXON source against canonical formatting."""

    formatted: bool
    message: str
    formatted_source: str


def format_source(source: str) -> str:
    """Parse and return canonical AXON source text.

    The returned text always ends with one newline. Syntax errors from the parser
    are intentionally allowed to propagate so callers get the same diagnostics as
    other AXON commands.
    """
    return format_declarations(parse(source))


def format_file(path: str | Path) -> str:
    """Read an AXON source file and return its canonical formatting."""
    source_path = Path(path)
    return format_source(source_path.read_text(encoding=DEFAULT_ENCODING))


def write_formatted_file(path: str | Path) -> Path:
    """Format an AXON source file in place and return the path written."""
    source_path = Path(path)
    source_path.write_text(format_file(source_path), encoding=DEFAULT_ENCODING)
    return source_path


def check_format_source(source: str) -> FormatCheckResult:
    """Return whether source already matches canonical AXON formatting."""
    formatted = format_source(source)
    normalized_source = _normalize_file_end(source)
    matched = normalized_source == formatted
    return FormatCheckResult(
        formatted=matched,
        message="AXON source is already formatted" if matched else "AXON source is not formatted",
        formatted_source=formatted,
    )


def check_format_file(path: str | Path) -> FormatCheckResult:
    """Return whether a source file already matches canonical formatting."""
    source_path = Path(path)
    return check_format_source(source_path.read_text(encoding=DEFAULT_ENCODING))


def format_declarations(declarations: Iterable[object]) -> str:
    """Render parsed AXON declarations in canonical form."""
    chunks = [_format_declaration(decl) for decl in declarations]
    return _normalize_file_end("\n\n".join(chunk for chunk in chunks if chunk.strip()))


def format_annotation(annotation: Annotation) -> str:
    """Render one AXON annotation."""
    if not annotation.args:
        return f"@{annotation.name}"
    args = ", ".join(
        key if value == "" else f"{key}: {value}"
        for key, value in annotation.args.items()
    )
    return f"@{annotation.name}({args})"


def format_param(param: Param) -> str:
    """Render one typed parameter."""
    rendered = f"{param.name}: {param.type_str}"
    if param.default is not None:
        rendered += f" = {param.default}"
    return rendered


def format_params(params: Iterable[Param]) -> str:
    """Render an inline parameter list without surrounding parentheses."""
    return ", ".join(format_param(param) for param in params)


def _format_declaration(decl: object) -> str:
    if isinstance(decl, ImportDecl):
        return _format_import(decl)
    if isinstance(decl, TypeAliasDecl):
        return _format_type_alias(decl)
    if isinstance(decl, PromptDecl):
        return _format_prompt(decl)
    if isinstance(decl, ToolDecl):
        return _format_tool(decl)
    if isinstance(decl, RagDecl):
        return _format_rag(decl)
    if isinstance(decl, FlowDecl):
        return _format_flow(decl)
    if isinstance(decl, AgentDecl):
        return _format_agent(decl)
    raise TypeError(f"Unsupported AXON declaration: {type(decl).__name__}")


def _format_import(decl: ImportDecl) -> str:
    if len(decl.names) == 1:
        return f'import {decl.names[0]} from "{decl.source}"'
    return f'import {{ {", ".join(decl.names)} }} from "{decl.source}"'


def _format_type_alias(decl: TypeAliasDecl) -> str:
    params = f"<{', '.join(decl.type_params)}>" if decl.type_params else ""
    if decl.fields:
        lines = [f"type {decl.name}{params} = {{"]
        for field in decl.fields:
            lines.append(f"    {format_param(field)},")
        lines.append("}")
        return "\n".join(lines)
    return f"type {decl.name}{params} = {decl.value}"


def _format_prompt(decl: PromptDecl) -> str:
    prompt_items = [format_param(param) for param in decl.params]
    prompt_items.extend(format_annotation(annotation) for annotation in decl.annotations)
    params = ", ".join(prompt_items)
    lines = [f"prompt {decl.name}({params}) -> {decl.return_type} {{", '    """']
    if decl.template:
        lines.extend(_indent_lines(decl.template, 4))
    lines.extend(['    """', "}"])
    return "\n".join(lines)


def _format_tool(decl: ToolDecl) -> str:
    lines: list[str] = []
    lines.extend(format_annotation(annotation) for annotation in decl.annotations)
    lines.append(f"tool {decl.name}({format_params(decl.params)}) -> {decl.return_type} {{")
    for docstring in decl.docstrings:
        lines.append(f"    /// {docstring}" if docstring else "    ///")
    if decl.docstrings and decl.body:
        lines.append("")
    if decl.body:
        lines.extend(_indent_lines(decl.body, 4))
    lines.append("}")
    return "\n".join(lines)


def _format_rag(decl: RagDecl) -> str:
    lines: list[str] = []
    lines.extend(format_annotation(annotation) for annotation in decl.annotations)
    lines.append(f"rag {decl.name} {{")
    lines.append(f"    source: {decl.source}")
    lines.append(f"    chunker: {decl.chunker}")
    lines.append(f"    embedder: {decl.embedder}")
    lines.append(f"    store: {decl.store}")
    if decl.methods:
        lines.append("")
        for index, method in enumerate(decl.methods):
            if index:
                lines.append("")
            lines.extend(_indent_lines(_format_method(method), 4))
    lines.append("}")
    return "\n".join(lines)


def _format_flow(decl: FlowDecl) -> str:
    lines: list[str] = []
    lines.extend(format_annotation(annotation) for annotation in decl.annotations)
    lines.append(f"flow {decl.name}({format_params(decl.params)}) -> {decl.return_type} {{")
    for stage in decl.stages:
        lines.append(_indent(_format_stage(stage), 4))
    if decl.stages and decl.body:
        lines.append("")
    if decl.body:
        lines.extend(_indent_lines(decl.body, 4))
    lines.append("}")
    return "\n".join(lines)


def _format_agent(decl: AgentDecl) -> str:
    lines: list[str] = []
    lines.extend(format_annotation(annotation) for annotation in decl.annotations)
    lines.append(f"agent {decl.name} {{")
    lines.append(f"    model: {decl.model}")
    lines.append(f"    tools: [{', '.join(decl.tools)}]")
    if decl.memory is not None:
        lines.append(f"    memory: {_format_memory(decl.memory)}")
    if decl.methods:
        lines.append("")
        for index, method in enumerate(decl.methods):
            if index:
                lines.append("")
            lines.extend(_indent_lines(_format_method(method), 4))
    lines.append("}")
    return "\n".join(lines)


def _format_method(method: MethodDecl) -> str:
    lines: list[str] = []
    lines.extend(format_annotation(annotation) for annotation in method.annotations)
    lines.append(f"fn {method.name}({format_params(method.params)}) -> {method.return_type} {{")
    if method.body:
        lines.extend(_indent_lines(method.body, 4))
    lines.append("}")
    return "\n".join(lines)


def _format_stage(stage: StageDecl) -> str:
    return f"stage {stage.name}({format_params(stage.params)}) -> {stage.return_type}"


def _format_memory(memory: MemoryDecl) -> str:
    base = f"Memory<{memory.kind}>"
    if not memory.options:
        return base
    options = ", ".join(
        f"{key}: {value}" for key, value in memory.options.items()
    )
    return f"{base}({options})"


def _indent(text: str, spaces: int) -> str:
    return " " * spaces + text


def _indent_lines(text: str, spaces: int) -> list[str]:
    prefix = " " * spaces
    return [prefix + line if line else "" for line in text.splitlines()]


def _normalize_file_end(text: str) -> str:
    return text.rstrip() + "\n"
