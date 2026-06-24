"""Tests for AXON multi-agent orchestration (delegate keyword)."""

from axon.expression_parser import parse_expression
from axon.expression_ast import DelegateExpr, LiteralExpr, VariableExpr
from axon.evaluator import Scope, evaluate
from result import Ok, Err


# -- Parser tests -------------------------------------------------

def test_parse_delegate_literal_args():
    expr = parse_expression('delegate SubAgent(query: "hello")')
    assert isinstance(expr, DelegateExpr)
    assert expr.agent_name == "SubAgent"
    assert len(expr.args) == 1
    key, val = expr.args[0]
    assert key == "query"
    assert isinstance(val, LiteralExpr)
    assert val.value == "hello"


def test_parse_delegate_variable_args():
    expr = parse_expression('delegate SubAgent(query: msg, count: n)')
    assert isinstance(expr, DelegateExpr)
    assert expr.agent_name == "SubAgent"
    assert len(expr.args) == 2
    assert expr.args[0][0] == "query"
    assert expr.args[1][0] == "count"


def test_parse_delegate_with_try():
    from axon.expression_ast import TryExpr
    expr = parse_expression('delegate SubAgent(query: "test")?')
    assert isinstance(expr, TryExpr)
    assert isinstance(expr.operand, DelegateExpr)


# -- Evaluator tests ----------------------------------------------

def test_evaluate_delegate_with_mock():
    expr = parse_expression('delegate SubAgent(query: "hello")')
    scope = Scope()

    def mock_delegate(agent_name: str, kwargs: dict) -> Result[Any, any]:
        assert agent_name == "SubAgent"
        assert kwargs == {"query": "hello"}
        return Ok(f"Result from {agent_name}")

    result = evaluate(expr, scope, delegate_fn=mock_delegate)
    assert result.ok_value == "Result from SubAgent"


def test_evaluate_delegate_no_fn():
    expr = parse_expression('delegate SubAgent(query: "test")')
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert "No delegate function" in result.err_value.message


def test_evaluate_delegate_with_try_ok():
    from axon.expression_ast import TryExpr
    expr = parse_expression('delegate SubAgent(query: "test")?')
    scope = Scope()

    def mock_delegate(agent_name: str, kwargs: dict) -> Result[Any, any]:
        return Ok({"ok": "success"})

    result = evaluate(expr, scope, delegate_fn=mock_delegate)
    assert result.ok_value == "success"


def test_evaluate_delegate_with_try_err():
    from axon.expression_ast import TryExpr
    expr = parse_expression('delegate SubAgent(query: "test")?')
    scope = Scope()

    def mock_delegate(agent_name: str, kwargs: dict) -> Result[Any, any]:
        return Ok({"err": "failed"})

    result = evaluate(expr, scope, delegate_fn=mock_delegate)
    assert isinstance(result, Err)
    assert "failed" in result.err_value.message


def test_evaluate_delegate_in_let():
    expr = parse_expression('let result = delegate SubAgent(query: "hi") in result')
    scope = Scope()

    def mock_delegate(agent_name: str, kwargs: dict) -> Result[Any, any]:
        return Ok("delegated")

    result = evaluate(expr, scope, delegate_fn=mock_delegate)
    assert result.ok_value == "delegated"


def test_evaluate_delegate_in_if():
    expr = parse_expression('if true { delegate SubAgent(query: "go") }')
    scope = Scope()

    def mock_delegate(agent_name: str, kwargs: dict) -> Result[Any, any]:
        return Ok("done")

    result = evaluate(expr, scope, delegate_fn=mock_delegate)
    assert result.ok_value == "done"


def test_evaluate_delegate_evaluates_args():
    expr = parse_expression('delegate SubAgent(query: x)')
    scope = Scope()
    scope.set("x", "world")

    captured = {}

    def mock_delegate(agent_name: str, kwargs: dict) -> Result[Any, any]:
        captured.update(kwargs)
        return Ok("ok")

    result = evaluate(expr, scope, delegate_fn=mock_delegate)
    assert captured == {"query": "world"}


# -- Named agent execution tests ----------------------------------

from pathlib import Path
from axon.cli import run_file


def test_named_agent_execution(tmp_path: Path):
    """Run a specific agent by name when multiple agents exist."""
    source = '''agent Alpha {
        model: @mock/gpt
        fn run() -> Str { "alpha" }
    }

    agent Beta {
        model: @mock/gpt
        fn run() -> Str { "beta" }
    }'''
    p = tmp_path / "multi.ax"
    p.write_text(source, encoding="utf-8")

    # Default: first agent (Alpha)
    code1, output1 = run_file(p)
    assert code1 == 0
    assert output1 == "alpha"

    # Named: Beta
    code2, output2 = run_file(p, agent_name="Beta")
    assert code2 == 0
    assert output2 == "beta"


def test_named_agent_missing(tmp_path: Path):
    """Error when named agent does not exist."""
    source = '''agent Alpha {
        model: @mock/gpt
        fn run() -> Str { "alpha" }
    }'''
    p = tmp_path / "multi.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, agent_name="Missing")
    assert code == 1
    assert "not found" in output.lower()


# -- Message bus tests --------------------------------------------

from axon.message_bus import MessageBus


def test_message_bus_send_receive():
    """Message bus supports basic send/receive."""
    bus = MessageBus()
    bus.set_current_agent("Worker")
    bus.send("Worker", "hello")
    result = bus.receive()
    assert result == "hello"


def test_message_bus_receive_empty():
    """Receive returns None when mailbox is empty."""
    bus = MessageBus()
    bus.set_current_agent("Worker")
    assert bus.receive() is None


def test_message_bus_multiple_recipients():
    """Messages are routed to correct recipients."""
    bus = MessageBus()
    bus.send("A", "msg-for-a")
    bus.send("B", "msg-for-b")

    bus.set_current_agent("A")
    assert bus.receive() == "msg-for-a"
    assert bus.receive() is None

    bus.set_current_agent("B")
    assert bus.receive() == "msg-for-b"


def test_message_bus_receive_blocking_timeout():
    """Blocking receive raises TimeoutError when no message arrives."""
    bus = MessageBus()
    bus.set_current_agent("Worker")
    try:
        bus.receive_blocking(timeout_ms=50)
        assert False, "Expected TimeoutError"
    except TimeoutError:
        pass


# -- End-to-end message passing tests -----------------------------

def test_agent_send_receive_e2e(tmp_path: Path):
    """An agent can send a message to itself and receive it."""
    source = '''agent SelfTalk {
        model: @mock/gpt
        fn run() -> Str {
            send("SelfTalk", "hello")
            let msg = receive_blocking()
            msg
        }
    }'''
    p = tmp_path / "messaging.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, agent_name="SelfTalk")
    assert code == 0
    assert output == "hello"


def test_message_trace_events(tmp_path: Path):
    """Message passing emits trace events."""
    source = '''agent Sender {
        model: @mock/gpt
        fn run() -> Str {
            send("Sender", "hi")
            receive_blocking()
            "done"
        }
    }'''
    p = tmp_path / "messaging.ax"
    p.write_text(source, encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"

    code, output = run_file(p, agent_name="Sender", trace_output=trace_path)
    assert code == 0

    import json
    events = [json.loads(line) for line in trace_path.read_text().strip().split("\n")]
    event_types = [e["event_type"] for e in events]

    assert "message_sent" in event_types
