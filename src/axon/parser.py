import re
import textwrap
from typing import Optional

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


def parse(source: str, parse_expressions: bool = False) -> list:
    """
    Parse AXON source text. Returns a list of declaration objects.
    Supports ImportDecl, TypeAliasDecl, ToolDecl, PromptDecl, RagDecl, FlowDecl, and AgentDecl for Tasks #01-#09.
    Raises SyntaxError with line number on parse failure.
    
    Args:
        source: AXON source text
        parse_expressions: If True, parse method/tool bodies as expression ASTs
    """
    decls = []
    pos = 0
    length = len(source)
    annotations: list[Annotation] = []

    while pos < length:
        pos = _skip_ws_and_regular_comments(source, pos)
        if pos >= length:
            break

        # Parse top-level annotation and attach it to the next declaration.
        if source.startswith("@", pos):
            annotation, pos = _parse_annotation_at(source, pos)
            annotations.append(annotation)
            continue

        # Parse import.
        match = re.match(
            r'import\s+(?:\{\s*([^}]+)\s*\}|([A-Za-z_][A-Za-z0-9_]*))\s+from\s+"([^"]+)"',
            source[pos:],
        )
        if match:
            names_str = match.group(1) or match.group(2)
            names = [n.strip() for n in names_str.split(",") if n.strip()]
            src = match.group(3)
            decls.append(ImportDecl(names=names, source=src))
            pos += match.end()
            continue

        # Parse type alias.
        if _starts_keyword(source, pos, "type"):
            if annotations:
                raise SyntaxError(
                    f"Annotations are not valid before type alias at line {_current_line(source, pos)}"
                )
            type_decl, pos = parse_type_alias(source, pos)
            decls.append(type_decl)
            continue

        # Parse prompt.
        if _starts_keyword(source, pos, "prompt"):
            prompt_decl, pos = parse_prompt(source, pos)
            prompt_decl.annotations = annotations + prompt_decl.annotations
            decls.append(prompt_decl)
            annotations = []
            continue

        # Parse RAG block.
        if _starts_keyword(source, pos, "rag"):
            rag_decl, pos = parse_rag(source, pos, parse_expressions=parse_expressions)
            rag_decl.annotations = annotations
            decls.append(rag_decl)
            annotations = []
            continue

        # Parse flow block.
        if _starts_keyword(source, pos, "flow"):
            flow_decl, pos = parse_flow(source, pos, parse_expressions=parse_expressions)
            flow_decl.annotations = annotations
            decls.append(flow_decl)
            annotations = []
            continue

        # Parse tool.
        if _starts_keyword(source, pos, "tool"):
            tool_decl, pos = parse_tool(source, pos, parse_expressions=parse_expressions)
            tool_decl.annotations = annotations
            decls.append(tool_decl)
            annotations = []
            continue

        # Parse agent.
        if _starts_keyword(source, pos, "agent"):
            agent_decl, pos = parse_agent(source, pos, parse_expressions=parse_expressions)
            agent_decl.annotations = annotations
            decls.append(agent_decl)
            annotations = []
            continue

        raise SyntaxError(
            f"Unexpected token at line {_current_line(source, pos)}: {source[pos:pos + 20]}"
        )

    return decls


