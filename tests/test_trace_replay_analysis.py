"""Tests for AXON trace replay analysis and regression detection."""

from __future__ import annotations

from axon.trace import ActEvent, StoreEvent, ThinkEvent, TraceLog
from axon.trace_replay import (
    TraceReplayer,
    compare_trace_files,
    compare_traces,
    replay_trace,
)


def _make_log() -> TraceLog:
    return TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.5),
            ThinkEvent(content="done", agent="Bot", ts=1.0),
        ]
    )


# ── Replay tests ────────────────────────────────────────────────────────────


def test_replay_basic() -> None:
    log = _make_log()
    result = TraceReplayer(log).replay()
    assert result.total_events == 3
    assert result.total_ms == 1000.0
    assert len(result.steps) == 3


def test_replay_steps_have_correct_types() -> None:
    log = _make_log()
    result = TraceReplayer(log).replay()
    assert result.steps[0].event_type == "think"
    assert result.steps[1].event_type == "act"
    assert result.steps[2].event_type == "think"


def test_replay_step_fields() -> None:
    log = _make_log()
    result = TraceReplayer(log).replay()
    step1 = result.steps[1]
    assert step1.index == 1
    assert step1.agent == "Bot"
    assert step1.tool == "Search"
    assert step1.latency_ms == 500.0
    assert step1.cumulative_ms == 500.0


def test_replay_cumulative_time() -> None:
    log = _make_log()
    result = TraceReplayer(log).replay()
    assert result.steps[0].cumulative_ms == 0.0
    assert result.steps[1].cumulative_ms == 500.0
    assert result.steps[2].cumulative_ms == 1000.0


def test_replay_empty_trace() -> None:
    result = TraceReplayer(TraceLog(events=[])).replay()
    assert result.total_events == 0
    assert result.total_ms == 0.0
    assert len(result.steps) == 0


def test_replay_multiple_agents() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="a", agent="Agent1", ts=0.0),
            ThinkEvent(content="b", agent="Agent2", ts=0.2),
            ActEvent(tool="X", args={}, agent="Agent1", ts=0.5),
            ThinkEvent(content="c", agent="Agent2", ts=1.0),
        ]
    )
    result = TraceReplayer(log).replay()
    assert len(result.steps) == 4
    assert result.steps[0].agent == "Agent1"
    assert result.steps[1].agent == "Agent2"


def test_replay_store_events() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            StoreEvent(key="result", value=42, agent="Bot", ts=0.3),
            ThinkEvent(content="done", agent="Bot", ts=0.5),
        ]
    )
    result = TraceReplayer(log).replay()
    assert result.steps[1].event_type == "store"
    assert "store" in result.steps[1].description


def test_replay_includes_profile_report() -> None:
    log = _make_log()
    result = TraceReplayer(log).replay()
    assert result.report is not None
    assert result.report.total_events == 3


def test_replay_from_file(tmp_path) -> None:
    log = _make_log()
    path = tmp_path / "trace.jsonl"
    path.write_text(log.to_jsonl(), encoding="utf-8")
    result = replay_trace(path)
    assert result.total_events == 3
    assert result.total_ms == 1000.0


def test_replay_to_dict() -> None:
    log = _make_log()
    result = TraceReplayer(log).replay()
    data = result.to_dict()
    assert data["total_events"] == 3
    assert data["total_ms"] == 1000.0
    assert len(data["steps"]) == 3
    assert "index" in data["steps"][0]
    assert "cumulative_ms" in data["steps"][0]


# ── Regression comparison tests ─────────────────────────────────────────────


def _make_baseline_log() -> TraceLog:
    return TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.1),
            ActEvent(tool="Fetch", args={}, agent="Bot", ts=0.3),
            ThinkEvent(content="done", agent="Bot", ts=0.4),
        ]
    )


def _make_candidate_log() -> TraceLog:
    return TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.3),
            ActEvent(tool="Fetch", args={}, agent="Bot", ts=0.5),
            ThinkEvent(content="done", agent="Bot", ts=0.6),
        ]
    )


