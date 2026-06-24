"""FastMCP code generator for the AXON prototype.

This module intentionally keeps Phase 1 generation conservative: AXON tool
bodies are preserved as comments and emitted as explicit stubs. The generated
server is meant to be runnable after the user fills in tool implementations.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from axon.ast_nodes import AgentDecl, Annotation, Param, ToolDecl

if TYPE_CHECKING:
    from axon.config import AxonConfig
    from axon.expression_ast import Expr


def generate_mcp_server(
    declarations: list,
    output_name: str = "axon_server",
    config: "AxonConfig | None" = None,
) -> str:
    """
    Generate a complete FastMCP Python server as a string.

    Args:
        declarations: output of parse() from parser.py
        output_name: used as the fallback FastMCP server name when no agent exists
        config: optional loaded axon.toml configuration; used only for safe defaults

    Returns:
        A Python source string ready to be written to a .py file and run.
    """
    tools = [decl for decl in declarations if isinstance(decl, ToolDecl)]
    agents = [decl for decl in declarations if isinstance(decl, AgentDecl)]
    agent = agents[0] if agents else None

    server_name = agent.name if agent else output_name
    model = _effective_model(agent.model if agent else "env.DEFAULT_MODEL", config)
    provider_default, model_default = _provider_model_defaults(model)

    lines: list[str] = []
    lines.extend(_header_lines(agent, agents, output_name))
    lines.append("from fastmcp import FastMCP")
    lines.append("from typing import Any, Optional, Iterator")
    lines.append("import os")
    lines.append("")
    lines.append("# ── Server ─────────────────────────────────────────────────────────────────────")
    lines.append(f'mcp = FastMCP("{_escape_py_string(server_name)}")')
    lines.append("")
    lines.append("# Provider configuration (set via environment variables in axon.toml)")
    lines.append(f'AXON_PROVIDER = os.getenv("AXON_PROVIDER", "{_escape_py_string(provider_default)}")')
    lines.append(f'AXON_MODEL    = os.getenv("AXON_MODEL",    "{_escape_py_string(model_default)}")')
    lines.append("")
    lines.append("# ── Tools ──────────────────────────────────────────────────────────────────────")
    lines.append("")

    for index, tool in enumerate(tools):
        if index:
            lines.append("")
        lines.extend(_generate_tool_lines(tool))

    if not tools:
        lines.append("# No AXON tool declarations found.")
        lines.append("")

    lines.append("")
    lines.append("# ── Agent metadata ─────────────────────────────────────────────────────────────")
    if agent:
        lines.extend(_agent_metadata_lines(agent))
    else:
        lines.append("AXON_AGENT_TOOLS    = []")
        lines.append("AXON_AGENT_MEMORY   = None")
        lines.append("AXON_AGENT_SCHEDULE = None")
    lines.append("")
    lines.append("# ── Entry point ────────────────────────────────────────────────────────────────")
    lines.append('if __name__ == "__main__":')
    lines.append("    mcp.run()")
    lines.append("")

    return "\n".join(lines)


def type_to_python(axon_type: str) -> str:
    """
    Convert an AXON type string to a Python type annotation string.
    """
    type_expr = axon_type.strip()
    if not type_expr:
        return "Any"

    # Literal unions are represented as strings for Phase 1.
    if "|" in type_expr and '"' in type_expr:
        return "str"

    # Result<T, E> is intentionally simplified for the first generator.
    if _is_generic(type_expr, "Result"):
        return "dict"

    primitive_map = {
        "Str": "str",
        "Int": "int",
        "Float": "float",
        "Bool": "bool",
        "Any": "Any",
        "Bytes": "bytes",
        "()": "None",
    }
    if type_expr in primitive_map:
        return primitive_map[type_expr]

    generic = _parse_generic(type_expr)
    if generic is None:
        # Unknown AXON domain/custom types are left permissive in generated stubs.
        return "Any"

    name, args = generic
    if name == "List" and len(args) == 1:
        return f"list[{type_to_python(args[0])}]"
    if name == "Set" and len(args) == 1:
        return f"set[{type_to_python(args[0])}]"
    if name == "Map" and len(args) == 2:
        return f"dict[{type_to_python(args[0])}, {type_to_python(args[1])}]"
    if name == "Tuple" and args:
        return f"tuple[{', '.join(type_to_python(arg) for arg in args)}]"
    if name == "Option" and len(args) == 1:
        return f"Optional[{type_to_python(args[0])}]"
    if name == "Stream" and len(args) == 1:
        return f"Iterator[{type_to_python(args[0])}]"

    return "Any"


def to_snake_case(name: str) -> str:
    """
    Convert CamelCase or mixedCase names to snake_case.
    """
    if not name:
        return name

    # Normalize separators first, then handle acronym and lower->upper boundaries.
    cleaned = re.sub(r"[\s\-]+", "_", name.strip())
    cleaned = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", cleaned)
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.lower().strip("_")


def _expr_to_python(expr) -> str | None:
    """Convert a parsed AXON expression AST to Python source.

    Returns ``None`` for constructs that cannot be safely translated
    (e.g. ``act``, ``store``, ``observe``) so the caller can fall back
    to ``NotImplementedError`` stubs.
    """
    if expr is None:
        return None

    from axon import expression_ast as e

    if isinstance(expr, e.LiteralExpr):
        val = expr.value
        if isinstance(val, str):
            # Detect AXON-style interpolation {var} and convert to Python f-string.
            import re as _re
            if _re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", val):
                py_parts = []
                last = 0
                for m in _re.finditer(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", val):
                    if m.start() > last:
                        py_parts.append(val[last:m.start()])
                    py_parts.append("{" + m.group(1) + "}")
                    last = m.end()
                if last < len(val):
                    py_parts.append(val[last:])
                result = 'f"'
                for part in py_parts:
                    if part.startswith("{") and part.endswith("}") and len(part) > 2:
                        result += part
                    else:
                        result += part.replace("{", "{{").replace("}", "}}")
                result += '"'
                return result
            return repr(val)
        if isinstance(val, bool):
            return "True" if val else "False"
        return repr(val)

    if isinstance(expr, e.VariableExpr):
        # AEL keywords cannot be safely translated to Python.
        if expr.name in {"act", "think", "store", "observe", "await", "go", "send", "select", "chan", "pool", "receive", "broadcast", "discover", "spawn", "pause", "resume", "terminate"}:
            return None
        return expr.name

    if isinstance(expr, e.StringInterpolationExpr):
        parts: list[str] = []
        for part in expr.parts:
            py = _expr_to_python(part)
            if py is None:
                return None
            parts.append(py)
        # Reconstruct as a Python f-string.
        result = 'f"'
        for part in parts:
            if part.startswith('"') and part.endswith('"'):
                # Literal string segment
                inner = part[1:-1]
                result += inner.replace("{", "{{").replace("}", "}}")
            else:
                # Variable/expression segment
                result += "{" + part + "}"
        result += '"'
        return result

    if isinstance(expr, e.BinaryOpExpr):
        op_map = {
            "&&": "and",
            "||": "or",
            "==": "==",
            "!=": "!=",
            "<": "<",
            ">": ">",
            "<=": "<=",
            ">=": ">=",
            "+": "+",
            "-": "-",
            "*": "*",
            "/": "/",
            "%": "%",
        }
        py_op = op_map.get(expr.op)
        if py_op is None:
            return None
        left = _expr_to_python(expr.left)
        right = _expr_to_python(expr.right)
        if left is None or right is None:
            return None
        return f"({left} {py_op} {right})"

    if isinstance(expr, e.UnaryOpExpr):
        op_map = {"!": "not ", "not": "not ", "-": "-"}
        py_op = op_map.get(expr.op)
        if py_op is None:
            return None
        operand = _expr_to_python(expr.operand)
        if operand is None:
            return None
        return f"{py_op}{operand}"

    if isinstance(expr, e.CallExpr):
        callee = _expr_to_python(expr.callee)
        if callee is None:
            return None
        args: list[str] = []
        for arg in expr.args:
            py = _expr_to_python(arg)
            if py is None:
                return None
            args.append(py)
        return f"{callee}({', '.join(args)})"

    if isinstance(expr, e.ActExpr):
        tool_name = to_snake_case(expr.tool_name)
        kwargs: list[str] = []
        for k, v in expr.args:
            py_v = _expr_to_python(v)
            if py_v is None:
                return None
            kwargs.append(f"{k}={py_v}")
        return f"{tool_name}({', '.join(kwargs)})"

    if isinstance(expr, e.MemberAccessExpr):
        obj = _expr_to_python(expr.object)
        if obj is None:
            return None
        return f"{obj}.{expr.member}"

    if isinstance(expr, e.IndexExpr):
        obj = _expr_to_python(expr.object)
        idx = _expr_to_python(expr.index)
        if obj is None or idx is None:
            return None
        return f"{obj}[{idx}]"

    if isinstance(expr, e.ListExpr):
        elems: list[str] = []
        for el in expr.elements:
            py = _expr_to_python(el)
            if py is None:
                return None
            elems.append(py)
        return f"[{', '.join(elems)}]"

    if isinstance(expr, e.MapExpr):
        pairs: list[str] = []
        for k, v in expr.pairs:
            pk = _expr_to_python(k)
            pv = _expr_to_python(v)
            if pk is None or pv is None:
                return None
            pairs.append(f"{pk}: {pv}")
        return "{" + ", ".join(pairs) + "}"

    if isinstance(expr, e.BlockExpr):
        if not expr.statements:
            return "None"
        lines: list[str] = []
        for stmt in expr.statements:
            py = _expr_to_python(stmt)
            if py is None:
                return None
            lines.append(py)
        # A block with a single expression is just that expression.
        if len(lines) == 1:
            return lines[0]
        # Multi-statement blocks are tricky to inline; safer to reject.
        return None

    if isinstance(expr, e.LetExpr):
        value = _expr_to_python(expr.value)
        body = _expr_to_python(expr.body)
        if value is None or body is None:
            return None
        # In Python: name = value; body  (simplified for single-expression body)
        return f"({body} if ({expr.name} := {value}) is not None else None)"

    if isinstance(expr, e.ReturnExpr):
        val = _expr_to_python(expr.value)
        if val is None:
            return None
        return f"return {val}"

    if isinstance(expr, e.OkExpr):
        val = _expr_to_python(expr.value)
        if val is None:
            return None
        return f"{{\"ok\": {val}}}"

    if isinstance(expr, e.ErrorExpr):
        val = _expr_to_python(expr.value)
        if val is None:
            return None
        return f"{{\"error\": {val}}}"

    if isinstance(expr, e.SomeExpr):
        val = _expr_to_python(expr.value)
        if val is None:
            return None
        return val

    if isinstance(expr, e.NoneExpr):
        return "None"

    if isinstance(expr, e.IfExpr):
        cond = _expr_to_python(expr.condition)
        then_ = _expr_to_python(expr.then_branch)
        else_ = _expr_to_python(expr.else_branch) if expr.else_branch else None
        if cond is None or then_ is None:
            return None
        if else_ is None:
            return None
        return f"({then_} if {cond} else {else_})"

    if isinstance(expr, e.MatchExpr):
        # Too complex for direct translation.
        return None

    if isinstance(expr, e.TryExpr):
        # Try-with-? operator: translate the inner expression directly.
        inner = _expr_to_python(expr.operand)
        if inner is None:
            return None
        return inner

    if isinstance(expr, e.AssignExpr):
        value = _expr_to_python(expr.value)
        if value is None:
            return None
        return f"({expr.name} := {value})"

    return None


def _stmt_to_python(expr) -> str | None:
    """Convert an AXON expression to a Python statement (not an expression).

    Used for multi-statement block generation where we need assignments,
    function calls, etc. rather than inline expressions.
    """
    from axon import expression_ast as e

    if isinstance(expr, e.LetExpr):
        value = _expr_to_python(expr.value)
        if value is None:
            return None
        return f"{expr.name} = {value}"

    if isinstance(expr, e.ActExpr):
        tool_name = to_snake_case(expr.tool_name)
        kwargs: list[str] = []
        for k, v in expr.arguments:
            py_v = _expr_to_python(v)
            if py_v is None:
                return None
            kwargs.append(f"{k}={py_v}")
        return f"{tool_name}({', '.join(kwargs)})"

    if isinstance(expr, e.StoreExpr):
        target = _expr_to_python(expr.target)
        value = _expr_to_python(expr.value)
        if target is None or value is None:
            return None
        return f"{target} = {value}"

    if isinstance(expr, e.ObserveExpr):
        value = _expr_to_python(expr.value)
        if value is None:
            return None
        return f"print(f'observe: {value}')"

    if isinstance(expr, e.ThinkExpr):
        value = _expr_to_python(expr.value)
        if value is None:
            return None
        return f"# think: {value}"

    if isinstance(expr, e.ReturnExpr):
        val = _expr_to_python(expr.value)
        if val is None:
            return None
        return f"return {val}"

    if isinstance(expr, e.AssignExpr):
        value = _expr_to_python(expr.value)
        if value is None:
            return None
        return f"{expr.name} = {value}"

    if isinstance(expr, e.ForExpr):
        iterable = _expr_to_python(expr.iterable)
        if iterable is None:
            return None
        lines = [f"for {expr.var_name} in {iterable}:"]
        # Handle body without implicit return (loop body is not a function body)
        if isinstance(expr.body, e.BlockExpr):
            for stmt in expr.body.statements:
                line = _stmt_to_python(stmt)
                if line is None:
                    return None
                if "\n" in line:
                    for sub in line.split("\n"):
                        lines.append(f"    {sub}")
                else:
                    lines.append(f"    {line}")
        else:
            line = _stmt_to_python(expr.body)
            if line is None:
                return None
            lines.append(f"    {line}")
        return "\n".join(lines)

    if isinstance(expr, e.TryExpr):
        # Try-with-? operator: translate the inner expression directly.
        # The generated stub is meant to be filled in by the user.
        inner = _stmt_to_python(expr.operand)
        if inner is None:
            return None
        return inner

    # Default: try as a plain expression statement
    py = _expr_to_python(expr)
    if py is None:
        return None
    return py


def _expr_to_python_lines(expr) -> list[str] | None:
    """Convert a parsed AXON expression AST to a list of Python lines.

    Supports multi-statement blocks. Returns ``None`` for constructs
    that cannot be safely translated.
    """
    from axon import expression_ast as e

    if expr is None:
        return None

    if isinstance(expr, e.BlockExpr):
        if not expr.statements:
            return ["return None"]
        result: list[str] = []
        for i, stmt in enumerate(expr.statements):
            is_last = i == len(expr.statements) - 1
            if is_last:
                # Last statement is the return value
                if isinstance(stmt, e.ReturnExpr):
                    line = _stmt_to_python(stmt)
                    if line is None:
                        return None
                    result.append(line)
                else:
                    py = _expr_to_python(stmt)
                    if py is None:
                        return None
                    result.append(f"return {py}")
            else:
                line = _stmt_to_python(stmt)
                if line is None:
                    return None
                if "\n" in line:
                    result.extend(line.split("\n"))
                else:
                    result.append(line)
        return result

    if isinstance(expr, e.LetExpr):
        # Let in a multi-line context: assignment + body
        value = _expr_to_python(expr.value)
        if value is None:
            return None
        lines: list[str] = [f"{expr.name} = {value}"]
        body_lines = _expr_to_python_lines(expr.body)
        if body_lines is None:
            return None
        lines.extend(body_lines)
        return lines

    # Single expression: just return it
    py = _expr_to_python(expr)
    if py is None:
        return None
    return [f"return {py}"]


def _header_lines(agent: AgentDecl | None, agents: list[AgentDecl], output_name: str) -> list[str]:
    agent_name = agent.name if agent else output_name
    model = agent.model if agent else "env.DEFAULT_MODEL"
    lines = [
        '"""',
        "Generated by AXON v0.1",
        f"Agent: {agent_name}",
        f"Model: {model}",
        "DO NOT EDIT — regenerate with: axon build <source.ax>",
        '"""',
        "",
    ]
    if len(agents) > 1:
        other_names = ", ".join(a.name for a in agents[1:])
        lines.append(f"# WARNING: multiple agents found. Using first agent: {agent.name}.")
        lines.append(f"# Other agents in source: {other_names}")
        lines.append("")
    return lines


