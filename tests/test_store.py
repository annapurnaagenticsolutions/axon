"""Tests for AXON store / memory mutation."""

from axon.expression_parser import parse_expression
from axon.expression_ast import StoreExpr, IndexExpr, MemberAccessExpr, VariableExpr, LiteralExpr
from axon.evaluator import Scope, evaluate
from axon.memory_store import MemoryStore
from result import Err


# -- Parser tests -------------------------------------------------

def test_parse_store_simple():
    expr = parse_expression('store memory.working["key"] = "value"')
    assert isinstance(expr, StoreExpr)
    assert isinstance(expr.target, IndexExpr)
    assert isinstance(expr.value, LiteralExpr)
    assert expr.value.value == "value"


def test_parse_store_with_variable_value():
    expr = parse_expression('store memory.working["last"] = x')
    assert isinstance(expr, StoreExpr)
    assert isinstance(expr.value, VariableExpr)


# -- Evaluator tests ----------------------------------------------

def test_evaluate_store_simple():
    store = MemoryStore()
    scope = Scope()
    expr = parse_expression('store memory.working["topic"] = "hello"')
    result = evaluate(expr, scope, memory_store=store)
    assert result.ok_value == "hello"
    assert store.get("working", "topic") == "hello"


def test_evaluate_store_with_variable():
    store = MemoryStore()
    scope = Scope()
    scope.set("msg", "world")
    expr = parse_expression('store memory.working["greeting"] = msg')
    result = evaluate(expr, scope, memory_store=store)
    assert result.ok_value == "world"
    assert store.get("working", "greeting") == "world"


def test_evaluate_store_no_memory_store():
    scope = Scope()
    expr = parse_expression('store memory.working["x"] = 1')
    result = evaluate(expr, scope)
    assert isinstance(result, Err)
    assert "No memory store" in result.err_value.message


def test_evaluate_store_invalid_target():
    store = MemoryStore()
    scope = Scope()
    # store foo = 1 — invalid target
    expr = parse_expression('store foo = 1')
    result = evaluate(expr, scope, memory_store=store)
    assert isinstance(result, Err)
    assert "Store target must be memory.section" in result.err_value.message


def test_evaluate_store_in_block():
    store = MemoryStore()
    scope = Scope()
    expr = parse_expression('store memory.working["a"] = 1; store memory.working["b"] = 2')
    result = evaluate(expr, scope, memory_store=store)
    assert result.ok_value == 2
    assert store.get("working", "a") == 1
    assert store.get("working", "b") == 2


def test_evaluate_store_in_if():
    store = MemoryStore()
    scope = Scope()
    scope.set("x", True)
    expr = parse_expression('if x { store memory.working["flag"] = "set" }')
    result = evaluate(expr, scope, memory_store=store)
    assert result.ok_value == "set"
    assert store.get("working", "flag") == "set"


def test_evaluate_store_in_for():
    store = MemoryStore()
    scope = Scope()
    # Use literal keys in loop body to avoid needing dispatch_fn for str()
    expr = parse_expression('for i in [1, 2] { store memory.working["k"] = i * 10 }')
    result = evaluate(expr, scope, memory_store=store)
    assert result.ok_value == 20
    assert store.get("working", "k") == 20  # last iteration wins


def test_memory_store_snapshot():
    store = MemoryStore()
    store.set("working", "a", 1)
    store.set("working", "b", 2)
    store.set("long_term", "c", 3)
    snap = store.snapshot()
    assert snap == {
        "working": {"a": 1, "b": 2},
        "long_term": {"c": 3},
    }


def test_memory_store_get_section():
    store = MemoryStore()
    store.set("working", "a", 1)
    store.set("working", "b", 2)
    assert store.get_section("working") == {"a": 1, "b": 2}
