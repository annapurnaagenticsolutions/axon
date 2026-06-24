"""Tests for sandboxed tool execution."""

from __future__ import annotations

import time

from result import Ok

from axon.sandbox import SandboxConfig, SandboxedToolRegistry
from axon.tool_registry import MockToolRegistry
from axon.tool_registry_errors import ToolErrorKind


def _make_slow_tool_registry() -> MockToolRegistry:
    """Create a registry with a tool that sleeps when dispatched."""
    from axon.ast_nodes import Param, ToolDecl
    from axon.expression_ast import LiteralExpr

    tool = ToolDecl(
        name="Sleep",
        params=[Param(name="duration", type_str="Int", default=None)],
        return_type="Str",
        body="\"done\"",
        parsed_body=LiteralExpr(value="done", line=1),
        docstrings=[],
        line=1,
    )
    registry = MockToolRegistry()
    registry.register(tool)
    return registry


def test_sandbox_denied_tool():
    registry = _make_slow_tool_registry()
    sandbox = SandboxedToolRegistry(registry, SandboxConfig(denied_tools={"Sleep"}))
    result = sandbox.dispatch("Sleep", {"duration": 0})
    assert isinstance(result, type(Ok(None))) is False  # Err
    assert result.is_err
    assert result.err_value.kind == ToolErrorKind.SANDBOX_VIOLATION
    assert "denied by sandbox" in result.err_value.message


def test_sandbox_timeout():
    """A tool that sleeps longer than the timeout should be killed."""
    from axon.ast_nodes import Param, ToolDecl

    # Create a tool whose body does actual Python sleep
    # Since evaluate runs Python code, we can make it slow
    # But tool bodies are AXON expressions, not arbitrary Python.
    # Instead, monkey-patch the registry dispatch to sleep.
    registry = MockToolRegistry()
    original_dispatch = registry.dispatch

    def slow_dispatch(name: str, kwargs: dict, max_depth: int | None = None):
        time.sleep(0.5)
        return original_dispatch(name, kwargs, max_depth=max_depth)

    registry.dispatch = slow_dispatch  # type: ignore[method-assign]

    sandbox = SandboxedToolRegistry(registry, SandboxConfig(timeout_ms=100))
    result = sandbox.dispatch("Greet", {"name": "World"})
    assert result.is_err
    assert result.err_value.kind == ToolErrorKind.TIMEOUT
    assert "exceeded sandbox timeout" in result.err_value.message


def test_sandbox_allows_normal_tool():
    from axon.ast_nodes import Param, ToolDecl
    from axon.expression_ast import LiteralExpr

    tool = ToolDecl(
        name="Greet",
        params=[Param(name="name", type_str="Str", default=None)],
        return_type="Str",
        body='"Hello, {name}!"',
        parsed_body=LiteralExpr(value="Hello, {name}!", line=1),
        docstrings=[],
        line=1,
    )
    registry = MockToolRegistry()
    registry.register(tool)
    sandbox = SandboxedToolRegistry(registry, SandboxConfig(timeout_ms=5000))
    result = sandbox.dispatch("Greet", {"name": "World"})
    assert result.is_ok
    assert result.ok_value == "Hello, World!"


def test_sandbox_max_eval_depth():
    """Deeply nested expressions should hit the depth limit."""
    from axon.ast_nodes import Param, ToolDecl
    from axon.expression_ast import BinaryOpExpr, LiteralExpr, VariableExpr

    # Build a left-nested binary expression: (((1 + 1) + 1) + 1) ...
    # This will recurse deeply in evaluate()
    depth = 50
    expr: BinaryOpExpr = LiteralExpr(value=1, line=1)
    for _ in range(depth):
        expr = BinaryOpExpr(op="+", left=expr, right=LiteralExpr(value=1, line=1), line=1)

    tool = ToolDecl(
        name="Deep",
        params=[],
        return_type="Int",
        body="1",
        parsed_body=expr,
        docstrings=[],
        line=1,
    )
    registry = MockToolRegistry()
    registry.register(tool)
    # Depth limit of 10 should catch the 50-level nesting
    sandbox = SandboxedToolRegistry(registry, SandboxConfig(max_eval_depth=10))
    result = sandbox.dispatch("Deep", {})
    assert result.is_err
    assert result.err_value.kind == ToolErrorKind.EVALUATION_FAILED
    assert "exceeded sandbox limit" in result.err_value.message
