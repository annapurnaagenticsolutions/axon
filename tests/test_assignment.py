"""Tests for AXON assignment expressions."""

from axon.expression_parser import parse_expression
from axon.expression_ast import AssignExpr, VariableExpr, LiteralExpr
from axon.evaluator import Scope, evaluate


# -- Parser tests -------------------------------------------------

def test_parse_assignment():
    expr = parse_expression('x = 5')
    assert isinstance(expr, AssignExpr)
    assert expr.name == 'x'
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == 5


def test_parse_assignment_right_associative():
    expr = parse_expression('x = y = 3')
    assert isinstance(expr, AssignExpr)
    assert expr.name == 'x'
    assert isinstance(expr.value, AssignExpr)
    assert expr.value.name == 'y'
    assert expr.value.value.value == 3


def test_parse_comparison_not_assignment():
    """x == 5 should be equality, not assignment."""
    expr = parse_expression('x == 5')
    assert not isinstance(expr, AssignExpr)
    # Should be BinaryOpExpr with op ==
    from axon.expression_ast import BinaryOpExpr
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == '=='


def test_parse_let_not_confused_with_assignment():
    """let x = 5 in x should still parse as LetExpr."""
    expr = parse_expression('let x = 5 in x')
    from axon.expression_ast import LetExpr
    assert isinstance(expr, LetExpr)


# -- Evaluator tests ----------------------------------------------

def test_evaluate_simple_assignment():
    scope = Scope()
    expr = parse_expression('x = 42')
    result = evaluate(expr, scope)
    assert result.ok_value == 42
    assert scope.get('x') == 42


def test_evaluate_assignment_then_read():
    scope = Scope()
    expr = parse_expression('x = 10')
    evaluate(expr, scope)
    expr2 = parse_expression('x + 5')
    result = evaluate(expr2, scope)
    assert result.ok_value == 15


def test_evaluate_chained_assignment():
    scope = Scope()
    expr = parse_expression('x = y = 7')
    result = evaluate(expr, scope)
    assert result.ok_value == 7
    assert scope.get('x') == 7
    assert scope.get('y') == 7


def test_evaluate_assignment_in_block():
    scope = Scope()
    expr = parse_expression('x = 1; x = x + 1; x')
    result = evaluate(expr, scope)
    assert result.ok_value == 2
    assert scope.get('x') == 2


def test_evaluate_assignment_with_expression():
    scope = Scope()
    scope.set('a', 3)
    expr = parse_expression('b = a * 2 + 1')
    result = evaluate(expr, scope)
    assert result.ok_value == 7
    assert scope.get('b') == 7


def test_evaluate_assignment_updates_existing():
    scope = Scope()
    scope.set('x', 1)
    expr = parse_expression('x = 99')
    result = evaluate(expr, scope)
    assert result.ok_value == 99
    assert scope.get('x') == 99
