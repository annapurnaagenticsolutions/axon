"""Tests for the AXON Profiler."""

from __future__ import annotations

from axon.profiler import Profiler, profile_trace
from axon.trace import ActEvent, ThinkEvent, TraceLog


def test_profiler_basic() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.5),
            ThinkEvent(content="done", agent="Bot", ts=1.0),
        ]
    )
    report = Profiler(log).profile()
    assert report.total_events == 3
    assert report.overall_ms == 1000.0
    assert "Bot" in report.agents
    bot = report.agents["Bot"]
    assert bot.event_count == 3
    assert bot.act_calls == 1


def test_profiler_multiple_agents() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="a", agent="Agent1", ts=0.0),
            ThinkEvent(content="b", agent="Agent2", ts=0.2),
            ActEvent(tool="X", args={}, agent="Agent1", ts=0.5),
            ThinkEvent(content="c", agent="Agent2", ts=1.0),
        ]
    )
    report = Profiler(log).profile()
    assert len(report.agents) == 2
    assert report.agents["Agent1"].event_count == 2
    assert report.agents["Agent2"].event_count == 2


def test_profiler_empty_trace() -> None:
    report = Profiler(TraceLog(events=[])).profile()
    assert report.total_events == 0
    assert report.overall_ms == 0.0


def test_profiler_from_file(tmp_path) -> None:
    from pathlib import Path
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=1.0),
        ]
    )
    path = tmp_path / "trace.jsonl"
    path.write_text(log.to_jsonl(), encoding="utf-8")
    report = profile_trace(path)
    assert report.total_events == 2
    assert report.overall_ms == 1000.0