def parse_tool(source: str, start: int, parse_expressions: bool = False) -> tuple[ToolDecl, int]:
    """
    Parse one tool declaration starting at position `start` in `source`.
    `start` points to the 't' of 'tool'.
    Returns (ToolDecl, position_after_closing_brace).
    """
    line_num = _current_line(source, start)

    match = re.match(r"tool\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source[start:])
    if not match:
        raise SyntaxError(f"Malformed tool declaration at line {line_num}")

    name = match.group(1)
    pos = start + match.end()

    params_str, pos = _read_balanced_content(
        source,
        pos - 1,
        open_char="(",
        close_char=")",
        error_context=f"parameters for tool {name}",
    )
    params = parse_params(params_str)

    arrow = re.match(r"\s*->\s*", source[pos:])
    if not arrow:
        raise SyntaxError(f"Expected '->' after parameters for tool {name} at line {line_num}")
    pos += arrow.end()

    return_type, pos = _read_until_top_level_char(source, pos, "{")
    return_type = return_type.strip()
    if not return_type:
        raise SyntaxError(f"Expected return type for tool {name} at line {line_num}")
    if pos >= len(source) or source[pos] != "{":
        raise SyntaxError(f"Expected '{{' for tool {name} at line {line_num}")

    body_raw, pos = _read_balanced_content(
        source,
        pos,
        open_char="{",
        close_char="}",
        error_context=f"body for tool {name}",
    )

    docstrings, body_text = _extract_docstrings_and_body(body_raw)
    
    parsed_body = None
    if parse_expressions and body_text.strip():
        try:
            from axon.expression_parser import parse_expression
            parsed_body = parse_expression(body_text, line_offset=line_num)
        except Exception:
            # If parsing fails, leave parsed_body as None
            pass

    return (
        ToolDecl(
            name=name,
            params=params,
            return_type=return_type,
            docstrings=docstrings,
            body=body_text,
            annotations=[],
            line=line_num,
            parsed_body=parsed_body,
        ),
        pos,
    )


def parse_type_alias(source: str, start: int) -> tuple[TypeAliasDecl, int]:
    """
    Parse one top-level type alias declaration starting at `start`.

    Supported forms:
      type IssueId = Int
      type Priority = "low" | "medium" | "high"
      type Issue = { id: Int, title: Str }
      type PagedList<T> = { items: List<T>, total: Int, page: Int }

    Returns (TypeAliasDecl, position_after_declaration).
    """
    line_num = _current_line(source, start)
    match = re.match(r"type\s+([A-Za-z_][A-Za-z0-9_]*)", source[start:])
    if not match:
        raise SyntaxError(f"Malformed type alias at line {line_num}")

    name = match.group(1)
    pos = start + match.end()
    pos = _skip_inline_ws(source, pos)

    type_params: list[str] = []
    if pos < len(source) and source[pos] == "<":
        params_str, pos = _read_balanced_content(
            source,
            pos,
            open_char="<",
            close_char=">",
            error_context=f"type parameters for {name}",
        )
        type_params = _parse_type_params(params_str, name, line_num)
        pos = _skip_inline_ws(source, pos)

    if pos >= len(source) or source[pos] != "=":
        raise SyntaxError(f"Expected '=' in type alias {name} at line {line_num}")
    pos += 1
    pos = _skip_ws_and_regular_comments(source, pos)

    if pos >= len(source):
        raise SyntaxError(f"Missing value in type alias {name} at line {line_num}")

    fields: list[Param] = []
    if source[pos] == "{":
        record_body, pos_after = _read_balanced_content(
            source,
            pos,
            open_char="{",
            close_char="}",
            error_context=f"record type alias {name}",
        )
        fields = parse_params(record_body)
        value = "{ " + _normalize_record_body(record_body) + " }"
        pos = pos_after
        pos = _consume_declaration_tail(source, pos, name, line_num)
    else:
        value, pos = _read_single_line_type_value(source, pos)
        value = value.strip()
        if not value:
            raise SyntaxError(f"Missing value in type alias {name} at line {line_num}")

    return (
        TypeAliasDecl(
            name=name,
            type_params=type_params,
            value=value,
            fields=fields,
            line=line_num,
        ),
        pos,
    )


def parse_prompt(source: str, start: int) -> tuple[PromptDecl, int]:
    """
    Parse one prompt declaration starting at position `start`.
    `start` points to the 'p' of 'prompt'.
    Returns (PromptDecl, position_after_closing_brace).

    Supported Phase 1 form:
      prompt Name(input: Str, @budget(tokens: 600)) -> Str {
          <triple-quoted template body>
      }
    """
    line_num = _current_line(source, start)

    match = re.match(r"prompt\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source[start:])
    if not match:
        raise SyntaxError(f"Malformed prompt declaration at line {line_num}")

    name = match.group(1)
    pos = start + match.end()

    params_str, pos = _read_balanced_content(
        source,
        pos - 1,
        open_char="(",
        close_char=")",
        error_context=f"parameters for prompt {name}",
    )
    params, inline_annotations = parse_prompt_params(params_str)

    arrow = re.match(r"\s*->\s*", source[pos:])
    if not arrow:
        raise SyntaxError(f"Expected '->' after parameters for prompt {name} at line {line_num}")
    pos += arrow.end()

    return_type, pos = _read_until_top_level_char(source, pos, "{")
    return_type = return_type.strip()
    if not return_type:
        raise SyntaxError(f"Expected return type for prompt {name} at line {line_num}")
    if pos >= len(source) or source[pos] != "{":
        raise SyntaxError(f"Expected '{{' for prompt {name} at line {line_num}")

    body_raw, pos = _read_balanced_content(
        source,
        pos,
        open_char="{",
        close_char="}",
        error_context=f"body for prompt {name}",
    )
    template = _parse_prompt_template(body_raw, name, line_num)

    return (
        PromptDecl(
            name=name,
            params=params,
            return_type=return_type,
            template=template,
            annotations=inline_annotations,
            line=line_num,
        ),
        pos,
    )


def parse_rag(source: str, start: int, parse_expressions: bool = False) -> tuple[RagDecl, int]:
    """
    Parse one RAG declaration starting at position `start`.
    `start` points to the 'r' of 'rag'.
    Returns (RagDecl, position_after_closing_brace).

    Phase 1 parser scope: preserve RAG configuration fields and retrieve
    methods as raw strings. It does not build indexes or execute retrieval.
    """
    line_num = _current_line(source, start)

    match = re.match(r"rag\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", source[start:])
    if not match:
        raise SyntaxError(f"Malformed rag declaration at line {line_num}")

    name = match.group(1)
    body_open_pos = start + match.end() - 1
    body_raw, pos_after = _read_balanced_content(
        source,
        body_open_pos,
        open_char="{",
        close_char="}",
        error_context=f"body for rag {name}",
    )

    source_value: Optional[str] = None
    chunker: Optional[str] = None
    embedder: Optional[str] = None
    store: Optional[str] = None
    methods: list[MethodDecl] = []
    method_annotations: list[Annotation] = []

    pos = 0
    while pos < len(body_raw):
        pos = _skip_ws_and_regular_comments(body_raw, pos)
        if pos >= len(body_raw):
            break

        if body_raw.startswith("@", pos):
            annotation, pos = _parse_annotation_at(body_raw, pos)
            method_annotations.append(annotation)
            continue

        if _starts_field(body_raw, pos, "source"):
            _reject_dangling_field_annotations(method_annotations, "source", name, line_num, "rag")
            source_value, pos = _parse_line_field(body_raw, pos, "source")
            continue

        if _starts_field(body_raw, pos, "chunker"):
            _reject_dangling_field_annotations(method_annotations, "chunker", name, line_num, "rag")
            chunker, pos = _parse_line_field(body_raw, pos, "chunker")
            continue

        if _starts_field(body_raw, pos, "embedder"):
            _reject_dangling_field_annotations(method_annotations, "embedder", name, line_num, "rag")
            embedder, pos = _parse_line_field(body_raw, pos, "embedder")
            continue

        if _starts_field(body_raw, pos, "store"):
            _reject_dangling_field_annotations(method_annotations, "store", name, line_num, "rag")
            store, pos = _parse_line_field(body_raw, pos, "store")
            continue

        if _starts_keyword(body_raw, pos, "fn"):
            method, pos = _parse_method(body_raw, pos, method_annotations, parse_expressions=parse_expressions)
            methods.append(method)
            method_annotations = []
            continue

        raise SyntaxError(
            f"Unexpected token in rag {name} at line {line_num}: {body_raw[pos:pos + 30]}"
        )

    if method_annotations:
        raise SyntaxError(f"Dangling annotation at end of rag {name} at line {line_num}")

    missing = [
        field_name
        for field_name, value in (
            ("source", source_value),
            ("chunker", chunker),
            ("embedder", embedder),
            ("store", store),
        )
        if value is None or value == ""
    ]
    if missing:
        raise SyntaxError(
            f"Missing required field(s) in rag {name} at line {line_num}: {', '.join(missing)}"
        )

    if not methods:
        raise SyntaxError(f"RAG block {name} must define at least one retrieve method at line {line_num}")

    return (
        RagDecl(
            name=name,
            source=source_value,
            chunker=chunker,
            embedder=embedder,
            store=store,
            annotations=[],
            methods=methods,
            line=line_num,
        ),
        pos_after,
    )


def parse_flow(source: str, start: int, parse_expressions: bool = False) -> tuple[FlowDecl, int]:
    """
    Parse one flow declaration starting at position `start`.
    `start` points to the 'f' of 'flow'.
    Returns (FlowDecl, position_after_closing_brace).

    Phase 1 parser scope: preserve stage declarations and the remaining
    orchestration body as raw text. It does not execute DAGs or channels.
    """
    line_num = _current_line(source, start)

    match = re.match(r"flow\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source[start:])
    if not match:
        raise SyntaxError(f"Malformed flow declaration at line {line_num}")

    name = match.group(1)
    pos = start + match.end()

    params_str, pos = _read_balanced_content(
        source,
        pos - 1,
        open_char="(",
        close_char=")",
        error_context=f"parameters for flow {name}",
    )
    params = parse_params(params_str)

    arrow = re.match(r"\s*->\s*", source[pos:])
    if not arrow:
        raise SyntaxError(f"Expected '->' after parameters for flow {name} at line {line_num}")
    pos += arrow.end()

    return_type, pos = _read_until_top_level_char(source, pos, "{")
    return_type = return_type.strip()
    if not return_type:
        raise SyntaxError(f"Expected return type for flow {name} at line {line_num}")
    if pos >= len(source) or source[pos] != "{":
        raise SyntaxError(f"Expected '{{' for flow {name} at line {line_num}")

    body_raw, pos_after = _read_balanced_content(
        source,
        pos,
        open_char="{",
        close_char="}",
        error_context=f"body for flow {name}",
    )

    stages: list[StageDecl] = []
    body_chunks: list[str] = []
    pos = 0
    statement_start: Optional[int] = None

    while pos < len(body_raw):
        next_pos = _skip_ws_and_regular_comments(body_raw, pos)
        if statement_start is not None and next_pos > pos:
            body_chunks.append(body_raw[pos:next_pos])
        pos = next_pos
        if pos >= len(body_raw):
            break

        if body_raw.startswith("@", pos):
            raise SyntaxError(f"Annotations inside flow {name} are not supported at line {line_num}")

        if _starts_keyword(body_raw, pos, "stage"):
            stage, pos = _parse_stage_decl(body_raw, pos, base_line=line_num)
            stages.append(stage)
            statement_start = None
            continue

        # Preserve all non-stage flow orchestration text exactly enough for
        # later phases while still allowing nested braces in loops/matches.
        start_body = pos
        pos = _read_flow_statement_end(body_raw, pos)
        body_chunks.append(body_raw[start_body:pos])
        statement_start = None

    body = _normalize_flow_body("".join(body_chunks))
    
    parsed_body = None
    if parse_expressions and body.strip():
        try:
            from axon.expression_parser import parse_expression
            parsed_body = parse_expression(body, line_offset=line_num)
        except Exception:
            # If parsing fails, leave parsed_body as None
            pass

    return (
        FlowDecl(
            name=name,
            params=params,
            return_type=return_type,
            annotations=[],
            stages=stages,
            body=body,
            line=line_num,
            parsed_body=parsed_body,
        ),
        pos_after,
    )


def _parse_stage_decl(source: str, start: int, base_line: int = 1) -> tuple[StageDecl, int]:
    line_num = base_line + _current_line(source, start) - 1
    match = re.match(r"stage\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source[start:])
    if not match:
        raise SyntaxError(f"Malformed stage declaration at line {line_num}")

    name = match.group(1)
    pos = start + match.end()
    params_str, pos = _read_balanced_content(
        source,
        pos - 1,
        open_char="(",
        close_char=")",
        error_context=f"parameters for stage {name}",
    )
    params = parse_params(params_str)

    arrow = re.match(r"[ \t\r]*->[ \t\r]*", source[pos:])
    if not arrow:
        raise SyntaxError(f"Expected '->' after parameters for stage {name} at line {line_num}")
    pos += arrow.end()

    return_type, pos = _read_until_top_level_newline_or_comment(source, pos)
    return_type = return_type.strip()
    if not return_type:
        raise SyntaxError(f"Expected return type for stage {name} at line {line_num}")

    return StageDecl(name=name, params=params, return_type=return_type, line=line_num), pos


def _read_until_top_level_newline_or_comment(source: str, start: int) -> tuple[str, int]:
    pos = start
    in_string = False
    escape = False
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0

    while pos < len(source):
        c = source[pos]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            pos += 1
            continue

        if c == '"':
            in_string = True
        elif c == "<":
            angle_depth += 1
        elif c == ">" and angle_depth > 0:
            angle_depth -= 1
        elif c == "(":
            paren_depth += 1
        elif c == ")" and paren_depth > 0:
            paren_depth -= 1
        elif c == "[":
            bracket_depth += 1
        elif c == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif c == "{":
            brace_depth += 1
        elif c == "}" and brace_depth > 0:
            brace_depth -= 1
        elif (
            c == "\n"
            and angle_depth == 0
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            return source[start:pos].rstrip(), pos + 1
        elif (
            source.startswith("//", pos)
            and not source.startswith("///", pos)
            and angle_depth == 0
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            end = source.find("\n", pos)
            return source[start:pos].rstrip(), len(source) if end == -1 else end + 1
        pos += 1

    return source[start:pos].rstrip(), pos


def _read_flow_statement_end(source: str, start: int) -> int:
    """Read one flow body statement, preserving nested brace blocks."""
    pos = start
    in_string = False
    escape = False
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0

    while pos < len(source):
        c = source[pos]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            pos += 1
            continue

        if c == '"':
            in_string = True
        elif c == "(":
            paren_depth += 1
        elif c == ")" and paren_depth > 0:
            paren_depth -= 1
        elif c == "[":
            bracket_depth += 1
        elif c == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif c == "{":
            brace_depth += 1
        elif c == "}" and brace_depth > 0:
            brace_depth -= 1
        elif (
            c == "\n"
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            return pos + 1
        pos += 1

    return pos


def _normalize_flow_body(body: str) -> str:
    lines: list[str] = []
    for line in textwrap.dedent(body).split("\n"):
        stripped = line.rstrip()
        if stripped.lstrip().startswith("//") and not stripped.lstrip().startswith("///"):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()

def parse_agent(source: str, start: int, parse_expressions: bool = False) -> tuple[AgentDecl, int]:
    """
    Parse one agent declaration starting at position `start`.
    `start` points to the 'a' of 'agent'.
    Returns (AgentDecl, position_after_closing_brace).
    """
    line_num = _current_line(source, start)

    match = re.match(r"agent\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", source[start:])
    if not match:
        raise SyntaxError(f"Malformed agent declaration at line {line_num}")

    name = match.group(1)
    body_open_pos = start + match.end() - 1
    body_raw, pos_after = _read_balanced_content(
        source,
        body_open_pos,
        open_char="{",
        close_char="}",
        error_context=f"body for agent {name}",
    )

    model: Optional[str] = None
    tools: list[str] = []
    memory: Optional[MemoryDecl] = None
    workers: Optional[str] = None
    methods: list[MethodDecl] = []
    method_annotations: list[Annotation] = []

    pos = 0
    while pos < len(body_raw):
        pos = _skip_ws_and_regular_comments(body_raw, pos)
        if pos >= len(body_raw):
            break

        if body_raw.startswith("@", pos):
            annotation, pos = _parse_annotation_at(body_raw, pos)
            method_annotations.append(annotation)
            continue

        if _starts_field(body_raw, pos, "model"):
            if method_annotations:
                raise SyntaxError(
                    f"Dangling annotation before model field in agent {name} at line {line_num}"
                )
            value, pos = _parse_line_field(body_raw, pos, "model")
            model = value.strip()
            continue

        if _starts_field(body_raw, pos, "tools"):
            if method_annotations:
                raise SyntaxError(
                    f"Dangling annotation before tools field in agent {name} at line {line_num}"
                )
            tools, pos = _parse_tools_field(body_raw, pos)
            continue

        if _starts_field(body_raw, pos, "memory"):
            if method_annotations:
                raise SyntaxError(
                    f"Dangling annotation before memory field in agent {name} at line {line_num}"
                )
            value, pos = _parse_line_field(body_raw, pos, "memory")
            memory = parse_memory_decl(value)
            continue

        if _starts_field(body_raw, pos, "workers"):
            if method_annotations:
                raise SyntaxError(
                    f"Dangling annotation before workers field in agent {name} at line {line_num}"
                )
            value, pos = _parse_line_field(body_raw, pos, "workers")
            workers = value.strip()
            continue

        if _starts_keyword(body_raw, pos, "fn"):
            method, pos = _parse_method(body_raw, pos, method_annotations, parse_expressions=parse_expressions)
            methods.append(method)
            method_annotations = []
            continue

        raise SyntaxError(
            f"Unexpected token in agent {name} at line {line_num}: {body_raw[pos:pos + 30]}"
        )

    if method_annotations:
        raise SyntaxError(f"Dangling annotation at end of agent {name} at line {line_num}")

    if not model:
        raise SyntaxError(f"Missing required model field for agent {name} at line {line_num}")

    return (
        AgentDecl(
            name=name,
            model=model,
            tools=tools,
            memory=memory,
            workers=workers,
            annotations=[],
            methods=methods,
            line=line_num,
        ),
        pos_after,
    )


def parse_params(params_str: str) -> list[Param]:
    """
    Parse a parameter list string like:
      "repo: Str, issue_number: Int, label: \"low\"|\"high\" = \"low\""
    Returns list of Param.
    """
    if not params_str.strip():
        return []

    params: list[Param] = []
    tokens = _split_top_level(params_str, ",")

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue

        colon_idx = _find_top_level(tok, ":")
        if colon_idx == -1:
            raise SyntaxError(f"Malformed parameter: {tok}")

        name = tok[:colon_idx].strip()
        rest = tok[colon_idx + 1 :].strip()
        if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise SyntaxError(f"Malformed parameter name: {tok}")
        if not rest:
            raise SyntaxError(f"Missing type for parameter: {tok}")

        eq_idx = _find_top_level(rest, "=")
        if eq_idx != -1:
            type_str = rest[:eq_idx].strip()
            default_val = rest[eq_idx + 1 :].strip()
            params.append(Param(name=name, type_str=type_str, default=default_val))
        else:
            params.append(Param(name=name, type_str=rest, default=None))

    return params


def parse_prompt_params(params_str: str) -> tuple[list[Param], list[Annotation]]:
    """
    Parse prompt parameter lists, where annotation entries such as
    @budget(tokens: 600) may appear alongside typed parameters.
    """
    if not params_str.strip():
        return [], []

    params: list[Param] = []
    annotations: list[Annotation] = []

    for token in _split_top_level(params_str, ","):
        token = token.strip()
        if not token:
            continue
        if token.startswith("@"):
            annotation, end_pos = _parse_annotation_at(token, 0)
            if token[end_pos:].strip():
                raise SyntaxError(f"Unexpected text after prompt annotation: {token}")
            annotations.append(annotation)
            continue
        parsed = parse_params(token)
        if len(parsed) != 1:
            raise SyntaxError(f"Malformed prompt parameter: {token}")
        params.extend(parsed)

    return params, annotations


def parse_memory_decl(value: str) -> MemoryDecl:
    """Parse Memory<Kind>(key: value, ...) into MemoryDecl."""
    value = value.strip()
    match = re.match(r"Memory\s*<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>", value)
    if not match:
        raise SyntaxError(f"Malformed memory declaration: {value}")

    kind = match.group(1)
    pos = match.end()
    options: dict[str, str] = {}

    rest = value[pos:].strip()
    if not rest:
        return MemoryDecl(kind=kind, options=options)

    if not rest.startswith("("):
        raise SyntaxError(f"Malformed memory options: {value}")

    options_str, end_pos = _read_balanced_content(
        rest,
        0,
        open_char="(",
        close_char=")",
        error_context="memory options",
    )
    if rest[end_pos:].strip():
        raise SyntaxError(f"Unexpected trailing text in memory declaration: {value}")

    for option in _split_top_level(options_str, ","):
        option = option.strip()
        if not option:
            continue
        colon_idx = _find_top_level(option, ":")
        if colon_idx == -1:
            raise SyntaxError(f"Malformed memory option: {option}")
        key = option[:colon_idx].strip()
        val = option[colon_idx + 1 :].strip()
        if not key:
            raise SyntaxError(f"Malformed memory option: {option}")
        options[key] = val

    return MemoryDecl(kind=kind, options=options)


def _parse_method(
    source: str, start: int, annotations: list[Annotation], parse_expressions: bool = False
) -> tuple[MethodDecl, int]:
    match = re.match(r"fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source[start:])
    if not match:
        raise SyntaxError(f"Malformed method declaration near: {source[start:start + 30]}")

    name = match.group(1)
    pos = start + match.end()

    params_str, pos = _read_balanced_content(
        source,
        pos - 1,
        open_char="(",
        close_char=")",
        error_context=f"parameters for method {name}",
    )
    params = parse_params(params_str)

    arrow = re.match(r"\s*->\s*", source[pos:])
    if not arrow:
        raise SyntaxError(f"Expected '->' after parameters for method {name}")
    pos += arrow.end()

    return_type, pos = _read_until_top_level_char(source, pos, "{")
    return_type = return_type.strip()
    if not return_type:
        raise SyntaxError(f"Expected return type for method {name}")
    if pos >= len(source) or source[pos] != "{":
        raise SyntaxError(f"Expected '{{' for method {name}")

    body_raw, pos = _read_balanced_content(
        source,
        pos,
        open_char="{",
        close_char="}",
        error_context=f"body for method {name}",
    )
    
    body = _normalize_body(body_raw)
    parsed_body = None
    if parse_expressions and body.strip():
        try:
            from axon.expression_parser import parse_expression
            parsed_body = parse_expression(body, line_offset=_current_line(source, start))
        except Exception:
            # If parsing fails, leave parsed_body as None
            pass

    return (
        MethodDecl(
            name=name,
            params=params,
            return_type=return_type,
            annotations=list(annotations),
            body=body,
            parsed_body=parsed_body,
        ),
        pos,
    )


def _reject_dangling_field_annotations(
    annotations: list[Annotation],
    field_name: str,
    decl_name: str,
    line_num: int,
    decl_kind: str,
) -> None:
    if annotations:
        raise SyntaxError(
            f"Dangling annotation before {field_name} field in {decl_kind} {decl_name} at line {line_num}"
        )


def _parse_line_field(source: str, start: int, field_name: str) -> tuple[str, int]:
    match = re.match(rf"{field_name}\s*:\s*", source[start:])
    if not match:
        raise SyntaxError(f"Malformed {field_name} field near: {source[start:start + 30]}")
    pos = start + match.end()

    # Field values in Task #02 are single-line except tools, which has its own parser.
    end = source.find("\n", pos)
    if end == -1:
        end = len(source)
    value = source[pos:end].strip()
    return value, end


def _parse_tools_field(source: str, start: int) -> tuple[list[str], int]:
    match = re.match(r"tools\s*:\s*", source[start:])
    if not match:
        raise SyntaxError(f"Malformed tools field near: {source[start:start + 30]}")
    pos = start + match.end()
    pos = _skip_inline_ws(source, pos)

    if pos >= len(source) or source[pos] != "[":
        raise SyntaxError(f"Expected '[' after tools: near {source[start:start + 40]}")

    tools_str, pos = _read_balanced_content(
        source,
        pos,
        open_char="[",
        close_char="]",
        error_context="tools list",
    )
    tools = [t.strip() for t in _split_top_level(tools_str, ",") if t.strip()]

    # Consume optional whitespace to the end of line so parsing continues cleanly.
    while pos < len(source) and source[pos] in " \t\r":
        pos += 1
    if pos < len(source) and source[pos] == "\n":
        pos += 1
    return tools, pos


def _parse_annotation_at(source: str, start: int) -> tuple[Annotation, int]:
    match = re.match(r"@([A-Za-z_][A-Za-z0-9_]*)", source[start:])
    if not match:
        raise SyntaxError(f"Malformed annotation at line {_current_line(source, start)}")

    name = match.group(1)
    pos = start + match.end()
    args: dict[str, str] = {}

    pos = _skip_inline_ws(source, pos)
    if pos < len(source) and source[pos] == "(":
        args_str, pos = _read_balanced_content(
            source,
            pos,
            open_char="(",
            close_char=")",
            error_context=f"annotation @{name}",
        )
        args = _parse_key_value_args(args_str)

    return Annotation(name=name, args=args), pos


def _parse_key_value_args(args_str: str) -> dict[str, str]:
    args: dict[str, str] = {}
    for pair in _split_top_level(args_str, ","):
        pair = pair.strip()
        if not pair:
            continue
        colon_idx = _find_top_level(pair, ":")
        if colon_idx == -1:
            # Keep positional args expressible without losing data.
            args[pair] = ""
            continue
        k = pair[:colon_idx].strip()
        v = pair[colon_idx + 1 :].strip()
        args[k] = v
    return args


def _parse_type_params(params_str: str, alias_name: str, line_num: int) -> list[str]:
    params: list[str] = []
    for raw in _split_top_level(params_str, ","):
        param = raw.strip()
        if not param:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", param):
            raise SyntaxError(
                f"Malformed type parameter '{param}' in type alias {alias_name} at line {line_num}"
            )
        params.append(param)
    if not params:
        raise SyntaxError(f"Empty type parameter list in type alias {alias_name} at line {line_num}")
    return params


def _normalize_record_body(record_body: str) -> str:
    return " ".join(_normalize_body(record_body).split())


def _consume_declaration_tail(source: str, pos: int, name: str, line_num: int) -> int:
    """After a type alias value, allow whitespace and one regular inline comment."""
    while pos < len(source) and source[pos] in " \t\r":
        pos += 1
    if source.startswith("//", pos) and not source.startswith("///", pos):
        end = source.find("\n", pos)
        return len(source) if end == -1 else end + 1
    if pos < len(source) and source[pos] == "\n":
        return pos + 1
    if pos >= len(source):
        return pos
    raise SyntaxError(
        f"Unexpected trailing text after type alias {name} at line {line_num}: {source[pos:pos + 30]}"
    )


def _read_single_line_type_value(source: str, start: int) -> tuple[str, int]:
    """Read a non-record type alias RHS until newline or regular inline comment."""
    pos = start
    in_string = False
    escape = False
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0

    while pos < len(source):
        c = source[pos]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            pos += 1
            continue

        if c == '"':
            in_string = True
        elif c == "<":
            angle_depth += 1
        elif c == ">" and angle_depth > 0:
            angle_depth -= 1
        elif c == "(":
            paren_depth += 1
        elif c == ")" and paren_depth > 0:
            paren_depth -= 1
        elif c == "[":
            bracket_depth += 1
        elif c == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif c == "\n" and angle_depth == 0 and paren_depth == 0 and bracket_depth == 0:
            return source[start:pos].rstrip(), pos + 1
        elif (
            source.startswith("//", pos)
            and not source.startswith("///", pos)
            and angle_depth == 0
            and paren_depth == 0
            and bracket_depth == 0
        ):
            end = source.find("\n", pos)
            return source[start:pos].rstrip(), len(source) if end == -1 else end + 1
        pos += 1

    return source[start:pos].rstrip(), pos


def _parse_prompt_template(body_raw: str, prompt_name: str, line_num: int) -> str:
    """Extract and dedent the single triple-quoted template string inside a prompt body."""
    body = body_raw.strip()
    if not body.startswith('"""'):
        raise SyntaxError(
            f"Prompt {prompt_name} body must start with a triple-quoted template at line {line_num}"
        )

    pos = 3
    template_chars: list[str] = []
    escape = False
    while pos < len(body):
        if body.startswith('"""', pos) and not escape:
            template = "".join(template_chars)
            trailing = body[pos + 3 :].strip()
            if trailing:
                raise SyntaxError(
                    f"Unexpected text after template in prompt {prompt_name} at line {line_num}"
                )
            return textwrap.dedent(template).strip()

        c = body[pos]
        template_chars.append(c)
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        pos += 1

    raise SyntaxError(f"Unclosed triple-quoted template in prompt {prompt_name} at line {line_num}")


def _extract_docstrings_and_body(body_raw: str) -> tuple[list[str], str]:
    docstrings: list[str] = []
    body_lines: list[str] = []

    for line in body_raw.split("\n"):
        sline = line.lstrip()
        if sline.startswith("///"):
            doc_content = sline[3:]
            if doc_content.startswith(" "):
                doc_content = doc_content[1:]
            docstrings.append(doc_content)
        elif sline.startswith("//"):
            continue
        else:
            body_lines.append(line)

    return docstrings, _normalize_body("\n".join(body_lines))


def _normalize_body(body: str) -> str:
    return textwrap.dedent(body).strip()


def _read_balanced_content(
    source: str,
    start: int,
    open_char: str,
    close_char: str,
    error_context: str,
) -> tuple[str, int]:
    """
    Read content inside a balanced pair.
    `start` must point at `open_char`.
    Returns (inside_content, position_after_close_char).
    """
    if start >= len(source) or source[start] != open_char:
        raise SyntaxError(
            f"Expected '{open_char}' for {error_context} at line {_current_line(source, start)}"
        )

    pos = start + 1
    content_start = pos
    depth = 1
    in_string = False
    escape = False

    while pos < len(source):
        c = source[pos]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return source[content_start:pos], pos + 1
        pos += 1

    raise SyntaxError(
        f"Unclosed {error_context} starting at line {_current_line(source, start)}"
    )


def _read_until_top_level_char(source: str, start: int, target: str) -> tuple[str, int]:
    """Read until `target`, ignoring occurrences inside strings and generic angle brackets."""
    pos = start
    in_string = False
    escape = False
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0

    while pos < len(source):
        c = source[pos]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "<":
                angle_depth += 1
            elif c == ">" and angle_depth > 0:
                angle_depth -= 1
            elif c == "(":
                paren_depth += 1
            elif c == ")" and paren_depth > 0:
                paren_depth -= 1
            elif c == "[":
                bracket_depth += 1
            elif c == "]" and bracket_depth > 0:
                bracket_depth -= 1
            elif (
                c == target
                and angle_depth == 0
                and paren_depth == 0
                and bracket_depth == 0
            ):
                return source[start:pos], pos
        pos += 1

    return source[start:pos], pos


def _split_top_level(text: str, sep: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_string = False
    escape = False
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0

    for c in text:
        if in_string:
            current.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue

        if c == '"':
            in_string = True
            current.append(c)
        elif c == "<":
            angle_depth += 1
            current.append(c)
        elif c == ">" and angle_depth > 0:
            angle_depth -= 1
            current.append(c)
        elif c == "(":
            paren_depth += 1
            current.append(c)
        elif c == ")" and paren_depth > 0:
            paren_depth -= 1
            current.append(c)
        elif c == "[":
            bracket_depth += 1
            current.append(c)
        elif c == "]" and bracket_depth > 0:
            bracket_depth -= 1
            current.append(c)
        elif c == "{":
            brace_depth += 1
            current.append(c)
        elif c == "}" and brace_depth > 0:
            brace_depth -= 1
            current.append(c)
        elif (
            c == sep
            and angle_depth == 0
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(c)

    if current or text.endswith(sep):
        parts.append("".join(current).strip())
    return parts


def _find_top_level(text: str, char: str) -> int:
    in_string = False
    escape = False
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0

    for i, c in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue

        if c == '"':
            in_string = True
        elif c == "<":
            angle_depth += 1
        elif c == ">" and angle_depth > 0:
            angle_depth -= 1
        elif c == "(":
            paren_depth += 1
        elif c == ")" and paren_depth > 0:
            paren_depth -= 1
        elif c == "[":
            bracket_depth += 1
        elif c == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif c == "{":
            brace_depth += 1
        elif c == "}" and brace_depth > 0:
            brace_depth -= 1
        elif (
            c == char
            and angle_depth == 0
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            return i

    return -1


def _skip_ws_and_regular_comments(source: str, pos: int) -> int:
    while pos < len(source):
        match = re.match(r"\s+", source[pos:])
        if match:
            pos += match.end()
            continue
        if source.startswith("//", pos):
            end_line = source.find("\n", pos)
            if end_line == -1:
                return len(source)
            pos = end_line + 1
            continue
        break
    return pos


def _skip_inline_ws(source: str, pos: int) -> int:
    while pos < len(source) and source[pos] in " \t\r":
        pos += 1
    return pos


def _starts_keyword(source: str, pos: int, keyword: str) -> bool:
    if not source.startswith(keyword, pos):
        return False
    after = pos + len(keyword)
    return after >= len(source) or not (
        source[after].isalnum() or source[after] == "_"
    )


def _starts_field(source: str, pos: int, field_name: str) -> bool:
    return re.match(rf"{field_name}\s*:", source[pos:]) is not None


def _current_line(source: str, pos: int) -> int:
    safe_pos = max(0, min(pos, len(source)))
    return source.count("\n", 0, safe_pos) + 1
