"""Tests for AXON expression evaluator."""

from result import Ok, Err

from axon.expression_ast import (
    ActExpr,
    AwaitExpr,
    BinaryOpExpr,
    BlockExpr,
    BroadcastExpr,
    CallExpr,
    ChanExpr,
    DiscoverExpr,
    ErrorExpr,
    GoExpr,
    IfExpr,
    IndexExpr,
    LetExpr,
    LiteralExpr,
    ListExpr,
    MapExpr,
    MatchArm,
    MatchExpr,
    MemberAccessExpr,
    NoneExpr,
    OkExpr,
    PoolExpr,
    ReceiveExpr,
    ReturnExpr,
    SelectArm,
    SelectExpr,
    SendExpr,
    SomeExpr,
    StringInterpolationExpr,
    UnaryOpExpr,
    VariableExpr,
    ParExpr,
    StructuredOutputExpr,
)
from axon.evaluator import Scope, evaluate
from axon.evaluator_errors import EvalError, EvalErrorKind


def _lit(value, line=1):
    return LiteralExpr(line=line, value=value)


def _var(name, line=1):
    return VariableExpr(line=line, name=name)


def test_evaluate_literal_int():
    scope = Scope()
    result = evaluate(_lit(42), scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 42


def test_evaluate_literal_float():
    scope = Scope()
    result = evaluate(_lit(3.14), scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 3.14


def test_evaluate_literal_string():
    scope = Scope()
    result = evaluate(_lit("hello"), scope)
    assert isinstance(result, Ok)
    assert result.ok_value == "hello"


def test_evaluate_literal_bool():
    scope = Scope()
    assert evaluate(_lit(True), scope).ok_value is True
    assert evaluate(_lit(False), scope).ok_value is False


def test_evaluate_literal_none():
    scope = Scope()
    result = evaluate(_lit(None), scope)
    assert isinstance(result, Ok)
    assert result.ok_value is None


def test_evaluate_variable_found():
    scope = Scope()
    scope.set("x", 99)
    result = evaluate(_var("x"), scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 99


def test_evaluate_variable_not_found():
    scope = Scope()
    result = evaluate(_var("missing"), scope)
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.UNKNOWN_VARIABLE


def test_evaluate_string_interpolation_literal():
    # "Hello, World!" parsed as single LiteralExpr inside StringInterpolationExpr
    expr = StringInterpolationExpr(
        line=1,
        parts=[LiteralExpr(line=1, value="Hello, World!")],
    )
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, World!"


def test_evaluate_string_interpolation_variable():
    # "Hello, {name}!"
    expr = StringInterpolationExpr(
        line=1,
        parts=[
            LiteralExpr(line=1, value="Hello, "),
            VariableExpr(line=1, name="name"),
            LiteralExpr(line=1, value="!"),
        ],
    )
    scope = Scope()
    scope.set("name", "Alice")
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, Alice!"


def test_evaluate_binary_addition():
    expr = BinaryOpExpr(line=1, op="+", left=_lit(1), right=_lit(2))
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 3


def test_evaluate_binary_subtraction():
    expr = BinaryOpExpr(line=1, op="-", left=_lit(5), right=_lit(3))
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 2


def test_evaluate_binary_multiplication():
    expr = BinaryOpExpr(line=1, op="*", left=_lit(4), right=_lit(3))
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 12


def test_evaluate_binary_division():
    expr = BinaryOpExpr(line=1, op="/", left=_lit(10), right=_lit(2))
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 5.0


def test_evaluate_binary_division_by_zero():
    expr = BinaryOpExpr(line=1, op="/", left=_lit(10), right=_lit(0))
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.DIVISION_BY_ZERO


def test_evaluate_binary_equality():
    expr = BinaryOpExpr(line=1, op="==", left=_lit(1), right=_lit(1))
    assert evaluate(expr, Scope()).ok_value is True

    expr = BinaryOpExpr(line=1, op="==", left=_lit(1), right=_lit(2))
    assert evaluate(expr, Scope()).ok_value is False


def test_evaluate_binary_inequality():
    expr = BinaryOpExpr(line=1, op="!=", left=_lit(1), right=_lit(2))
    assert evaluate(expr, Scope()).ok_value is True


def test_evaluate_binary_comparison():
    expr = BinaryOpExpr(line=1, op="<", left=_lit(1), right=_lit(2))
    assert evaluate(expr, Scope()).ok_value is True

    expr = BinaryOpExpr(line=1, op=">", left=_lit(3), right=_lit(2))
    assert evaluate(expr, Scope()).ok_value is True

    expr = BinaryOpExpr(line=1, op="<=", left=_lit(2), right=_lit(2))
    assert evaluate(expr, Scope()).ok_value is True

    expr = BinaryOpExpr(line=1, op=">=", left=_lit(3), right=_lit(2))
    assert evaluate(expr, Scope()).ok_value is True


def test_evaluate_binary_logical_and():
    expr = BinaryOpExpr(line=1, op="&&", left=_lit(True), right=_lit(False))
    assert evaluate(expr, Scope()).ok_value is False

    expr = BinaryOpExpr(line=1, op="&&", left=_lit(True), right=_lit(True))
    assert evaluate(expr, Scope()).ok_value is True


def test_evaluate_binary_logical_or():
    expr = BinaryOpExpr(line=1, op="||", left=_lit(False), right=_lit(True))
    assert evaluate(expr, Scope()).ok_value is True

    expr = BinaryOpExpr(line=1, op="||", left=_lit(False), right=_lit(False))
    assert evaluate(expr, Scope()).ok_value is False


def test_evaluate_unary_negation():
    expr = UnaryOpExpr(line=1, op="-", operand=_lit(5))
    assert evaluate(expr, Scope()).ok_value == -5


def test_evaluate_unary_not():
    expr = UnaryOpExpr(line=1, op="!", operand=_lit(True))
    assert evaluate(expr, Scope()).ok_value is False

    expr = UnaryOpExpr(line=1, op="!", operand=_lit(False))
    assert evaluate(expr, Scope()).ok_value is True


def test_evaluate_call_with_dispatch():
    """CallExpr dispatches through a provided function."""
    expr = CallExpr(
        line=1,
        callee=VariableExpr(line=1, name="add"),
        args=[_lit(1), _lit(2)],
    )

    def mock_dispatch(name, args):
        if name == "add":
            return Ok(sum(args))
        return Err(EvalError(EvalErrorKind.TOOL_NOT_FOUND, f"Unknown: {name}"))

    scope = Scope()
    result = evaluate(expr, scope, dispatch_fn=mock_dispatch)
    assert isinstance(result, Ok)
    assert result.ok_value == 3


def test_evaluate_call_no_dispatch():
    """CallExpr without dispatch_fn returns NotImplemented."""
    expr = CallExpr(
        line=1,
        callee=VariableExpr(line=1, name="foo"),
        args=[_lit(1)],
    )
    scope = Scope()
    result = evaluate(expr, scope)
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.NOT_IMPLEMENTED


def test_evaluate_call_arg_error():
    """Errors in argument evaluation propagate."""
    expr = CallExpr(
        line=1,
        callee=VariableExpr(line=1, name="add"),
        args=[_var("missing")],
    )

    def mock_dispatch(name, args):
        return Ok(0)

    scope = Scope()
    result = evaluate(expr, scope, dispatch_fn=mock_dispatch)
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.UNKNOWN_VARIABLE


def test_evaluate_block_empty():
    expr = BlockExpr(line=1, statements=[])
    assert evaluate(expr, Scope()).ok_value is None


def test_evaluate_block_single():
    expr = BlockExpr(line=1, statements=[_lit(42)])
    assert evaluate(expr, Scope()).ok_value == 42


def test_evaluate_block_multiple():
    expr = BlockExpr(
        line=1,
        statements=[_lit(1), _lit(2), _lit(3)],
    )
    assert evaluate(expr, Scope()).ok_value == 3


def test_evaluate_ok_constructor():
    expr = OkExpr(line=1, value=_lit(42))
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == {"ok": 42}


def test_evaluate_err_constructor():
    expr = ErrorExpr(line=1, value=_lit("oops"))
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == {"err": "oops"}


def test_evaluate_some_constructor():
    expr = SomeExpr(line=1, value=_lit(42))
    assert evaluate(expr, Scope()).ok_value == 42


def test_evaluate_none_literal():
    expr = NoneExpr(line=1)
    assert evaluate(expr, Scope()).ok_value is None


def test_evaluate_list_literal():
    expr = ListExpr(line=1, elements=[_lit(1), _lit(2), _lit(3)])
    assert evaluate(expr, Scope()).ok_value == [1, 2, 3]


def test_evaluate_map_literal():
    expr = MapExpr(
        line=1,
        pairs=[(_lit("a"), _lit(1)), (_lit("b"), _lit(2))],
    )
    assert evaluate(expr, Scope()).ok_value == {"a": 1, "b": 2}


def test_evaluate_member_access():
    class Point:
        x = 10
        y = 20

    expr = MemberAccessExpr(
        line=1,
        object=LiteralExpr(line=1, value=Point()),
        member="x",
    )
    assert evaluate(expr, Scope()).ok_value == 10


def test_evaluate_member_access_none():
    expr = MemberAccessExpr(
        line=1,
        object=LiteralExpr(line=1, value=None),
        member="x",
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.INVALID_OPERATION


def test_evaluate_index_list():
    expr = IndexExpr(
        line=1,
        object=LiteralExpr(line=1, value=[10, 20, 30]),
        index=LiteralExpr(line=1, value=1),
    )
    assert evaluate(expr, Scope()).ok_value == 20


def test_evaluate_index_dict():
    expr = IndexExpr(
        line=1,
        object=LiteralExpr(line=1, value={"a": 1, "b": 2}),
        index=LiteralExpr(line=1, value="a"),
    )
    assert evaluate(expr, Scope()).ok_value == 1


def test_evaluate_index_out_of_bounds():
    expr = IndexExpr(
        line=1,
        object=LiteralExpr(line=1, value=[10]),
        index=LiteralExpr(line=1, value=5),
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.INVALID_INDEX


def test_evaluate_let_binding():
    expr = LetExpr(
        line=1,
        name="x",
        value=_lit(10),
        body=VariableExpr(line=1, name="x"),
    )
    assert evaluate(expr, Scope()).ok_value == 10


def test_evaluate_let_nested():
    expr = LetExpr(
        line=1,
        name="x",
        value=_lit(1),
        body=LetExpr(
            line=1,
            name="y",
            value=_lit(2),
            body=BinaryOpExpr(
                line=1,
                op="+",
                left=VariableExpr(line=1, name="x"),
                right=VariableExpr(line=1, name="y"),
            ),
        ),
    )
    assert evaluate(expr, Scope()).ok_value == 3


def test_evaluate_return_expression():
    expr = ReturnExpr(line=1, value=_lit(42), is_ok=True)
    assert evaluate(expr, Scope()).ok_value == 42


def test_evaluate_if_true():
    expr = IfExpr(
        line=1,
        condition=_lit(True),
        then_branch=_lit("yes"),
        else_branch=_lit("no"),
    )
    assert evaluate(expr, Scope()).ok_value == "yes"


def test_evaluate_if_false():
    expr = IfExpr(
        line=1,
        condition=_lit(False),
        then_branch=_lit("yes"),
        else_branch=_lit("no"),
    )
    assert evaluate(expr, Scope()).ok_value == "no"


def test_evaluate_if_no_else():
    expr = IfExpr(
        line=1,
        condition=_lit(False),
        then_branch=_lit("yes"),
        else_branch=None,
    )
    assert evaluate(expr, Scope()).ok_value is None


def test_evaluate_match_no_arm_matches():
    expr = MatchExpr(line=1, value=_lit(1), arms=[MatchArm(pattern=_lit(2), body=_lit("two"))])
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.INVALID_OPERATION


def test_evaluate_scope_child_does_not_leak():
    scope = Scope()
    scope.set("x", 1)
    child = scope.child()
    child.set("x", 99)
    # Parent should still have original value
    assert scope.get("x") == 1
    # Child should see its own value
    assert child.get("x") == 99


def test_evaluate_scope_parent_lookup():
    scope = Scope()
    scope.set("x", 42)
    child = scope.child()
    # Child can read parent bindings
    assert child.get("x") == 42


def test_evaluate_go_and_await():
    # go spawn returns a Future; await unwraps it
    scope = Scope()
    scope.set("x", 21)
    go_expr = GoExpr(line=1, call=BinaryOpExpr(line=1, op="+", left=_var("x"), right=_lit(21)))
    fut_res = evaluate(go_expr, scope)
    assert isinstance(fut_res, Ok)
    fut = fut_res.ok_value
    from concurrent.futures import Future
    assert isinstance(fut, Future)

    await_expr = AwaitExpr(line=1, future=_lit(fut))
    result = evaluate(await_expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == 42


def test_evaluate_chan_unbounded():
    expr = ChanExpr(line=1, capacity=None)
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    import queue
    assert isinstance(result.ok_value, queue.Queue)
    assert result.ok_value.maxsize == 0


def test_evaluate_chan_bounded():
    expr = ChanExpr(line=1, capacity=_lit(5))
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    import queue
    assert isinstance(result.ok_value, queue.Queue)
    assert result.ok_value.maxsize == 5


def test_evaluate_select_with_data():
    import queue
    ch = queue.Queue()
    ch.put("hello")
    scope = Scope()
    scope.set("ch", ch)
    expr = SelectExpr(
        line=1,
        arms=[
            SelectArm(channel=_var("ch"), var_name="msg", body=_var("msg"), is_default=False),
        ],
    )
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == "hello"


def test_evaluate_select_default():
    import queue
    ch = queue.Queue()
    scope = Scope()
    scope.set("ch", ch)
    expr = SelectExpr(
        line=1,
        arms=[
            SelectArm(channel=_var("ch"), var_name="msg", body=_var("msg"), is_default=False),
            SelectArm(channel=_lit(None), var_name="", body=_lit("none"), is_default=True),
        ],
    )
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == "none"


def test_evaluate_select_no_default_no_data():
    import queue
    ch = queue.Queue()
    scope = Scope()
    scope.set("ch", ch)
    expr = SelectExpr(
        line=1,
        arms=[
            SelectArm(channel=_var("ch"), var_name="msg", body=_var("msg"), is_default=False),
        ],
    )
    result = evaluate(expr, scope)
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.INVALID_OPERATION


def test_evaluate_pool():
    expr = PoolExpr(line=1, size=_lit(4), target=_lit("Agent"))
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    from axon.worker_pool import WorkerPool
    pool = result.ok_value
    assert isinstance(pool, WorkerPool)
    assert pool.size == 4
    assert pool.target == "Agent"


def test_evaluate_pool_invalid_size():
    expr = PoolExpr(line=1, size=_lit("four"), target=_lit("Agent"))
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.TYPE_MISMATCH


def test_evaluate_match_guard():
    expr = MatchExpr(
        line=1,
        value=_lit(5),
        arms=[
            MatchArm(pattern=_var("x"), guard=BinaryOpExpr(line=1, op=">", left=_var("x"), right=_lit(10)), body=_lit("big")),
            MatchArm(pattern=_var("x"), guard=None, body=_lit("small")),
        ],
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == "small"


def test_evaluate_match_guard_passes():
    expr = MatchExpr(
        line=1,
        value=_lit(15),
        arms=[
            MatchArm(pattern=_var("x"), guard=BinaryOpExpr(line=1, op=">", left=_var("x"), right=_lit(10)), body=_lit("big")),
            MatchArm(pattern=_var("x"), guard=None, body=_lit("small")),
        ],
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == "big"


def test_evaluate_match_exhaustive_with_wildcard():
    expr = MatchExpr(
        line=1,
        value=_lit(42),
        arms=[
            MatchArm(pattern=_lit(1), body=_lit("one")),
            MatchArm(pattern=VariableExpr(line=1, name="_"), body=_lit("other")),
        ],
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == "other"


def test_evaluate_match_non_exhaustive():
    expr = MatchExpr(
        line=1,
        value=_lit(42),
        arms=[
            MatchArm(pattern=_lit(1), body=_lit("one")),
        ],
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Err)
    assert result.err_value.kind == EvalErrorKind.INVALID_OPERATION


def test_evaluate_match_binding():
    expr = MatchExpr(
        line=1,
        value=_lit(99),
        arms=[
            MatchArm(pattern=_var("x"), body=_var("x")),
        ],
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == 99


def test_evaluate_match_list_destructure():
    expr = MatchExpr(
        line=1,
        value=ListExpr(line=1, elements=[_lit(1), _lit(2), _lit(3)]),
        arms=[
            MatchArm(
                pattern=ListExpr(line=1, elements=[_var("a"), _var("b"), _var("c")]),
                body=ListExpr(line=1, elements=[_var("a"), _var("b"), _var("c")]),
            ),
        ],
    )
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == [1, 2, 3]


def test_evaluate_send_and_receive():
    from axon.message_bus import MessageBus
    bus = MessageBus()
    bus.set_current_agent("agent2")
    scope = Scope()
    scope.set("__message_bus__", bus)

    send_expr = SendExpr(line=1, recipient=_lit("agent2"), message=_lit("hello"))
    send_res = evaluate(send_expr, scope)
    assert isinstance(send_res, Ok)

    receive_expr = ReceiveExpr(line=1, timeout_ms=_lit(100))
    receive_res = evaluate(receive_expr, scope)
    assert isinstance(receive_res, Ok)
    assert receive_res.ok_value == "hello"


def test_evaluate_broadcast():
    from axon.message_bus import MessageBus
    bus = MessageBus()
    bus.set_current_agent("agent1")
    scope = Scope()
    scope.set("__message_bus__", bus)

    expr = BroadcastExpr(line=1, channel=_lit("alerts"), message=_lit("fire"))
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)


def test_evaluate_discover():
    from axon.service_registry import AgentService, ServiceRegistry
    registry = ServiceRegistry()
    registry.register(AgentService(name="WorkerA", host="localhost", port=8080))
    registry.register(AgentService(name="WorkerB", host="localhost", port=8081))
    scope = Scope()
    scope.set("__service_registry__", registry)

    expr = DiscoverExpr(line=1, pattern=_lit("*"))
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert "WorkerA" in result.ok_value
    assert "WorkerB" in result.ok_value


def test_par_basic():
    """par { 1 + 2, 3 + 4 } => [3, 7]"""
    expr = ParExpr(line=1, expressions=[
        BinaryOpExpr(line=1, op="+", left=_lit(1), right=_lit(2)),
        BinaryOpExpr(line=1, op="+", left=_lit(3), right=_lit(4)),
    ])
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == [3, 7]


def test_par_empty():
    """par { } => []"""
    expr = ParExpr(line=1, expressions=[])
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == []


def test_par_single():
    """par { 42 } => [42]"""
    expr = ParExpr(line=1, expressions=[_lit(42)])
    result = evaluate(expr, Scope())
    assert isinstance(result, Ok)
    assert result.ok_value == [42]


def test_par_with_variables():
    """par { x * 2, x + 1 } with x=10 => [20, 11]"""
    scope = Scope()
    scope.set("x", 10)
    expr = ParExpr(line=1, expressions=[
        BinaryOpExpr(line=1, op="*", left=_var("x"), right=_lit(2)),
        BinaryOpExpr(line=1, op="+", left=_var("x"), right=_lit(1)),
    ])
    result = evaluate(expr, scope)
    assert isinstance(result, Ok)
    assert result.ok_value == [20, 11]


def test_par_with_act():
    """par { act Foo(x: 1), act Bar(y: 2) } dispatches both concurrently"""
    call_log = []

    def kw_dispatch(name: str, kwargs: dict):
        call_log.append((name, kwargs))
        return Ok(f"{name}_result")

    expr = ParExpr(line=1, expressions=[
        ActExpr(line=1, tool_name="Foo", args=[("x", _lit(1))]),
        ActExpr(line=1, tool_name="Bar", args=[("y", _lit(2))]),
    ])
    result = evaluate(expr, Scope(), kwargs_dispatch_fn=kw_dispatch)
    assert isinstance(result, Ok)
    assert len(result.ok_value) == 2
    # Both tools were dispatched
    names = sorted(c[0] for c in call_log)
    assert names == ["Bar", "Foo"]


def test_think_as_with_structured_fn():
    """think_as(Str, 'prompt') calls structured_fn and returns parsed JSON."""
    def structured_fn(prompt: str, type_str: str):
        return Ok('"hello world"')

    scope = Scope()
    scope.set("__structured_call_fn__", structured_fn)

    expr = StructuredOutputExpr(line=1, type_str="Str", prompt=_lit("test prompt"))
    result = evaluate(expr, scope, model_call_fn=lambda p: Ok("fallback"))
    assert isinstance(result, Ok)
    assert result.ok_value == "hello world"


def test_think_as_fallback_to_model_call():
    """think_as without structured_fn falls back to model_call_fn and parses JSON."""
    def model_call(prompt: str):
        return Ok('{"name": "Alice", "age": 30}')

    scope = Scope()
    expr = StructuredOutputExpr(line=1, type_str="Any", prompt=_lit("test"))
    result = evaluate(expr, scope, model_call_fn=model_call)
    assert isinstance(result, Ok)
    assert isinstance(result.ok_value, dict)
    assert result.ok_value["name"] == "Alice"


def test_think_as_type_validation_error():
    """think_as validates response against AXON type and returns Err on mismatch."""
    def structured_fn(prompt: str, type_str: str):
        return Ok('"not an integer"')

    scope = Scope()
    scope.set("__structured_call_fn__", structured_fn)

    expr = StructuredOutputExpr(line=1, type_str="Int", prompt=_lit("test"))
    result = evaluate(expr, scope, model_call_fn=lambda p: Ok("0"))
    assert isinstance(result, Err)
    assert "validation" in result.err_value.message.lower()
