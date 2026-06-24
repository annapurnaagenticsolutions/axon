"""Documentation generator for AXON declarations.

This module generates documentation from AXON source files, extracting
docstrings, type signatures, and other metadata to produce human-readable
documentation in Markdown format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from axon.parser import parse
from axon.ast_nodes import (
    AgentDecl,
    ToolDecl,
    PromptDecl,
    RagDecl,
    FlowDecl,
    TypeAliasDecl,
)


@dataclass
class DocumentationSection:
    """A section of generated documentation."""
    title: str
    content: str
    level: int = 2  # Markdown heading level


def generate_docs(source: str, source_path: Optional[str] = None) -> str:
    """Generate Markdown documentation from AXON source.
    
    Args:
        source: AXON source code
        source_path: Optional source file path for reference
        
    Returns:
        Markdown documentation string
    """
    declarations = parse(source)
    sections: list[DocumentationSection] = []
    
    # Add title
    if source_path:
        title = Path(source_path).stem.replace("_", " ").title()
        sections.append(DocumentationSection(title, f"# {title}\n", level=1))
    
    # Group declarations by type
    tools = [d for d in declarations if isinstance(d, ToolDecl)]
    agents = [d for d in declarations if isinstance(d, AgentDecl)]
    prompts = [d for d in declarations if isinstance(d, PromptDecl)]
    rags = [d for d in declarations if isinstance(d, RagDecl)]
    flows = [d for d in declarations if isinstance(d, FlowDecl)]
    type_aliases = [d for d in declarations if isinstance(d, TypeAliasDecl)]
    
    # Generate sections for each type
    if tools:
        sections.append(_generate_tools_section(tools))
    
    if agents:
        sections.append(_generate_agents_section(agents))
    
    if prompts:
        sections.append(_generate_prompts_section(prompts))
    
    if rags:
        sections.append(_generate_rags_section(rags))
    
    if flows:
        sections.append(_generate_flows_section(flows))
    
    if type_aliases:
        sections.append(_generate_type_aliases_section(type_aliases))
    
    # Combine all sections
    return "\n\n".join(section.content for section in sections)


def _generate_tools_section(tools: list[ToolDecl]) -> DocumentationSection:
    """Generate documentation for tools."""
    content = "## Tools\n\n"
    
    for tool in tools:
        content += f"### `{tool.name}`\n\n"
        
        # Add docstring
        if tool.docstrings:
            docstring = "\n".join(tool.docstrings)
            content += f"{docstring}\n\n"
        
        # Add signature
        params = ", ".join(f"{p.name}: {p.type_str}" for p in tool.params)
        content += f"**Signature:** `{tool.name}({params}) -> {tool.return_type}`\n\n"
        
        # Add annotations
        if tool.annotations:
            content += "**Annotations:**\n"
            for ann in tool.annotations:
                args_str = ", ".join(f"{k}={v}" for k, v in ann.args.items())
                content += f"- `@{ann.name}`({args_str})\n"
            content += "\n"
    
    return DocumentationSection("Tools", content, level=2)


def _generate_agents_section(agents: list[AgentDecl]) -> DocumentationSection:
    """Generate documentation for agents."""
    content = "## Agents\n\n"
    
    for agent in agents:
        content += f"### `{agent.name}`\n\n"
        
        # Add model
        content += f"**Model:** `{agent.model}`\n\n"
        
        # Add tools
        if agent.tools:
            tools_str = ", ".join(f"`{t}`" for t in agent.tools)
            content += f"**Tools:** {tools_str}\n\n"
        
        # Add methods
        if agent.methods:
            content += "**Methods:**\n\n"
            for method in agent.methods:
                params = ", ".join(f"{p.name}: {p.type_str}" for p in method.params)
                content += f"- `{method.name}({params}) -> {method.return_type}`\n"
            content += "\n"
    
    return DocumentationSection("Agents", content, level=2)


def _generate_prompts_section(prompts: list[PromptDecl]) -> DocumentationSection:
    """Generate documentation for prompts."""
    content = "## Prompts\n\n"
    
    for prompt in prompts:
        content += f"### `{prompt.name}`\n\n"
        
        # Add template
        if prompt.template:
            content += f"**Template:**\n```\n{prompt.template}\n```\n\n"
        
        # Add signature
        params = ", ".join(f"{p.name}: {p.type_str}" for p in prompt.params)
        content += f"**Signature:** `{prompt.name}({params}) -> {prompt.return_type}`\n\n"
        
        # Add annotations
        if prompt.annotations:
            content += "**Annotations:**\n"
            for ann in prompt.annotations:
                args_str = ", ".join(f"{k}={v}" for k, v in ann.args.items())
                content += f"- `@{ann.name}`({args_str})\n"
            content += "\n"
    
    return DocumentationSection("Prompts", content, level=2)


def _generate_rags_section(rags: list[RagDecl]) -> DocumentationSection:
    """Generate documentation for RAG declarations."""
    content = "## RAG\n\n"
    
    for rag in rags:
        content += f"### `{rag.name}`\n\n"
        
        # Add source
        content += f"**Source:** `{rag.source}`\n\n"
        
        # Add chunker
        if rag.chunker:
            content += f"**Chunker:** `{rag.chunker}`\n\n"
        
        # Add embedder
        if rag.embedder:
            content += f"**Embedder:** `{rag.embedder}`\n\n"
        
        # Add store
        if rag.store:
            content += f"**Store:** `{rag.store}`\n\n"
        
        # Add methods
        if rag.methods:
            content += "**Methods:**\n\n"
            for method in rag.methods:
                params = ", ".join(f"{p.name}: {p.type_str}" for p in method.params)
                content += f"- `{method.name}({params}) -> {method.return_type}`\n"
            content += "\n"
    
    return DocumentationSection("RAG", content, level=2)


def _generate_flows_section(flows: list[FlowDecl]) -> DocumentationSection:
    """Generate documentation for flow declarations."""
    content = "## Flows\n\n"
    
    for flow in flows:
        content += f"### `{flow.name}`\n\n"
        
        # Add signature
        params = ", ".join(f"{p.name}: {p.type_str}" for p in flow.params)
        content += f"**Signature:** `{flow.name}({params}) -> {flow.return_type}`\n\n"
        
        # Add stages
        if flow.stages:
            content += "**Stages:**\n\n"
            for stage in flow.stages:
                params = ", ".join(f"{p.name}: {p.type_str}" for p in stage.params)
                content += f"- `{stage.name}({params}) -> {stage.return_type}`\n"
            content += "\n"
    
    return DocumentationSection("Flows", content, level=2)


def _generate_type_aliases_section(type_aliases: list[TypeAliasDecl]) -> DocumentationSection:
    """Generate documentation for type aliases."""
    content = "## Type Aliases\n\n"
    
    for alias in type_aliases:
        content += f"### `{alias.name}`\n\n"
        
        # Add type
        content += f"**Type:** `{alias.value}`\n\n"
        
        # Add fields if it's a record
        if alias.fields:
            content += "**Fields:**\n\n"
            for field in alias.fields:
                content += f"- `{field.name}: {field.type_str}`\n"
            content += "\n"
    
    return DocumentationSection("Type Aliases", content, level=2)


def generate_docs_file(source_path: str, output_path: str) -> None:
    """Generate documentation from an AXON file and write to output.
    
    Args:
        source_path: Path to AXON source file
        output_path: Path to write Markdown documentation
    """
    source = Path(source_path).read_text(encoding="utf-8")
    docs = generate_docs(source, source_path=source_path)
    Path(output_path).write_text(docs, encoding="utf-8")
