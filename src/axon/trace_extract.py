"""Static AEL trace extraction for AXON method bodies.

This module produces a *preview* trace from parsed AXON declarations. It does
not execute an agent, dispatch tools, evaluate expressions, or call model
providers. Instead, it scans raw method body text for the AEL statements that
are already part of the AXON syntax:

- ``think "..."``
- ``act ToolName(arg: value, ...)``
- ``observe name: value``
- ``store memory.path = value``

The result is a ``TraceLog`` containing normal trace event objects with source
metadata attached. That gives developers an early, deterministic way to inspect
what a method is expected to log once runtime execution exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import ast
import json
import re

from axon.ast_nodes import AgentDecl, MethodDecl, RagDecl
from axon.parser import parse
from axon.trace import ActEvent, AELTraceEvent, ObserveEvent, StoreEvent, ThinkEvent, TraceLog
from axon.validator import validate_or_raise


@dataclass(frozen=True)
class TraceExtractionOptions:
    """Options controlling static trace extraction.

    ``include_rag_methods`` is disabled by default because AEL traces are most
    useful for agent methods. It exists so later tooling can preview traces for
    RAG retrieval functions without changing this API.
    """

    include_rag_methods: bool = False


def extract_trace_events_from_body(
    body: str,
    *,
    agent: str | None = None,
    method: str | None = None,
    declaration_kind: str | None = None,
    start_line: int = 1,
) -> list[AELTraceEvent]:
    """Extract AEL preview events from one raw method body.

    Args:
        body: Raw AXON method body text from ``MethodDecl.body``.
        agent: Optional declaration/agent name attached to each event.
        method: Optional method name stored in event metadata.
        declaration_kind: Optional owner kind, usually ``"agent"`` or ``"rag"``.
        start_line: 1-based line offset for metadata. Method bodies currently
            do not carry exact source line numbers, so callers usually keep the
            default and treat this as body-relative.

    Returns:
        A list of ``ThinkEvent``, ``ActEvent``, ``ObserveEvent``, and
        ``StoreEvent`` objects in source order.
    """
    events: list[AELTraceEvent] = []
    for offset, raw_line in enumerate(body.splitlines(), start=start_line):
        line = _strip_line_comment(raw_line).strip()
        if not line:
            continue

        metadata = _source_metadata(method=method, declaration_kind=declaration_kind, line=offset, source_line=line)

        think = _parse_think_line(line)
        if think is not None:
            events.append(ThinkEvent(think, agent=agent, metadata=metadata))
            continue

        store = _parse_store_line(line)
        if store is not None:
            key, value = store
            events.append(StoreEvent(key, value, agent=agent, metadata=metadata))
            # Do not continue here; a line could theoretically contain both a
            # store and an act expression. In normal style it will not, but the
            # scanner below keeps this function conservative.

        observe = _parse_observe_line(line)
        if observe is not None:
            name, value, count = observe
            events.append(ObserveEvent(name, value, count=count, agent=agent, metadata=metadata))
            continue

        for tool, args in _iter_act_calls(line):
            events.append(ActEvent(tool, args, agent=agent, metadata=metadata))

    return events


def extract_trace_preview(
    declarations: Iterable[Any],
    *,
    options: TraceExtractionOptions | None = None,
) -> TraceLog:
    """Extract a static AEL preview trace from parsed declarations.

    Only ``AgentDecl`` methods are scanned by default. ``RagDecl`` methods can
    be included by passing ``TraceExtractionOptions(include_rag_methods=True)``.
    """
    opts = options or TraceExtractionOptions()
    log = TraceLog()

    for declaration in declarations:
        if isinstance(declaration, AgentDecl):
            for method in declaration.methods:
                log.extend(
                    extract_trace_events_from_method(
                        method,
                        agent=declaration.name,
                        declaration_kind="agent",
                    )
                )
        elif opts.include_rag_methods and isinstance(declaration, RagDecl):
            for method in declaration.methods:
                log.extend(
                    extract_trace_events_from_method(
                        method,
                        agent=declaration.name,
                        declaration_kind="rag",
                    )
                )

    return log


def extract_trace_events_from_method(
    method: MethodDecl,
    *,
    agent: str | None = None,
    declaration_kind: str | None = None,
) -> list[AELTraceEvent]:
    """Extract a static AEL preview trace from one parsed method."""
    return extract_trace_events_from_body(
        method.body,
        agent=agent,
        method=method.name,
        declaration_kind=declaration_kind,
    )


def extract_trace_preview_from_source(source: str, *, validate_source: bool = True) -> TraceLog:
    """Parse AXON source and return its static AEL trace preview."""
    declarations = parse(source)
    if validate_source:
        validate_or_raise(declarations)
    return extract_trace_preview(declarations)


def extract_trace_preview_from_file(path: str | Path, *, validate_source: bool = True) -> TraceLog:
    """Read an AXON file and return its static AEL trace preview."""
    source = Path(path)
    return extract_trace_preview_from_source(source.read_text(encoding="utf-8"), validate_source=validate_source)


def trace_preview_to_json(log: TraceLog) -> str:
    """Serialise a trace preview as a pretty JSON array."""
    return json.dumps([event.to_dict() for event in log.events], ensure_ascii=False, indent=2)


def format_trace_preview(log: TraceLog) -> str:
    """Return a compact human-readable trace preview."""
    if not log.events:
        return "No AEL trace events found."

    lines = [f"AEL trace preview: {len(log.events)} event(s)"]
    for index, event in enumerate(log.events, start=1):
        location = _format_location(event)
        if isinstance(event, ThinkEvent):
            lines.append(f"{index}. think{location}: {event.content}")
        elif isinstance(event, ActEvent):
            args = _format_args(event.args)
            lines.append(f"{index}. act{location}: {event.tool}({args})")
        elif isinstance(event, ObserveEvent):
            suffix = f" count={event.count}" if event.count is not None else f" value={event.value}"
            lines.append(f"{index}. observe{location}: {event.name}{suffix}")
        elif isinstance(event, StoreEvent):
            suffix = f" = {event.value}" if event.value is not None else ""
            lines.append(f"{index}. store{location}: {event.key}{suffix}")
        else:  # pragma: no cover - exhaustive for current TraceEvent union
            lines.append(f"{index}. {event.t}{location}")
    return "\n".join(lines)


def _parse_think_line(line: str) -> str | None:
    match = re.match(r'^think\s+"((?:\\.|[^"\\])*)"\s*$', line)
    if not match:
        return None
    return _unescape_preview_string(match.group(1))


def _parse_store_line(line: str) -> tuple[str, str | None] | None:
    # Example: store memory.working["topic"] = results
    match = re.match(r"^store\s+(.+?)(?:\s*=\s*(.+))?$", line)
    if not match:
        return None
    key = match.group(1).strip()
    value = match.group(2).strip() if match.group(2) is not None else None
    return key, value


def _parse_observe_line(line: str) -> tuple[str, str | None, int | None] | None:
    # Example: observe results: [{ title: "A" }]
    match = re.match(r"^observe\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", line)
    if not match:
        return None
    name = match.group(1)
    value = match.group(2).strip()
    return name, value, _infer_preview_count(value)


def _iter_act_calls(line: str) -> Iterable[tuple[str, dict[str, str]]]:
    """Yield ``act Tool(args)`` occurrences in one source line."""
    index = 0
    while index < len(line):
        match = re.search(r"\bact\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\(", line[index:])
        if not match:
            return

        tool = match.group(1)
        args_start = index + match.end()
        args_text, close_pos = _read_balanced_parens_content(line, args_start)
        if args_text is None:
            return

        yield tool, _parse_call_args(args_text)
        index = close_pos + 1


def _read_balanced_parens_content(text: str, start: int) -> tuple[str | None, int]:
    """Read content after an already-consumed opening parenthesis.

    Args:
        text: Full line.
        start: Position immediately after the opening ``(``.

    Returns:
        ``(content, close_position)`` or ``(None, len(text))`` if unbalanced.
    """
    depth = 1
    in_string = False
    quote = ""
    escaped = False
    pos = start
    while pos < len(text):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
        else:
            if char in {'"', "'"}:
                in_string = True
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[start:pos], pos
        pos += 1
    return None, len(text)


def _parse_call_args(args_text: str) -> dict[str, str]:
    args: dict[str, str] = {}
    positional_index = 0
    for token in _split_top_level(args_text, separator=","):
        if not token.strip():
            continue
        key_value = _split_first_top_level(token, separator=":")
        if key_value is None:
            positional_index += 1
            args[f"_${positional_index}"] = token.strip()
        else:
            key, value = key_value
            args[key.strip()] = value.strip()
    return args


def _split_top_level(text: str, *, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    angle = paren = bracket = brace = 0
    in_string = False
    quote = ""
    escaped = False

    for char in text:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            quote = char
            current.append(char)
        elif char == "<":
            angle += 1
            current.append(char)
        elif char == ">" and angle > 0:
            angle -= 1
            current.append(char)
        elif char == "(":
            paren += 1
            current.append(char)
        elif char == ")" and paren > 0:
            paren -= 1
            current.append(char)
        elif char == "[":
            bracket += 1
            current.append(char)
        elif char == "]" and bracket > 0:
            bracket -= 1
            current.append(char)
        elif char == "{":
            brace += 1
            current.append(char)
        elif char == "}" and brace > 0:
            brace -= 1
            current.append(char)
        elif char == separator and angle == paren == bracket == brace == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _split_first_top_level(text: str, *, separator: str) -> tuple[str, str] | None:
    parts = _split_top_level(text, separator=separator)
    if len(parts) < 2:
        return None
    return parts[0], separator.join(parts[1:])


def _infer_preview_count(value: str) -> int | None:
    stripped = value.strip()
    if stripped == "[]":
        return 0
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return 0
        return len(_split_top_level(inner, separator=","))
    return None


def _strip_line_comment(line: str) -> str:
    in_string = False
    quote = ""
    escaped = False
    for index, char in enumerate(line):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            in_string = True
            quote = char
        elif char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            return line[:index]
    return line


def _unescape_preview_string(value: str) -> str:
    try:
        parsed = ast.literal_eval(f'"{value}"')
    except (SyntaxError, ValueError):
        return value
    return parsed if isinstance(parsed, str) else value


def _source_metadata(
    *,
    method: str | None,
    declaration_kind: str | None,
    line: int,
    source_line: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"line": line, "source": source_line}
    if method:
        metadata["method"] = method
    if declaration_kind:
        metadata["declaration"] = declaration_kind
    return metadata


def _format_location(event: AELTraceEvent) -> str:
    bits: list[str] = []
    if event.agent:
        bits.append(event.agent)
    method = event.metadata.get("method") if event.metadata else None
    if isinstance(method, str):
        bits.append(method)
    if not bits:
        return ""
    return f" [{'.'.join(bits)}]"


def _format_args(args: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in args.items())
