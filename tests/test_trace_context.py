"""Tests for trace context and correlation ID propagation."""

from axon.trace_context import (
    TraceContext,
    child_span,
    get_current_trace,
    set_current_trace,
    trace_context,
)
from axon.trace_emitter import TraceEmitter


def test_trace_context_new_root() -> None:
    ctx = TraceContext.new()
    assert len(ctx.trace_id) == 32
    assert len(ctx.span_id) == 16
    assert ctx.parent_span_id is None


def test_trace_context_child() -> None:
    parent = TraceContext.new()
    child = TraceContext.new(parent=parent)
    assert child.trace_id == parent.trace_id
    assert child.span_id != parent.span_id
    assert child.parent_span_id == parent.span_id


def test_trace_context_to_dict() -> None:
    ctx = TraceContext(trace_id="abc", span_id="def", parent_span_id="ghi")
    assert ctx.to_dict() == {
        "trace_id": "abc",
        "span_id": "def",
        "parent_span_id": "ghi",
    }


def test_trace_context_uniqueness() -> None:
    ids = {TraceContext.new().trace_id for _ in range(100)}
    assert len(ids) == 100


def test_context_get_set() -> None:
    assert get_current_trace() is None
    ctx = TraceContext.new()
    set_current_trace(ctx)
    assert get_current_trace() == ctx
    set_current_trace(None)
    assert get_current_trace() is None


def test_trace_context_manager() -> None:
    assert get_current_trace() is None
    ctx = TraceContext.new()
    with trace_context(ctx) as active:
        assert active == ctx
        assert get_current_trace() == ctx
    assert get_current_trace() is None


def test_child_span_context_manager() -> None:
    root = TraceContext.new()
    with trace_context(root):
        assert get_current_trace() == root
        with child_span() as child:
            assert child.trace_id == root.trace_id
            assert child.parent_span_id == root.span_id
            assert get_current_trace() == child
        assert get_current_trace() == root
    assert get_current_trace() is None


def test_emitter_injects_trace_ids() -> None:
    emitter = TraceEmitter()
    ctx = TraceContext.new()
    with trace_context(ctx):
        emitter.agent_start(agent_name="test-bot", source_file="test.ax")
    event = emitter.events[0]
    assert event["event_type"] == "agent_start"
    assert event["trace_id"] == ctx.trace_id
    assert event["span_id"] == ctx.span_id
    assert "timestamp" in event


def test_emitter_no_context_when_none() -> None:
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="test-bot", source_file="test.ax")
    event = emitter.events[0]
    assert "trace_id" not in event
    assert "span_id" not in event


def test_emitter_nested_spans() -> None:
    emitter = TraceEmitter()
    root = TraceContext.new()
    with trace_context(root):
        emitter.agent_start(agent_name="parent", source_file="parent.ax")
        with child_span() as child:
            emitter.delegate_call(method_name="run", agent_name="child", arguments={})
    # First event: agent_start under root
    e1 = emitter.events[0]
    assert e1["trace_id"] == root.trace_id
    assert e1["span_id"] == root.span_id
    # Second event: delegate_call under child
    e2 = emitter.events[1]
    assert e2["trace_id"] == child.trace_id
    assert e2["span_id"] == child.span_id
    assert e2["parent_span_id"] == root.span_id


def test_emitter_method_start_and_model_call() -> None:
    emitter = TraceEmitter()
    ctx = TraceContext.new()
    with trace_context(ctx):
        emitter.method_start(method_name="run", arguments={"q": "hello"})
        emitter.model_call(method_name="run", model_reference="@mock/gpt", prompt_summary="hello")
    assert len(emitter.events) == 2
    for e in emitter.events:
        assert e["trace_id"] == ctx.trace_id
        assert e["span_id"] == ctx.span_id


def test_emitter_agent_end() -> None:
    emitter = TraceEmitter()
    ctx = TraceContext.new()
    with trace_context(ctx):
        emitter.agent_end(result_type="ok", result_summary="done")
    event = emitter.events[0]
    assert event["event_type"] == "agent_end"
    assert event["trace_id"] == ctx.trace_id
    assert "duration_ms" in event


def test_emitter_message_sent() -> None:
    emitter = TraceEmitter()
    ctx = TraceContext.new()
    with trace_context(ctx):
        emitter.message_sent(from_agent="a", to_agent="b", message_summary="hi")
    event = emitter.events[0]
    assert event["event_type"] == "message_sent"
    assert event["trace_id"] == ctx.trace_id


def test_emitter_tool_dispatch() -> None:
    emitter = TraceEmitter()
    ctx = TraceContext.new()
    with trace_context(ctx):
        emitter.tool_dispatch(method_name="run", tool_name="NoOp", arguments={"x": "hello"})
    event = emitter.events[0]
    assert event["event_type"] == "tool_dispatch"
    assert event["trace_id"] == ctx.trace_id
    assert event["tool_name"] == "NoOp"