def _generate_tool_lines(tool: ToolDecl) -> list[str]:
    function_name = to_snake_case(tool.name)
    signature = _tool_signature(tool)
    source_signature = _axon_tool_signature(tool)
    docstring = _tool_docstring(tool, source_signature)
    body_comments = _axon_body_comment_lines(tool.body)

    lines = [
        "@mcp.tool()",
        f"def {function_name}({signature}) -> {type_to_python(tool.return_type)}:",
    ]
    lines.extend(_indent_docstring(docstring))

    # Try to translate parsed body to real Python.
    body_lines = None
    if hasattr(tool, "parsed_body") and tool.parsed_body is not None:
        body_lines = _expr_to_python_lines(tool.parsed_body)

    if body_lines is not None:
        for line in body_lines:
            lines.append(f"    {line}")
    else:
        lines.append("    # TODO: implement tool body")
        lines.extend(body_comments)
        lines.append("    raise NotImplementedError(")
        lines.append(f'        "{_escape_py_string(tool.name)} is not yet implemented. "')
        lines.append('        "Add your implementation here or run: axon implement '
                     f'{_escape_py_string(tool.name)}"')
        lines.append("    )")
    return lines


def _tool_signature(tool: ToolDecl) -> str:
    return ", ".join(_param_signature(param) for param in tool.params)