def test_compare_traces_basic() -> None:
    baseline = _make_baseline_log()
    candidate = _make_candidate_log()
    report = compare_traces(baseline, candidate)
    assert report.baseline_events == 4
    assert report.candidate_events == 4
    assert report.baseline_total_ms > 0
    assert report.candidate_total_ms > 0


def test_compare_traces_overall_regression() -> None:
    baseline = _make_baseline_log()
    candidate = _make_candidate_log()
    report = compare_traces(baseline, candidate, regression_threshold_pct=10.0)
    assert report.candidate_total_ms > report.baseline_total_ms
    assert report.overall_delta_ms > 0
    assert report.overall_delta_pct > 0


def test_compare_traces_tool_regression() -> None:
    baseline = _make_baseline_log()
    candidate = _make_candidate_log()
    report = compare_traces(baseline, candidate, regression_threshold_pct=10.0)
    search_reg = [t for t in report.tool_regressions if t.tool == "Search"]
    assert len(search_reg) == 1
    assert search_reg[0].regressed is True
    assert search_reg[0].delta_pct > 100.0


def test_compare_traces_no_regression() -> None:
    baseline = _make_baseline_log()
    report = compare_traces(baseline, baseline, regression_threshold_pct=10.0)
    assert report.overall_regressed is False
    regressed = [t for t in report.tool_regressions if t.regressed]
    assert len(regressed) == 0


def test_compare_traces_new_removed_tools() -> None:
    baseline = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.1),
            ThinkEvent(content="done", agent="Bot", ts=0.2),
        ]
    )
    candidate = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Fetch", args={}, agent="Bot", ts=0.1),
            ThinkEvent(content="done", agent="Bot", ts=0.2),
        ]
    )
    report = compare_traces(baseline, candidate)
    assert "Fetch" in report.new_tools
    assert "Search" in report.removed_tools


def test_compare_traces_new_removed_agents() -> None:
    baseline = TraceLog(
        events=[
            ThinkEvent(content="a", agent="Agent1", ts=0.0),
            ActEvent(tool="X", args={}, agent="Agent1", ts=0.1),
        ]
    )
    candidate = TraceLog(
        events=[
            ThinkEvent(content="a", agent="Agent2", ts=0.0),
            ActEvent(tool="X", args={}, agent="Agent2", ts=0.1),
        ]
    )
    report = compare_traces(baseline, candidate)
    assert "Agent2" in report.new_agents
    assert "Agent1" in report.removed_agents


def test_compare_traces_event_delta() -> None:
    baseline = _make_baseline_log()
    candidate = TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot", ts=0.0),
            ActEvent(tool="Search", args={}, agent="Bot", ts=0.1),
            ThinkEvent(content="done", agent="Bot", ts=0.2),
        ]
    )
    report = compare_traces(baseline, candidate)
    assert report.event_delta == -1


def test_compare_traces_to_dict() -> None:
    baseline = _make_baseline_log()
    candidate = _make_candidate_log()
    report = compare_traces(baseline, candidate)
    data = report.to_dict()
    assert "baseline_total_ms" in data
    assert "candidate_total_ms" in data
    assert "tool_regressions" in data
    assert "agent_regressions" in data
    assert "new_tools" in data
    assert "removed_tools" in data


def test_compare_traces_threshold() -> None:
    baseline = _make_baseline_log()
    candidate = _make_candidate_log()
    report = compare_traces(baseline, candidate, regression_threshold_pct=500.0)
    regressed = [t for t in report.tool_regressions if t.regressed]
    assert len(regressed) == 0


def test_compare_trace_files(tmp_path) -> None:
    baseline = _make_baseline_log()
    candidate = _make_candidate_log()
    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    baseline_path.write_text(baseline.to_jsonl(), encoding="utf-8")
    candidate_path.write_text(candidate.to_jsonl(), encoding="utf-8")
    report = compare_trace_files(baseline_path, candidate_path)
    assert report.baseline_events == 4
    assert report.candidate_events == 4


def test_compare_traces_empty_logs() -> None:
    report = compare_traces(TraceLog(events=[]), TraceLog(events=[]))
    assert report.baseline_events == 0
    assert report.candidate_events == 0
    assert report.overall_regressed is False
