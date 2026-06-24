"""Tests for AXON act expression parsing and evaluation."""

from axon.expression_parser import parse_expression
from axon.expression_ast import ActExpr, VariableExpr, LiteralExpr
from axon.evaluator import Scope, evaluate
from result import Ok, Err


# -- Parser tests -------------------------------------------------

def test_parse_act_no_args():
    expr = parse_expression('act Greet()')
    assert isinstance(expr, ActExpr)
    assert expr.tool_name == "Greet"
    assert expr.args == []


def test_parse_act_with_args():
    expr = parse_expression('act Greet(name: "World")')
    assert isinstance(expr, ActExpr)
    assert expr.tool_name == "Greet"
    assert len(expr.args) == 1
    assert expr.args[0][0] == "name"
    assert isinstance(expr.args[0][1], LiteralExpr)


def test_parse_act_with_multiple_args():
    expr = parse_expression('act Add(repo: "foo", issue: 42)')
    assert isinstance(expr, ActExpr)
    assert expr.tool_name == "Add"
    assert len(expr.args) == 2
    assert expr.args[0][0] == "repo"
    assert expr.args[1][0] == "issue"


def test_parse_act_with_variable_arg():
    expr = parse_expression('act Greet(name: user)')
    assert isinstance(expr, ActExpr)
    assert expr.args[0][0] == "name"
    assert isinstance(expr.args[0][1], VariableExpr)


def test_parse_act_with_try():
    expr = parse_expression('act Fetch()?')
    from axon.expression_ast import TryExpr
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, ActExpr)


# -- Evaluator tests ----------------------------------------------

def test_evaluate_act_with_mock_dispatch():
    """Test ActExpr evaluation with a mock kwargs dispatch function."""
    expr = parse_expression('act Greet(name: "World")')
    scope = Scope()

    def mock_dispatch(name: str, kwargs: dict) -> Result[Any, any]:
        assert name == "Greet"
        assert kwargs == {"name": "World"}
        return Ok(f"Hello, {kwargs['name']}!")

    result = evaluate(expr, scope, kwargs_dispatch_fn=mock_dispatch)
    assert result.ok_value == "Hello, World!"


def test_evaluate_act_with_variable_arg():
    expr = parse_expression('act Greet(name: user)')
    scope = Scope()
    scope.set("user", "Alice")

    def mock_dispatch(name: str, kwargs: dict) -> Result[Any, any]:
        return Ok(f"Hello, {kwargs['name']}!")

    result = evaluate(expr, scope, kwargs_dispatch_fn=mock_dispatch)
    assert result.ok_value == "Hello, Alice!"


def test_evaluate_act_no_dispatch():
    expr = parse_expression('act Greet()')
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert "No kwargs dispatch" in result.err_value.message


def test_evaluate_act_with_try_ok():
    from axon.expression_ast import TryExpr
    expr = parse_expression('act Greet(name: "World")?')
    scope = Scope()

    def mock_dispatch(name: str, kwargs: dict) -> Result[Any, any]:
        return Ok({"ok": "success"})

    result = evaluate(expr, scope, kwargs_dispatch_fn=mock_dispatch)
    assert result.ok_value == "success"


def test_evaluate_act_with_try_err():
    from axon.expression_ast import TryExpr
    expr = parse_expression('act Greet(name: "World")?')
    scope = Scope()

    def mock_dispatch(name: str, kwargs: dict) -> Result[Any, any]:
        return Ok({"err": "failed"})

    result = evaluate(expr, scope, kwargs_dispatch_fn=mock_dispatch)
    assert isinstance(result, Err)
    assert "failed" in result.err_value.message


def test_evaluate_act_in_if():
    expr = parse_expression('if true { act Greet(name: "hi") }')
    scope = Scope()

    def mock_dispatch(name: str, kwargs: dict) -> Result[Any, any]:
        return Ok("greeted")

    result = evaluate(expr, scope, kwargs_dispatch_fn=mock_dispatch)
    assert result.ok_value == "greeted"
