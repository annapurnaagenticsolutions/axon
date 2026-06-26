"""Tests for the AXON Profiler."""

from __future__ import annotations

import json

from axon.profiler import (
    Hotspot,
    ProfileReport,
    Profiler,
    ThinkProfile,
    ToolProfile,
    profile_trace,
)
from axon.trace import ActEvent, StoreEvent, ThinkEvent, TraceLog


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
    assert bot.think_count == 2


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


# ── Per-tool latency tests ──────────────────────────────────────────────────

def test_profiler_tool_profile() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.1),
            ThinkEvent(content="mid", agent="Bot", ts=0.3),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.4),
            ThinkEvent(content="done", agent="Bot", ts=0.6),
        ]
    )
    report = Profiler(log).profile()
    assert "Search" in report.tools
    tp = report.tools["Search"]
    assert tp.call_count == 2
    assert tp.total_ms > 0
    assert tp.avg_ms > 0
    assert tp.p50_ms > 0
    assert tp.p95_ms > 0
    assert tp.p99_ms > 0


def test_profiler_multiple_tools() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.1),
            ActEvent(tool="Fetch", args={}, agent="Bot", ts=0.3),
            ThinkEvent(content="done", agent="Bot", ts=0.5),
        ]
    )
    report = Profiler(log).profile()
    assert len(report.tools) == 2
    assert "Search" in report.tools
    assert "Fetch" in report.tools


def test_profiler_tool_percentiles() -> None:
    events = [ThinkEvent(content="start", agent="Bot", ts=0.0)]
    for i in range(1, 11):
        events.append(ActEvent(tool="SlowTool", args={}, agent="Bot", ts=float(i) * 0.1))
    events.append(ThinkEvent(content="done", agent="Bot", ts=1.5))
    log = TraceLog(events=events)
    report = Profiler(log).profile()
    tp = report.tools["SlowTool"]
    assert tp.call_count == 10
    assert tp.p50_ms > 0
    assert tp.p95_ms >= tp.p50_ms
    assert tp.p99_ms >= tp.p95_ms


# ── Think timing tests ──────────────────────────────────────────────────────

def test_profiler_think_timing() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="think1", agent="Bot", ts=0.0, tokens=100),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.5),
            ThinkEvent(content="think2", agent="Bot", ts=0.8, tokens=200),
        ]
    )
    report = Profiler(log).profile()
    assert report.think.count == 2
    assert report.think.total_ms > 0
    assert report.think.avg_ms > 0
    assert report.think.total_tokens == 300
    assert report.think.tokens_per_sec > 0


def test_profiler_think_percentiles() -> None:
    events = []
    for i in range(5):
        events.append(ThinkEvent(content=f"t{i}", agent="Bot", ts=float(i) * 0.1, tokens=50))
    events.append(ThinkEvent(content="done", agent="Bot", ts=1.0))
    log = TraceLog(events=events)
    report = Profiler(log).profile()
    assert report.think.count == 6
    assert report.think.p50_ms > 0
    assert report.think.p95_ms >= report.think.p50_ms


# ── Hotspot detection tests ────────────────────────────────────────────────

def test_profiler_hotspot_detection() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="SlowAPI", args={}, agent="Bot", ts=0.2),
            ThinkEvent(content="done", agent="Bot", ts=1.0),
        ]
    )
    report = Profiler(log, hotspot_threshold_ms=100.0).profile()
    assert len(report.hotspots) >= 1
    h = report.hotspots[0]
    assert h.latency_ms >= 100.0
    assert h.event_type in ("act", "think")
    assert h.agent == "Bot"


def test_profiler_hotspot_threshold() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Fast", args={}, agent="Bot", ts=0.01),
            ThinkEvent(content="done", agent="Bot", ts=0.02),
        ]
    )
    report = Profiler(log, hotspot_threshold_ms=100.0).profile()
    assert len(report.hotspots) == 0


def test_profiler_hotspot_max_limit() -> None:
    events = [ThinkEvent(content="start", agent="Bot", ts=0.0)]
    for i in range(1, 6):
        events.append(ActEvent(tool=f"Slow{i}", args={}, agent="Bot", ts=float(i) * 0.5))
    events.append(ThinkEvent(content="done", agent="Bot", ts=3.0))
    log = TraceLog(events=events)
    report = Profiler(log, hotspot_threshold_ms=100.0, max_hotspots=3).profile()
    assert len(report.hotspots) <= 3


def test_profiler_hotspot_sorted_by_latency() -> None:
    events = [ThinkEvent(content="start", agent="Bot", ts=0.0)]
    events.append(ActEvent(tool="A", args={}, agent="Bot", ts=0.5))
    events.append(ActEvent(tool="B", args={}, agent="Bot", ts=2.0))
    events.append(ThinkEvent(content="done", agent="Bot", ts=2.1))
    log = TraceLog(events=events)
    report = Profiler(log, hotspot_threshold_ms=100.0).profile()
    if len(report.hotspots) >= 2:
        assert report.hotspots[0].latency_ms >= report.hotspots[1].latency_ms


# ── CSV export tests ────────────────────────────────────────────────────────

def test_profiler_csv_export() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.5),
            ThinkEvent(content="done", agent="Bot", ts=1.0),
        ]
    )
    report = Profiler(log).profile()
    csv_output = report.to_csv()
    lines = csv_output.strip().splitlines()
    assert lines[0] == "index,event_type,agent,tool,latency_ms,tokens,description"
    assert len(lines) == 4  # header + 3 events


def test_profiler_tool_csv_export() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.5),
            ActEvent(tool="Fetch", args={}, agent="Bot", ts=0.8),
            ThinkEvent(content="done", agent="Bot", ts=1.0),
        ]
    )
    report = Profiler(log).profile()
    csv_output = report.to_tool_csv()
    lines = csv_output.strip().splitlines()
    assert lines[0] == "tool,call_count,total_ms,avg_ms,p50_ms,p95_ms,p99_ms"
    assert len(lines) == 3  # header + 2 tools


# ── JSON export test ────────────────────────────────────────────────────────

def test_profiler_json_export() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0, tokens=100),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.5),
            ThinkEvent(content="done", agent="Bot", ts=1.0),
        ]
    )
    report = Profiler(log).profile()
    data = report.to_dict()
    assert "overall_ms" in data
    assert "tools" in data
    assert "think" in data
    assert "hotspots" in data
    assert data["think"]["total_tokens"] == 100
    assert data["tools"]["Search"]["call_count"] == 1
    assert "p50_ms" in data["tools"]["Search"]
    assert "p95_ms" in data["tools"]["Search"]
    assert "p99_ms" in data["tools"]["Search"]


# ── Store event test ────────────────────────────────────────────────────────

def test_profiler_store_events() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            StoreEvent(key="result", value=42, agent="Bot", ts=0.2),
            ThinkEvent(content="done", agent="Bot", ts=0.4),
        ]
    )
    report = Profiler(log).profile()
    assert report.total_events == 3
    bot = report.agents["Bot"]
    assert bot.event_count == 3