def _param_signature(param: Param) -> str:
    annotation = type_to_python(param.type_str)
    if param.default is None:
        return f"{param.name}: {annotation}"
    return f"{param.name}: {annotation} = {_default_to_python(param.default)}"


def _default_to_python(default: str) -> str:
    value = default.strip()
    if value == "true":
        return "True"
    if value == "false":
        return "False"
    if value == "null":
        return "None"
    return value


def _axon_tool_signature(tool: ToolDecl) -> str:
    params = ", ".join(_axon_param_signature(param) for param in tool.params)
    return f"{tool.name}({params}) -> {tool.return_type}"


def _axon_param_signature(param: Param) -> str:
    if param.default is None:
        return f"{param.name}: {param.type_str}"
    return f"{param.name}: {param.type_str} = {param.default}"


def _tool_docstring(tool: ToolDecl, source_signature: str) -> str:
    doc_lines = list(tool.docstrings)
    if doc_lines:
        doc_lines.append("")
    doc_lines.append(f"AXON source: {source_signature}")
    return "\n".join(doc_lines)


def _indent_docstring(content: str) -> list[str]:
    safe = content.replace('"""', r'\"\"\"')
    lines = ['    """']
    for line in safe.split("\n"):
        lines.append(f"    {line}" if line else "")
    lines.append('    """')
    return lines


