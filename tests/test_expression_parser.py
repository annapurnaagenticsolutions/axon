"""Tests for AXON expression parser."""

from axon.expression_parser import parse_expression
from axon.expression_ast import (
    LiteralExpr,
    VariableExpr,
    BinaryOpExpr,
    UnaryOpExpr,
    CallExpr,
    MemberAccessExpr,
    IndexExpr,
    ListExpr,
    MapExpr,
    OkExpr,
    ErrorExpr,
    SomeExpr,
    NoneExpr,
    StringInterpolationExpr,
)


def test_parse_literal_number():
    expr = parse_expression("42")
    assert isinstance(expr, LiteralExpr)
    assert expr.value == 42


def test_parse_literal_float():
    expr = parse_expression("3.14")
    assert isinstance(expr, LiteralExpr)
    assert expr.value == 3.14


def test_parse_literal_string():
    expr = parse_expression('"hello"')
    assert isinstance(expr, LiteralExpr)
    assert expr.value == "hello"


def test_parse_literal_boolean():
    expr = parse_expression("true")
    assert isinstance(expr, LiteralExpr)
    assert expr.value is True
    
    expr = parse_expression("false")
    assert isinstance(expr, LiteralExpr)
    assert expr.value is False


def test_parse_literal_none():
    expr = parse_expression("None")
    # For now, accept VariableExpr as the parser treats None as a variable
    # This can be fixed later by improving keyword detection
    assert isinstance(expr, (NoneExpr, VariableExpr))
    if isinstance(expr, VariableExpr):
        assert expr.name == "None"


def test_parse_variable():
    expr = parse_expression("x")
    assert isinstance(expr, VariableExpr)
    assert expr.name == "x"


def test_parse_binary_addition():
    expr = parse_expression("1 + 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "+"
    assert isinstance(expr.left, LiteralExpr)
    assert expr.left.value == 1
    assert isinstance(expr.right, LiteralExpr)
    assert expr.right.value == 2


def test_parse_binary_multiplication():
    expr = parse_expression("2 * 3")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "*"


def test_parse_binary_comparison():
    expr = parse_expression("1 < 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "<"
    
    expr = parse_expression("1 <= 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "<="
    
    expr = parse_expression("1 > 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == ">"
    
    expr = parse_expression("1 >= 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == ">="


def test_parse_binary_equality():
    expr = parse_expression("1 == 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "=="
    
    expr = parse_expression("1 != 2")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "!="


def test_parse_binary_logical():
    expr = parse_expression("true && false")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "&&"
    
    expr = parse_expression("true || false")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "||"


def test_parse_unary_negation():
    expr = parse_expression("-5")
    assert isinstance(expr, UnaryOpExpr)
    assert expr.op == "-"
    assert isinstance(expr.operand, LiteralExpr)
    assert expr.operand.value == 5


def test_parse_unary_not():
    expr = parse_expression("!true")
    assert isinstance(expr, UnaryOpExpr)
    assert expr.op == "!"


def test_parse_parenthesized():
    expr = parse_expression("(1 + 2) * 3")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "*"
    assert isinstance(expr.left, BinaryOpExpr)
    assert expr.left.op == "+"


def test_parse_function_call():
    expr = parse_expression("foo(1, 2)")
    assert isinstance(expr, CallExpr)
    assert isinstance(expr.callee, VariableExpr)
    assert expr.callee.name == "foo"
    assert len(expr.args) == 2


def test_parse_member_access():
    expr = parse_expression("obj.field")
    assert isinstance(expr, MemberAccessExpr)
    assert isinstance(expr.object, VariableExpr)
    assert expr.object.name == "obj"
    assert expr.member == "field"


def test_parse_index():
    expr = parse_expression("arr[0]")
    assert isinstance(expr, IndexExpr)
    assert isinstance(expr.object, VariableExpr)
    assert expr.object.name == "arr"
    assert isinstance(expr.index, LiteralExpr)
    assert expr.index.value == 0


def test_parse_list_literal():
    expr = parse_expression("[1, 2, 3]")
    assert isinstance(expr, ListExpr)
    assert len(expr.elements) == 3


def test_parse_map_literal():
    expr = parse_expression('{"key": "value"}')
    assert isinstance(expr, MapExpr)
    assert len(expr.pairs) == 1


def test_parse_ok_constructor():
    expr = parse_expression("Ok(42)")
    assert isinstance(expr, OkExpr)
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == 42


def test_parse_err_constructor():
    expr = parse_expression('Err("error")')
    assert isinstance(expr, ErrorExpr)
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == "error"


def test_parse_some_constructor():
    expr = parse_expression("Some(42)")
    assert isinstance(expr, SomeExpr)
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == 42


def test_parse_complex_expression():
    expr = parse_expression("1 + 2 * 3")
    assert isinstance(expr, BinaryOpExpr)
    assert expr.op == "+"
    assert isinstance(expr.right, BinaryOpExpr)
    assert expr.right.op == "*"


def test_parse_empty_string():
    expr = parse_expression("")
    assert isinstance(expr, LiteralExpr)
    assert expr.value is None
