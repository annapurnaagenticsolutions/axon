"""Mock tool registry for AXON.

Registers ToolDecl objects and dispatches tool calls by evaluating
the tool's parsed body expression with a scoped argument map.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from result import Result, Ok, Err

from axon.ast_nodes import Param, ToolDecl

from axon.evaluator import Scope, evaluate, reset_eval_depth
from axon.expression_ast import LiteralExpr, NoneExpr, StringInterpolationExpr, VariableExpr
from axon.tool_registry_errors import ToolError, ToolErrorKind
from axon.type_checker import validate_runtime_type


class MockToolRegistry:
    """Registry that stores ToolDecl definitions and evaluates them on dispatch."""

    def __init__(self, max_depth: int | None = None, builtins: dict[str, Any] | None = None) -> None:
        self._tools: dict[str, ToolDecl] = {}
        self._max_depth = max_depth
        self._builtins = builtins or {}

    def register(self, tool: ToolDecl) -> None:
        """Register a tool declaration."""
        self._tools[tool.name] = tool

    def register_all(self, declarations: list) -> None:
        """Register every ToolDecl found in a list of parsed declarations."""
        for decl in declarations:
            if isinstance(decl, ToolDecl):
                self.register(decl)

    def dispatch(
        self,
        name: str,
        kwargs: dict[str, Any],
        max_depth: int | None = None,
    ) -> Result[Any, ToolError]:
        """Dispatch a tool call with keyword arguments.

        Steps:
        1. Look up the tool by name.
        2. Validate that required arguments are present.
        3. Build an evaluation scope from the arguments.
        4. Evaluate the tool's parsed_body expression.
        5. Return the result.

        Args:
            name: Tool name (e.g. "Greet").
            kwargs: Keyword arguments mapping parameter names to values.
            max_depth: Override the default max_eval_depth for this dispatch.

        Returns:
            Ok(value) on success, Err(ToolError) on failure.
        """
        tool = self._tools.get(name)
        if tool is None:
            return Err(
                ToolError(
                    kind=ToolErrorKind.NOT_FOUND,
                    message=f"Tool '{name}' is not defined",
                    line=0,
                )
            )

        # Validate required arguments
        provided = set(kwargs.keys())
        for param in tool.params:
            if param.default is None and param.name not in provided:
                return Err(
                    ToolError(
                        kind=ToolErrorKind.MISSING_ARGUMENT,
                        message=(
                            f"Tool '{name}' missing required argument: "
                            f"{param.name}: {param.type_str}"
                        ),
                        line=tool.line,
                    )
                )

        # Validate argument types at runtime
        for param in tool.params:
            if param.name in kwargs:
                err = validate_runtime_type(kwargs[param.name], param.type_str)
                if err:
                    return Err(
                        ToolError(
                            kind=ToolErrorKind.TYPE_MISMATCH,
                            message=f"Tool '{name}' argument '{param.name}': {err} (expected {param.type_str})",
                            line=tool.line,
                        )
                    )

        # Build evaluation scope (pre-populate with runtime builtins)
        scope = Scope()
        for name, value in self._builtins.items():
            scope.set(name, value)
        for param in tool.params:
            if param.name in kwargs:
                scope.set(param.name, kwargs[param.name])
            elif param.default is not None:
                # Try to parse the default value
                scope.set(param.name, _parse_default(param.default))

        # Evaluate tool body
        body_expr = tool.parsed_body
        if body_expr is None:
            # Fallback: try to create a simple expression from raw body text
            body_expr = _infer_body_expr(tool.body)
        elif (
            isinstance(body_expr, LiteralExpr)
            and isinstance(body_expr.value, str)
            and re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", body_expr.value)
        ):
            # The expression parser produced a plain LiteralExpr for a string
            # that contains interpolation patterns — use the inferred version.
            inferred = _infer_body_expr(tool.body)
            if inferred is not None:
                body_expr = inferred

        if body_expr is None:
            return Err(
                ToolError(
                    kind=ToolErrorKind.NOT_IMPLEMENTED,
                    message=(
                        f"Tool '{name}' has no parsed body and its raw body "
                        f"cannot be evaluated: {tool.body[:60]!r}"
                    ),
                    line=tool.line,
                )
            )

        reset_eval_depth()
        effective_depth = max_depth if max_depth is not None else self._max_depth
        eval_result = evaluate(body_expr, scope, max_depth=effective_depth)
        if isinstance(eval_result, Err):
            return Err(
                ToolError(
                    kind=ToolErrorKind.EVALUATION_FAILED,
                    message=f"Tool '{name}' body evaluation failed: {eval_result.err_value}",
                    line=tool.line,
                )
            )

        return Ok(eval_result.ok_value)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        """Return a list of registered tool names."""
        return list(self._tools.keys())


def _parse_default(value_str: str) -> Any:
    """Parse a default value string into a Python value."""
    value_str = value_str.strip()
    if value_str == "true":
        return True
    if value_str == "false":
        return False
    if value_str == "None":
        return None
    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1]
    try:
        if "." in value_str:
            return float(value_str)
        return int(value_str)
    except ValueError:
        return value_str


def _infer_body_expr(body_text: str) -> Optional[Any]:
    """Infer a simple expression from raw body text when parsed_body is missing.

    Handles:
    - Plain string literals: "Hello, World!"
    - String literals with interpolation: "Hello, {name}!"
    - Plain numeric literals
    - Simple variable references
    """
    text = body_text.strip()
    if not text:
        return LiteralExpr(line=0, value=None)

    # String literal (including interpolation)
    if text.startswith('"') and text.endswith('"'):
        inner = text[1:-1]
        # Check for interpolation
        parts: list[Any] = []
        last = 0
        for m in re.finditer(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", inner):
            if m.start() > last:
                parts.append(LiteralExpr(line=0, value=inner[last:m.start()]))
            parts.append(VariableExpr(line=0, name=m.group(1)))
            last = m.end()
        if last < len(inner):
            parts.append(LiteralExpr(line=0, value=inner[last:]))

        if len(parts) == 1 and isinstance(parts[0], LiteralExpr):
            return parts[0]
        return StringInterpolationExpr(line=0, parts=parts)

    # Boolean literals
    if text == "true":
        return LiteralExpr(line=0, value=True)
    if text == "false":
        return LiteralExpr(line=0, value=False)
    if text == "None":
        return NoneExpr(line=0)

    # Numeric literal
    try:
        if "." in text:
            return LiteralExpr(line=0, value=float(text))
        return LiteralExpr(line=0, value=int(text))
    except ValueError:
        pass

    # Variable reference
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        return VariableExpr(line=0, name=text)

    # Cannot infer
    return None