def _axon_body_comment_lines(body: str) -> list[str]:
    if not body.strip():
        return ["    # AXON body: <empty>"]

    body_lines = body.split("\n")
    comments: list[str] = []
    for index, line in enumerate(body_lines):
        prefix = "    # AXON body:" if index == 0 else "    #"
        comments.append(f"{prefix} {line}".rstrip())
    return comments


def _agent_metadata_lines(agent: AgentDecl) -> list[str]:
    lines = [
        f"AXON_AGENT_TOOLS    = {_py_list_literal(agent.tools)}",
        f"AXON_AGENT_MEMORY   = {_py_string_or_none(agent.memory.kind if agent.memory else None)}",
        f"AXON_AGENT_SCHEDULE = {_py_string_or_none(_find_schedule(agent))}",
        f"AXON_AGENT_MODEL    = {_py_string_or_none(agent.model)}",
    ]
    if agent.memory and agent.memory.options:
        lines.append(f"AXON_AGENT_MEMORY_OPTIONS = {_py_dict_literal(agent.memory.options)}")
    else:
        lines.append("AXON_AGENT_MEMORY_OPTIONS = {}")
    return lines


def _find_schedule(agent: AgentDecl) -> str | None:
    for method in agent.methods:
        for annotation in method.annotations:
            if annotation.name == "schedule":
                if annotation.args:
                    return ", ".join(f"{key}: {value}" for key, value in annotation.args.items())
                return "enabled"
    return None


