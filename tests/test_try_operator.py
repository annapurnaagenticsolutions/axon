"""Tests for AXON try operator (?)."""

from axon.expression_parser import parse_expression
from axon.expression_ast import TryExpr, LiteralExpr, OkExpr, ErrorExpr, SomeExpr, NoneExpr
from axon.evaluator import Scope, evaluate
from result import Ok, Err


# -- Parser tests -------------------------------------------------

def test_parse_try_on_ok():
    expr = parse_expression('Ok(42)?')
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, OkExpr)


def test_parse_try_on_err():
    expr = parse_expression('Err("fail")?')
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, ErrorExpr)


def test_parse_try_on_some():
    expr = parse_expression('Some(7)?')
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, SomeExpr)


def test_parse_try_on_none():
    expr = parse_expression('None?')
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, NoneExpr)


def test_parse_try_on_variable():
    expr = parse_expression('x?')
    from axon.expression_ast import VariableExpr
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, VariableExpr)


# -- Evaluator tests ----------------------------------------------

def test_evaluate_try_ok():
    scope = Scope()
    expr = parse_expression('Ok(42)?')
    result = evaluate(expr, scope)
    assert result.ok_value == 42


def test_evaluate_try_err():
    scope = Scope()
    expr = parse_expression('Err("fail")?')
    result = evaluate(expr, scope)
    assert isinstance(result, Err)
    assert "fail" in result.err_value.message


def test_evaluate_try_some():
    scope = Scope()
    expr = parse_expression('Some(7)?')
    result = evaluate(expr, scope)
    assert result.ok_value == 7


def test_evaluate_try_none():
    scope = Scope()
    expr = parse_expression('None?')
    result = evaluate(expr, scope)
    assert isinstance(result, Err)
    assert "None" in result.err_value.message


def test_evaluate_try_plain_value():
    """Try on a non-result, non-optional value just returns it."""
    scope = Scope()
    expr = parse_expression('5?')
    result = evaluate(expr, scope)
    assert result.ok_value == 5


def test_evaluate_try_variable_ok():
    scope = Scope()
    scope.set("r", {"ok": "hello"})
    expr = parse_expression('r?')
    result = evaluate(expr, scope)
    assert result.ok_value == "hello"


def test_evaluate_try_variable_err():
    scope = Scope()
    scope.set("r", {"err": "oops"})
    expr = parse_expression('r?')
    result = evaluate(expr, scope)
    assert isinstance(result, Err)


def test_evaluate_try_in_let():
    """let x = Ok(10)? in x + 1"""
    expr = parse_expression('let x = Ok(10)? in x + 1')
    result = evaluate(expr, Scope())
    assert result.ok_value == 11


def test_evaluate_try_propagates():
    """Err("bad")? should short-circuit in a block."""
    expr = parse_expression('let x = Err("bad")? in x + 1')
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
