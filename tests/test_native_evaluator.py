"""Tests for the native Rust evaluator bridge."""

import json
import pytest
from result import Ok, Err

from axon.evaluator import Scope
from axon.evaluator_errors import EvalError
from axon.expression_ast import (
    LiteralExpr,
    VariableExpr,
    BinaryOpExpr,
    UnaryOpExpr,
    IfExpr,
    BlockExpr,
    LetExpr,
    ListExpr,
    MapExpr,
    MemberAccessExpr,
    IndexExpr,
    StringInterpolationExpr,
    OkExpr,
    ErrorExpr,
    SomeExpr,
    NoneExpr,
    TryExpr,
    ForExpr,
    MatchArm,
    MatchExpr,
    ActExpr,
    ThinkExpr,
    ModelCallExpr,
)
from axon.native_evaluator import (
    evaluate,
    _is_pure,
    _expr_to_json,
    _scope_to_json,
)


def _lit(value, line=0):
    return LiteralExpr(line=line, value=value)


def _var(name, line=0):
    return VariableExpr(line=line, name=name)


class TestIsPure:
    def test_literal_is_pure(self):
        assert _is_pure(_lit(42))

    def test_variable_is_pure(self):
        assert _is_pure(_var("x"))

    def test_binary_op_pure(self):
        expr = BinaryOpExpr(line=0, op="+", left=_lit(1), right=_lit(2))
        assert _is_pure(expr)

    def test_act_not_pure(self):
        expr = ActExpr(line=0, tool_name="search", args=[("q", _lit("test"))])
        assert not _is_pure(expr)

    def test_think_not_pure(self):
        expr = ThinkExpr(line=0, message=_lit("hello"))
        assert not _is_pure(expr)

    def test_model_call_not_pure(self):
        expr = ModelCallExpr(line=0, prompt=_lit("hello"))
        assert not _is_pure(expr)

    def test_nested_act_not_pure(self):
        expr = IfExpr(
            line=0,
            condition=_lit(True),
            then_branch=ActExpr(line=0, tool_name="t", args=[]),
            else_branch=None,
        )
        assert not _is_pure(expr)

    def test_let_with_pure_body(self):
        expr = LetExpr(line=0, name="x", value=_lit(1), body=_var("x"))
        assert _is_pure(expr)

    def test_let_with_impure_body(self):
        expr = LetExpr(
            line=0, name="x", value=_lit(1),
            body=ActExpr(line=0, tool_name="t", args=[]),
        )
        assert not _is_pure(expr)


class TestExprToJson:
    def test_literal_int(self):
        result = _expr_to_json(_lit(42))
        assert result == {"kind": "literal", "value": {"int": 42}}

    def test_literal_string(self):
        result = _expr_to_json(_lit("hello"))
        assert result == {"kind": "literal", "value": {"string": "hello"}}

    def test_literal_bool(self):
        result = _expr_to_json(_lit(True))
        assert result == {"kind": "literal", "value": {"bool": True}}

    def test_literal_none(self):
        result = _expr_to_json(NoneExpr(line=0))
        assert result == {"kind": "none"}

    def test_variable(self):
        result = _expr_to_json(_var("x"))
        assert result == {"kind": "variable", "name": "x"}

    def test_binary_op(self):
        expr = BinaryOpExpr(line=0, op="+", left=_lit(1), right=_lit(2))
        result = _expr_to_json(expr)
        assert result["kind"] == "binary_op"
        assert result["op"] == "+"
        assert result["left"] == {"kind": "literal", "value": {"int": 1}}
        assert result["right"] == {"kind": "literal", "value": {"int": 2}}

    def test_if(self):
        expr = IfExpr(line=0, condition=_lit(True), then_branch=_lit("yes"), else_branch=_lit("no"))
        result = _expr_to_json(expr)
        assert result["kind"] == "if"
        assert "else_branch" in result

    def test_if_no_else(self):
        expr = IfExpr(line=0, condition=_lit(True), then_branch=_lit("yes"), else_branch=None)
        result = _expr_to_json(expr)
        assert result["kind"] == "if"
        assert "else_branch" not in result


class TestScopeToJson:
    def test_flat_scope(self):
        s = Scope()
        s.set("x", 42)
        s.set("y", "hello")
        result = _scope_to_json(s)
        assert result == {"x": 42, "y": "hello"}

    def test_child_scope(self):
        parent = Scope()
        parent.set("x", 1)
        child = parent.child()
        child.set("y", 2)
        result = _scope_to_json(child)
        assert result == {"x": 1, "y": 2}