def _effective_model(model: str, config: "AxonConfig | None" = None) -> str:
    value = model.strip()
    if config is None:
        return value
    if value == "env.DEFAULT_MODEL" and config.default_model():
        return config.default_model() or value
    if not value and config.default_model():
        return config.default_model() or value
    return value


def _provider_model_defaults(model: str) -> tuple[str, str]:
    value = model.strip()
    if value.startswith("@") and "/" in value:
        provider, model_name = value[1:].split("/", 1)
        friendly_model = {
            ("anthropic", "claude-haiku"): "claude-haiku-20241022",
            ("anthropic", "claude-3-5-sonnet"): "claude-3-5-sonnet-20241022",
        }.get((provider, model_name), model_name)
        return provider, friendly_model
    if value.startswith("env."):
        return "env", value
    return "default", value or "default"


def _parse_generic(type_expr: str) -> tuple[str, list[str]] | None:
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*<(.+)>$", type_expr.strip())
    if not match:
        return None

    name = match.group(1)
    inner = match.group(2).strip()
    if not _outer_angle_brackets_are_balanced(type_expr.strip(), name):
        return None
    return name, _split_top_level(inner, ",")


def _is_generic(type_expr: str, generic_name: str) -> bool:
    parsed = _parse_generic(type_expr)
    return parsed is not None and parsed[0] == generic_name


def _outer_angle_brackets_are_balanced(type_expr: str, name: str) -> bool:
    prefix = f"{name}<"
    compact = re.sub(r"\s+", "", type_expr)
    if not compact.startswith(prefix.replace(" ", "")) or not compact.endswith(">"):
        return False
    depth = 0
    in_string = False
    escape = False
    for i, c in enumerate(compact[len(name):], start=len(name)):
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
            depth += 1
        elif c == ">":
            depth -= 1
            if depth == 0 and i != len(compact) - 1:
                return False
            if depth < 0:
                return False
    return depth == 0


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


def _py_list_literal(values: list[str]) -> str:
    return "[" + ", ".join(_py_string_or_none(value) for value in values) + "]"


def _py_dict_literal(values: dict[str, str]) -> str:
    pairs = ", ".join(
        f"{_py_string_or_none(key)}: {_py_string_or_none(value)}"
        for key, value in values.items()
    )
    return "{" + pairs + "}"


def _py_string_or_none(value: str | None) -> str:
    if value is None:
        return "None"
    return f'"{_escape_py_string(value)}"'


def _escape_py_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
