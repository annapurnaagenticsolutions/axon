"""Tests for AXON mock tool registry."""

from result import Ok, Err

from axon.ast_nodes import Param, ToolDecl
from axon.expression_ast import LiteralExpr, StringInterpolationExpr, VariableExpr
from axon.tool_registry import MockToolRegistry, _infer_body_expr, _parse_default
from axon.tool_registry_errors import ToolError, ToolErrorKind


def _make_tool(name, params, body, parsed_body=None):
    return ToolDecl(
        name=name,
        params=params,
        return_type="Str",
        docstrings=[],
        body=body,
        parsed_body=parsed_body,
    )


def test_register_tool():
    registry = MockToolRegistry()
    tool = _make_tool("Greet", [Param(name="name", type_str="Str")], '"Hello, {name}!"')
    registry.register(tool)
    assert "Greet" in registry
    assert registry.list_tools() == ["Greet"]


def test_dispatch_simple_literal():
    """Tool body is a plain literal — no args needed."""
    registry = MockToolRegistry()
    tool = _make_tool("SayHi", [], '"hi"')
    registry.register(tool)

    result = registry.dispatch("SayHi", {})
    assert isinstance(result, Ok)
    assert result.ok_value == "hi"


def test_dispatch_with_parsed_body():
    """Tool has a parsed StringInterpolationExpr body."""
    registry = MockToolRegistry()
    parsed = StringInterpolationExpr(
        line=1,
        parts=[
            LiteralExpr(line=1, value="Hello, "),
            VariableExpr(line=1, name="name"),
            LiteralExpr(line=1, value="!"),
        ],
    )
    tool = _make_tool(
        "Greet",
        [Param(name="name", type_str="Str")],
        '"Hello, {name}!"',
        parsed_body=parsed,
    )
    registry.register(tool)

    result = registry.dispatch("Greet", {"name": "World"})
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, World!"


def test_dispatch_without_parsed_body_infers_interpolation():
    """Tool has no parsed_body but raw body can be inferred."""
    registry = MockToolRegistry()
    tool = _make_tool(
        "Greet",
        [Param(name="name", type_str="Str")],
        '"Hello, {name}!"',
        parsed_body=None,
    )
    registry.register(tool)

    result = registry.dispatch("Greet", {"name": "World"})
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, World!"


def test_dispatch_missing_tool():
    registry = MockToolRegistry()
    result = registry.dispatch("MissingTool", {})
    assert isinstance(result, Err)
    assert result.err_value.kind == ToolErrorKind.NOT_FOUND


def test_dispatch_missing_required_argument():
    registry = MockToolRegistry()
    tool = _make_tool(
        "Greet",
        [Param(name="name", type_str="Str")],
        '"Hello, {name}!"',
    )
    registry.register(tool)

    result = registry.dispatch("Greet", {})
    assert isinstance(result, Err)
    assert result.err_value.kind == ToolErrorKind.MISSING_ARGUMENT


def test_dispatch_with_default_argument():
    """Missing argument that has a default should use the default."""
    registry = MockToolRegistry()
    parsed = StringInterpolationExpr(
        line=1,
        parts=[
            LiteralExpr(line=1, value="Hello, "),
            VariableExpr(line=1, name="name"),
            LiteralExpr(line=1, value="!"),
        ],
    )
    tool = _make_tool(
        "Greet",
        [Param(name="name", type_str="Str", default='"Guest"')],
        '"Hello, {name}!"',
        parsed_body=parsed,
    )
    registry.register(tool)

    result = registry.dispatch("Greet", {})
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, Guest!"


def test_dispatch_numeric_body():
    registry = MockToolRegistry()
    tool = _make_tool("Double", [Param(name="x", type_str="Int")], "x * 2")
    registry.register(tool)
    # Without parsed_body, raw "x * 2" cannot be inferred — returns NotImplemented
    result = registry.dispatch("Double", {"x": 5})
    assert isinstance(result, Err)
    assert result.err_value.kind == ToolErrorKind.NOT_IMPLEMENTED


def test_dispatch_numeric_body_with_parsed_body():
    from axon.expression_ast import BinaryOpExpr, VariableExpr, LiteralExpr
    registry = MockToolRegistry()
    parsed = BinaryOpExpr(
        line=1,
        op="*",
        left=VariableExpr(line=1, name="x"),
        right=LiteralExpr(line=1, value=2),
    )
    tool = _make_tool(
        "Double",
        [Param(name="x", type_str="Int")],
        "x * 2",
        parsed_body=parsed,
    )
    registry.register(tool)

    result = registry.dispatch("Double", {"x": 5})
    assert isinstance(result, Ok)
    assert result.ok_value == 10


def test_register_all_from_declarations():
    """register_all picks out only ToolDecl instances."""
    from axon.ast_nodes import AgentDecl

    registry = MockToolRegistry()
    tool = _make_tool("Greet", [Param(name="name", type_str="Str")], '"hi"')
    agent = AgentDecl(
        name="Bot",
        model="@mock/model",
        tools=[],
        memory=None,
        methods=[],
    )

    registry.register_all([tool, agent, tool])
    assert registry.list_tools() == ["Greet"]


def test_parse_default_string():
    assert _parse_default('"hello"') == "hello"


def test_parse_default_int():
    assert _parse_default("42") == 42


def test_parse_default_float():
    assert _parse_default("3.14") == 3.14


def test_parse_default_bool():
    assert _parse_default("true") is True
    assert _parse_default("false") is False


def test_parse_default_none():
    assert _parse_default("None") is None


def test_infer_body_expr_string():
    expr = _infer_body_expr('"hello"')
    assert isinstance(expr, LiteralExpr)
    assert expr.value == "hello"


def test_infer_body_expr_interpolation():
    expr = _infer_body_expr('"Hello, {name}!"')
    assert isinstance(expr, StringInterpolationExpr)
    assert len(expr.parts) == 3


def test_infer_body_expr_number():
    expr = _infer_body_expr("42")
    assert isinstance(expr, LiteralExpr)
    assert expr.value == 42


def test_infer_body_expr_bool():
    expr = _infer_body_expr("true")
    assert isinstance(expr, LiteralExpr)
    assert expr.value is True


def test_infer_body_expr_variable():
    expr = _infer_body_expr("x")
    assert isinstance(expr, VariableExpr)
    assert expr.name == "x"


def test_infer_body_expr_unknown_returns_none():
    assert _infer_body_expr("x + y") is None
    assert _infer_body_expr("foo()") is None