class TestNativeEvaluate:
    """Tests that exercise the native evaluator bridge (requires axon_parser PyO3 module)."""

    def test_literal_int(self):
        result = evaluate(_lit(42), Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 42

    def test_literal_string(self):
        result = evaluate(_lit("hello"), Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "hello"

    def test_literal_bool(self):
        result = evaluate(_lit(True), Scope())
        assert isinstance(result, Ok)
        assert result.ok_value is True

    def test_none_expr(self):
        result = evaluate(NoneExpr(line=0), Scope())
        assert isinstance(result, Ok)
        assert result.ok_value is None

    def test_variable_lookup(self):
        s = Scope()
        s.set("x", 42)
        result = evaluate(_var("x"), s)
        assert isinstance(result, Ok)
        assert result.ok_value == 42

    def test_binary_add_ints(self):
        expr = BinaryOpExpr(line=0, op="+", left=_lit(3), right=_lit(4))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 7

    def test_binary_add_strings(self):
        expr = BinaryOpExpr(line=0, op="+", left=_lit("hello "), right=_lit("world"))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "hello world"

    def test_binary_sub(self):
        expr = BinaryOpExpr(line=0, op="-", left=_lit(10), right=_lit(3))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 7

    def test_binary_eq(self):
        expr = BinaryOpExpr(line=0, op="==", left=_lit(5), right=_lit(5))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value is True

    def test_unary_neg(self):
        expr = UnaryOpExpr(line=0, op="-", operand=_lit(5))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == -5

    def test_unary_not(self):
        expr = UnaryOpExpr(line=0, op="!", operand=_lit(True))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value is False

    def test_if_true(self):
        expr = IfExpr(line=0, condition=_lit(True), then_branch=_lit("yes"), else_branch=_lit("no"))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "yes"

    def test_if_false(self):
        expr = IfExpr(line=0, condition=_lit(False), then_branch=_lit("yes"), else_branch=_lit("no"))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "no"

    def test_block(self):
        expr = BlockExpr(line=0, statements=[_lit(1), _lit(2), _lit(3)])
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 3

    def test_let_in(self):
        expr = LetExpr(line=0, name="x", value=_lit(42), body=_var("x"))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 42

    def test_list(self):
        expr = ListExpr(line=0, elements=[_lit(1), _lit(2), _lit(3)])
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == [1, 2, 3]

    def test_string_interpolation(self):
        expr = StringInterpolationExpr(line=0, parts=[_lit("Hello, "), _lit("world")])
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "Hello, world"

    def test_ok_expr(self):
        expr = OkExpr(line=0, value=_lit(42))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert isinstance(result.ok_value, dict)
        assert result.ok_value["ok"] == 42

    def test_error_expr(self):
        expr = ErrorExpr(line=0, value=_lit("fail"))
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value["err"] == "fail"

    def test_try_ok(self):
        inner = OkExpr(line=0, value=_lit(42))
        expr = TryExpr(line=0, operand=inner)
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 42

    def test_for_loop(self):
        expr = ForExpr(
            line=0, var_name="x",
            iterable=ListExpr(line=0, elements=[_lit(1), _lit(2)]),
            body=_var("x"),
        )
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == 2

    def test_member_access(self):
        expr = MemberAccessExpr(
            line=0,
            object=MapExpr(line=0, pairs=[(_lit("name"), _lit("Alice"))]),
            member="name",
        )
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "Alice"

    def test_index_array(self):
        expr = IndexExpr(
            line=0,
            object=ListExpr(line=0, elements=[_lit("a"), _lit("b")]),
            index=_lit(1),
        )
        result = evaluate(expr, Scope())
        assert isinstance(result, Ok)
        assert result.ok_value == "b"

    def test_act_falls_back_to_python(self):
        """ActExpr should fall back to Python evaluator with dispatch callback."""
        from axon.evaluator import KwargsDispatchFn
        from result import Ok as OkResult

        def mock_dispatch(name, kwargs):
            return OkResult(f"dispatched:{name}:{kwargs}")

        expr = ActExpr(line=0, tool_name="search", args=[("q", _lit("test"))])
        result = evaluate(expr, Scope(), kwargs_dispatch_fn=mock_dispatch)
        assert isinstance(result, Ok)
        assert "dispatched:search" in str(result.ok_value)

    def test_think_falls_back_to_python(self):
        """ThinkExpr should fall back to Python evaluator with trace callback."""
        traces = []

        def mock_trace(event, data):
            traces.append((event, data))

        expr = ThinkExpr(line=0, message=_lit("thinking..."))
        result = evaluate(expr, Scope(), trace_fn=mock_trace)
        assert isinstance(result, Ok)
        assert len(traces) == 1
        assert traces[0][0] == "think"
