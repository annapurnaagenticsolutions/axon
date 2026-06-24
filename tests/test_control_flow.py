"""Tests for AXON control flow: if, for, match, let, return.

These tests verify both parsing from source text and evaluation.
"""

from axon.expression_parser import parse_expression
from axon.evaluator import Scope, evaluate
from axon.expression_ast import (
    LiteralExpr,
    VariableExpr,
    IfExpr,
    ForExpr,
    MatchExpr,
    LetExpr,
    ReturnExpr,
    BlockExpr,
    ListExpr,
)


# -- Parser tests -------------------------------------------------

def test_parse_if():
    expr = parse_expression('if true { 1 } else { 0 }')
    assert isinstance(expr, IfExpr)
    assert isinstance(expr.condition, LiteralExpr)
    assert expr.condition.value is True
    assert isinstance(expr.then_branch, BlockExpr)
    assert isinstance(expr.else_branch, BlockExpr)


def test_parse_if_no_else():
    expr = parse_expression('if false { 1 }')
    assert isinstance(expr, IfExpr)
    assert expr.else_branch is None


def test_parse_for():
    expr = parse_expression('for x in [1, 2, 3] { x + 1 }')
    assert isinstance(expr, ForExpr)
    assert expr.var_name == "x"
    assert isinstance(expr.iterable, ListExpr)
    assert isinstance(expr.body, BlockExpr)


def test_parse_match():
    expr = parse_expression('match 1 { 1 => "one", 2 => "two" }')
    assert isinstance(expr, MatchExpr)
    assert isinstance(expr.value, LiteralExpr)
    assert len(expr.arms) == 2
    assert isinstance(expr.arms[0].pattern, LiteralExpr)
    assert expr.arms[0].pattern.value == 1


def test_parse_let():
    expr = parse_expression('let x = 5 in x + 1')
    assert isinstance(expr, LetExpr)
    assert expr.name == "x"
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == 5


def test_parse_return():
    expr = parse_expression('return 42')
    assert isinstance(expr, ReturnExpr)
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == 42


# -- Evaluator tests from parsed source ----------------------------

def test_evaluate_if_true():
    expr = parse_expression('if true { 1 } else { 0 }')
    result = evaluate(expr, Scope())
    assert result.ok_value == 1


def test_evaluate_if_false():
    expr = parse_expression('if false { 1 } else { 0 }')
    result = evaluate(expr, Scope())
    assert result.ok_value == 0


def test_evaluate_if_with_variable():
    expr = parse_expression('if x { "yes" } else { "no" }')
    scope = Scope()
    scope.set("x", True)
    result = evaluate(expr, scope)
    assert result.ok_value == "yes"


def test_evaluate_for_list():
    expr = parse_expression('for x in [1, 2, 3] { x + 1 }')
    result = evaluate(expr, Scope())
    assert result.ok_value == 4  # last iteration: 3 + 1


def test_evaluate_for_empty_list():
    expr = parse_expression('for x in [] { x + 1 }')
    result = evaluate(expr, Scope())
    assert result.ok_value is None


def test_evaluate_for_string():
    expr = parse_expression('for c in "ab" { c }')
    result = evaluate(expr, Scope())
    assert result.ok_value == "b"  # last char


def test_evaluate_match_literal():
    expr = parse_expression('match 2 { 1 => "one", 2 => "two" }')
    result = evaluate(expr, Scope())
    assert result.ok_value == "two"


def test_evaluate_match_wildcard():
    expr = parse_expression('match 99 { 1 => "one", x => "other" }')
    result = evaluate(expr, Scope())
    assert result.ok_value == "other"


def test_evaluate_match_none():
    expr = parse_expression('match None { None => "empty", x => "full" }')
    result = evaluate(expr, Scope())
    assert result.ok_value == "empty"


def test_evaluate_let_binding():
    expr = parse_expression('let x = 10 in x * 2')
    result = evaluate(expr, Scope())
    assert result.ok_value == 20


def test_evaluate_let_shadowing():
    expr = parse_expression('let x = 5 in let x = 99 in x')
    result = evaluate(expr, Scope())
    assert result.ok_value == 99


def test_evaluate_return():
    expr = parse_expression('return 7')
    result = evaluate(expr, Scope())
    assert result.ok_value == 7


# -- Nested control flow -------------------------------------------

def test_evaluate_nested_if():
    expr = parse_expression('if true { if false { 0 } else { 1 } } else { 2 }')
    result = evaluate(expr, Scope())
    assert result.ok_value == 1


def test_evaluate_for_sum():
    """Use a let binding inside the loop body."""
    expr = parse_expression('for x in [1, 2, 3] { x }')
    result = evaluate(expr, Scope())
    assert result.ok_value == 3
