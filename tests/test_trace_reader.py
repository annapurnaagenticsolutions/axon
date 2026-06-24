import json

import pytest

from axon.trace import ActEvent, ObserveEvent, StoreEvent, ThinkEvent, TraceFormatError, TraceLog
from axon.trace_reader import (
    filter_trace_log,
    format_trace_summary,
    read_trace_file,
    summarize_trace_log,
    trace_report_to_json,
)


def _sample_log() -> TraceLog:
    return TraceLog(
        [
            ThinkEvent("Plan", agent="Bot", ts=1),
            ActEvent("Search", {"q": "axon"}, agent="Bot", ts=2),
            ObserveEvent("results", count=2, agent="Bot", ts=3),
            StoreEvent("working.results", "saved", agent="Other", ts=4),
        ]
    )


def test_summarize_trace_log_counts_types_agents_and_time_bounds():
    summary = summarize_trace_log(_sample_log())

    assert summary.total_events == 4
    assert summary.counts_by_type == {"act": 1, "observe": 1, "store": 1, "think": 1}
    assert summary.counts_by_agent == {"Bot": 3, "Other": 1}
    assert summary.first_ts == 1
    assert summary.last_ts == 4


def test_filter_trace_log_by_type_and_agent():
    filtered = filter_trace_log(_sample_log(), event_type="act", agent="Bot")

    assert len(filtered.events) == 1
    assert filtered.events[0].t == "act"
    assert filtered.events[0].agent == "Bot"


def test_format_trace_summary_can_include_events():
    text = format_trace_summary(_sample_log(), source="trace.jsonl", include_events=True)

    assert "AEL trace log: trace.jsonl" in text
    assert "events: 4" in text
    assert "by type: act=1, observe=1, store=1, think=1" in text
    assert "1. think [Bot]: Plan" in text
    assert "2. act [Bot]: Search(q='axon')" in text


def test_trace_report_to_json_contains_summary_and_events():
    payload = json.loads(trace_report_to_json(_sample_log(), source="trace.jsonl"))

    assert payload["source"] == "trace.jsonl"
    assert payload["summary"]["total_events"] == 4
    assert payload["events"][1]["tool"] == "Search"


def test_read_trace_file_round_trip(tmp_path):
    path = tmp_path / "trace.jsonl"
    _sample_log().write(path)

    loaded = read_trace_file(path)

    assert loaded.events == _sample_log().events


def test_read_trace_file_reports_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="trace file not found"):
        read_trace_file(tmp_path / "missing.jsonl")


def test_read_trace_file_propagates_trace_format_error(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"t":"think","content":"ok"}\nnot-json\n', encoding="utf-8")

    with pytest.raises(TraceFormatError, match="line 2"):
        read_trace_file(path)
