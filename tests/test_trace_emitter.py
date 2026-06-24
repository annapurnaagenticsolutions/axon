"""Tests for AXON runtime trace emitter."""

import json

from axon.trace_emitter import TraceEmitter


def test_agent_start():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")

    assert len(emitter.events) == 1
    assert emitter.events[0]["event_type"] == "agent_start"
    assert emitter.events[0]["agent_name"] == "Bot"
    assert emitter.events[0]["source_file"] == "hello.ax"
    assert "timestamp" in emitter.events[0]


def test_method_start():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_start(method_name="run", arguments={"q": "World"})

    assert len(emitter.events) == 2
    assert emitter.events[1]["event_type"] == "method_start"
    assert emitter.events[1]["agent_name"] == "Bot"
    assert emitter.events[1]["method_name"] == "run"
    assert emitter.events[1]["arguments"]["q"] == "World"


def test_tool_dispatch():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.tool_dispatch(
        method_name="run",
        tool_name="Greet",
        arguments={"name": "World"},
    )

    assert emitter.events[1]["event_type"] == "tool_dispatch"
    assert emitter.events[1]["tool_name"] == "Greet"
    assert emitter.events[1]["method_name"] == "run"


def test_tool_return():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.tool_return(
        method_name="run",
        tool_name="Greet",
        result_type="ok",
        result_summary="Str",
    )

    assert emitter.events[1]["event_type"] == "tool_return"
    assert emitter.events[1]["result_type"] == "ok"
    assert emitter.events[1]["result_summary"] == "Str"


def test_method_return():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_return(
        method_name="run",
        result_type="ok",
        result_summary="Str",
    )

    assert emitter.events[1]["event_type"] == "method_return"
    assert emitter.events[1]["result_type"] == "ok"


def test_agent_end():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.agent_end(result_type="ok", result_summary="Str")

    assert emitter.events[1]["event_type"] == "agent_end"
    assert emitter.events[1]["agent_name"] == "Bot"
    assert "duration_ms" in emitter.events[1]
    assert isinstance(emitter.events[1]["duration_ms"], int)


def test_full_execution_flow():
    """Emit all 6 event types in correct order."""
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_start(method_name="run", arguments={"q": "World"})
    emitter.tool_dispatch(
        method_name="run",
        tool_name="Greet",
        arguments={"name": "World"},
    )
    emitter.tool_return(
        method_name="run",
        tool_name="Greet",
        result_type="ok",
        result_summary="Str",
    )
    emitter.method_return(
        method_name="run",
        result_type="ok",
        result_summary="Str",
    )
    emitter.agent_end(result_type="ok", result_summary="Str")

    assert len(emitter.events) == 6
    types = [e["event_type"] for e in emitter.events]
    assert types == [
        "agent_start",
        "method_start",
        "tool_dispatch",
        "tool_return",
        "method_return",
        "agent_end",
    ]


def test_to_jsonl():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    jsonl = emitter.to_jsonl()

    lines = jsonl.strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event_type"] == "agent_start"
    assert parsed["agent_name"] == "Bot"


def test_jsonl_multiple_events():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.agent_end()

    lines = emitter.to_jsonl().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "agent_start"
    assert json.loads(lines[1])["event_type"] == "agent_end"


def test_redaction_of_secret_keys():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_start(
        method_name="run",
        arguments={
            "query": "hello",
            "api_key": "sk-secret-123",
            "my_secret": "hidden",
            "auth_token": "bearer-xyz",
            "password": "hunter2",
        },
    )

    args = emitter.events[1]["arguments"]
    assert args["query"] == "hello"
    assert args["api_key"] == "[REDACTED]"
    assert args["my_secret"] == "[REDACTED]"
    assert args["auth_token"] == "[REDACTED]"
    assert args["password"] == "[REDACTED]"


def test_truncation_of_long_strings():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    long_text = "x" * 200
    emitter.method_start(method_name="run", arguments={"text": long_text})

    value = emitter.events[1]["arguments"]["text"]
    assert len(value) == 100
    assert value.endswith("...")


def test_collection_values_summary():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_start(
        method_name="run",
        arguments={
            "items": [1, 2, 3],
            "config": {"a": 1},
        },
    )

    assert emitter.events[1]["arguments"]["items"] == "<list[3]>"
    assert emitter.events[1]["arguments"]["config"] == "<dict[1]>"


def test_scalar_values_pass_through():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_start(
        method_name="run",
        arguments={
            "n": 42,
            "f": 3.14,
            "flag": True,
            "none": None,
        },
    )

    args = emitter.events[1]["arguments"]
    assert args["n"] == 42
    assert args["f"] == 3.14
    assert args["flag"] is True
    assert args["none"] is None


def test_agent_name_propagated_to_all_events():
    emitter = TraceEmitter()
    emitter.agent_start(agent_name="Bot", source_file="hello.ax")
    emitter.method_start(method_name="run", arguments={})
    emitter.tool_dispatch(method_name="run", tool_name="Greet", arguments={})
    emitter.tool_return(
        method_name="run",
        tool_name="Greet",
        result_type="ok",
        result_summary="Str",
    )
    emitter.method_return(
        method_name="run",
        result_type="ok",
        result_summary="Str",
    )
    emitter.agent_end()

    for event in emitter.events:
        if event["event_type"] != "agent_start":
            assert event["agent_name"] == "Bot"
