"""Tests for AXON model.complete() expression parsing and evaluation."""

from axon.expression_parser import parse_expression
from axon.expression_ast import ModelCallExpr, LiteralExpr, VariableExpr
from axon.evaluator import Scope, evaluate
from result import Ok, Err


# -- Parser tests -------------------------------------------------

def test_parse_model_complete_literal():
    expr = parse_expression('model.complete("hello")')
    assert isinstance(expr, ModelCallExpr)
    assert isinstance(expr.prompt, LiteralExpr)
    assert expr.prompt.value == "hello"


def test_parse_model_complete_variable():
    expr = parse_expression('model.complete(prompt)')
    assert isinstance(expr, ModelCallExpr)
    assert isinstance(expr.prompt, VariableExpr)


def test_parse_model_complete_with_try():
    from axon.expression_ast import TryExpr
    expr = parse_expression('model.complete("test")?')
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, ModelCallExpr)


# -- Evaluator tests ----------------------------------------------

def test_evaluate_model_complete_with_mock():
    expr = parse_expression('model.complete("hello")')
    scope = Scope()

    def mock_model_call(prompt: str) -> Result[Any, any]:
        assert prompt == "hello"
        return Ok(f"Response to: {prompt}")

    result = evaluate(expr, scope, model_call_fn=mock_model_call)
    assert result.ok_value == "Response to: hello"


def test_evaluate_model_complete_with_variable():
    expr = parse_expression('model.complete(msg)')
    scope = Scope()
    scope.set("msg", "world")

    def mock_model_call(prompt: str) -> Result[Any, any]:
        return Ok(f"Got: {prompt}")

    result = evaluate(expr, scope, model_call_fn=mock_model_call)
    assert result.ok_value == "Got: world"


def test_evaluate_model_complete_no_fn():
    expr = parse_expression('model.complete("test")')
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert "No model call function" in result.err_value.message


def test_evaluate_model_complete_with_try_ok():
    from axon.expression_ast import TryExpr
    expr = parse_expression('model.complete("test")?')
    scope = Scope()

    def mock_model_call(prompt: str) -> Result[Any, any]:
        return Ok({"ok": "success"})

    result = evaluate(expr, scope, model_call_fn=mock_model_call)
    assert result.ok_value == "success"


def test_evaluate_model_complete_with_try_err():
    from axon.expression_ast import TryExpr
    expr = parse_expression('model.complete("test")?')
    scope = Scope()

    def mock_model_call(prompt: str) -> Result[Any, any]:
        return Ok({"err": "failed"})

    result = evaluate(expr, scope, model_call_fn=mock_model_call)
    assert isinstance(result, Err)
    assert "failed" in result.err_value.message


def test_evaluate_model_complete_in_let():
    expr = parse_expression('let result = model.complete("hi") in result')
    scope = Scope()

    def mock_model_call(prompt: str) -> Result[Any, any]:
        return Ok("AI says hi")

    result = evaluate(expr, scope, model_call_fn=mock_model_call)
    assert result.ok_value == "AI says hi"


def test_evaluate_model_complete_in_if():
    expr = parse_expression('if true { model.complete("go") }')
    scope = Scope()

    def mock_model_call(prompt: str) -> Result[Any, any]:
        return Ok("done")

    result = evaluate(expr, scope, model_call_fn=mock_model_call)
    assert result.ok_value == "done"
