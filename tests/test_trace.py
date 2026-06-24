import json

import pytest

from axon.trace import (
    ActEvent,
    ObserveEvent,
    StoreEvent,
    ThinkEvent,
    TraceFormatError,
    TraceLog,
    TraceRecorder,
    event_from_dict,
)


def test_think_event_to_dict_is_compact():
    event = ThinkEvent("Need recent data", agent="ResearchAgent", ts=123, tokens=4)

    assert event.to_dict() == {
        "t": "think",
        "content": "Need recent data",
        "agent": "ResearchAgent",
        "ts": 123,
        "tokens": 4,
    }
    assert json.loads(event.to_json())["t"] == "think"


def test_act_event_preserves_tool_and_args():
    event = ActEvent("WebSearch", {"query": "climate 2025", "max_results": 5}, agent="A", ts=1)

    assert event.to_dict()["tool"] == "WebSearch"
    assert event.to_dict()["args"] == {"query": "climate 2025", "max_results": 5}


def test_observe_event_supports_count_or_value():
    event = ObserveEvent("results", [{"title": "A"}], count=1, ts=2)

    assert event.to_dict()["t"] == "observe"
    assert event.to_dict()["name"] == "results"
    assert event.to_dict()["count"] == 1
    assert event.to_dict()["value"] == [{"title": "A"}]


def test_store_event_records_memory_key_and_value():
    event = StoreEvent("working.results", {"top": 1}, agent="A", ts=3)

    assert event.to_dict() == {
        "t": "store",
        "key": "working.results",
        "value": {"top": 1},
        "agent": "A",
        "ts": 3,
    }


def test_event_from_dict_round_trip_all_event_types():
    events = [
        ThinkEvent("Plan", agent="A", ts=1),
        ActEvent("Search", {"q": "x"}, agent="A", ts=2),
        ObserveEvent("results", count=3, agent="A", ts=3),
        StoreEvent("working.results", "saved", agent="A", ts=4),
    ]

    round_tripped = [event_from_dict(event.to_dict()) for event in events]

    assert round_tripped == events


def test_trace_log_jsonl_round_trip():
    log = TraceLog(
        [
            ThinkEvent("Plan", agent="A", ts=1),
            ActEvent("Search", {"q": "x"}, agent="A", ts=2),
        ]
    )

    jsonl = log.to_jsonl()
    restored = TraceLog.from_jsonl(jsonl)

    assert restored.events == log.events
    assert jsonl.endswith("\n")


def test_trace_log_write_and_read(tmp_path):
    path = tmp_path / "traces" / "agent.jsonl"
    log = TraceLog([StoreEvent("memory.key", "value", ts=5)])

    written = log.write(path)
    restored = TraceLog.read(written)

    assert written == path
    assert restored.events == log.events


def test_trace_log_filters_by_type_and_agent():
    log = TraceLog(
        [
            ThinkEvent("A thought", agent="A", ts=1),
            ActEvent("Tool", {}, agent="B", ts=2),
            ThinkEvent("Another", agent="B", ts=3),
        ]
    )

    assert len(log.by_type("think")) == 2
    assert len(log.by_agent("B")) == 2


def test_trace_recorder_injects_agent_and_clock():
    ticks = iter([100, 101, 102, 103])
    recorder = TraceRecorder(agent="ResearchAgent", clock=lambda: next(ticks))

    recorder.think("Need data", tokens=2)
    recorder.act("WebSearch", {"query": "axon"})
    recorder.observe("results", count=5)
    recorder.store("working.results", "ok")

    assert [event.t for event in recorder.events] == ["think", "act", "observe", "store"]
    assert [event.ts for event in recorder.events] == [100, 101, 102, 103]
    assert all(event.agent == "ResearchAgent" for event in recorder.events)


def test_non_json_safe_values_are_represented_readably():
    class NotJson:
        def __repr__(self):
            return "<NotJson>"

    event = ObserveEvent("obj", NotJson())

    assert event.to_dict()["value"] == "<NotJson>"


def test_unknown_trace_event_type_raises():
    with pytest.raises(TraceFormatError, match="unknown trace event type"):
        event_from_dict({"t": "learn", "content": "future"})


def test_invalid_trace_jsonl_reports_line_number():
    with pytest.raises(TraceFormatError, match="line 2"):
        TraceLog.from_jsonl('{"t":"think","content":"ok"}\nnot-json\n')


def test_invalid_field_shape_reports_field_name():
    with pytest.raises(TraceFormatError, match="tokens"):
        event_from_dict({"t": "think", "content": "bad", "tokens": "many"})
