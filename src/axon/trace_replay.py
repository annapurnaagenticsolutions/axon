"""AXON Trace Replay — replay trace events with timing and detect regressions.

Reads AEL trace logs and provides:
- Trace replay: walk events with timing, emit progress, collect per-event metrics
- Regression detection: compare two traces (baseline vs candidate) and flag
  per-tool and per-agent latency regressions
- Diff summary: event count changes, new/removed tools, timing deltas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axon.profiler import ProfileReport, Profiler, _percentile
from axon.trace import ActEvent, TraceLog
from axon.trace_reader import read_trace_file


@dataclass
class ReplayStep:
    """One step in a replay sequence."""

    index: int
    event_type: str
    agent: str
    tool: str | None
    latency_ms: float
    description: str
    cumulative_ms: float


@dataclass
class ReplayResult:
    """Result of replaying a trace."""

    steps: list[ReplayStep] = field(default_factory=list)
    total_ms: float = 0.0
    total_events: int = 0
    report: ProfileReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_ms": round(self.total_ms, 3),
            "total_events": self.total_events,
            "steps": [
                {
                    "index": s.index,
                    "event_type": s.event_type,
                    "agent": s.agent,
                    "tool": s.tool,
                    "latency_ms": round(s.latency_ms, 3),
                    "cumulative_ms": round(s.cumulative_ms, 3),
                    "description": s.description,
                }
                for s in self.steps
            ],
        }


@dataclass
class ToolRegression:
    """Per-tool regression info."""

    tool: str
    baseline_avg_ms: float
    candidate_avg_ms: float
    delta_ms: float
    delta_pct: float
    baseline_p95_ms: float
    candidate_p95_ms: float
    regressed: bool


@dataclass
class AgentRegression:
    """Per-agent regression info."""

    agent: str
    baseline_total_ms: float
    candidate_total_ms: float
    delta_ms: float
    delta_pct: float
    baseline_events: int
    candidate_events: int
    regressed: bool


@dataclass
class RegressionReport:
    """Comparison report between baseline and candidate traces."""

    baseline_total_ms: float = 0.0
    candidate_total_ms: float = 0.0
    overall_delta_ms: float = 0.0
    overall_delta_pct: float = 0.0
    overall_regressed: bool = False
    tool_regressions: list[ToolRegression] = field(default_factory=list)
    agent_regressions: list[AgentRegression] = field(default_factory=list)
    new_tools: list[str] = field(default_factory=list)
    removed_tools: list[str] = field(default_factory=list)
    new_agents: list[str] = field(default_factory=list)
    removed_agents: list[str] = field(default_factory=list)
    baseline_events: int = 0
    candidate_events: int = 0
    event_delta: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_total_ms": round(self.baseline_total_ms, 3),
            "candidate_total_ms": round(self.candidate_total_ms, 3),
            "overall_delta_ms": round(self.overall_delta_ms, 3),
            "overall_delta_pct": round(self.overall_delta_pct, 1),
            "overall_regressed": self.overall_regressed,
            "baseline_events": self.baseline_events,
            "candidate_events": self.candidate_events,
            "event_delta": self.event_delta,
            "new_tools": self.new_tools,
            "removed_tools": self.removed_tools,
            "new_agents": self.new_agents,
            "removed_agents": self.removed_agents,
            "tool_regressions": [
                {
                    "tool": t.tool,
                    "baseline_avg_ms": round(t.baseline_avg_ms, 3),
                    "candidate_avg_ms": round(t.candidate_avg_ms, 3),
                    "delta_ms": round(t.delta_ms, 3),
                    "delta_pct": round(t.delta_pct, 1),
                    "baseline_p95_ms": round(t.baseline_p95_ms, 3),
                    "candidate_p95_ms": round(t.candidate_p95_ms, 3),
                    "regressed": t.regressed,
                }
                for t in self.tool_regressions
            ],
            "agent_regressions": [
                {
                    "agent": a.agent,
                    "baseline_total_ms": round(a.baseline_total_ms, 3),
                    "candidate_total_ms": round(a.candidate_total_ms, 3),
                    "delta_ms": round(a.delta_ms, 3),
                    "delta_pct": round(a.delta_pct, 1),
                    "baseline_events": a.baseline_events,
                    "candidate_events": a.candidate_events,
                    "regressed": a.regressed,
                }
                for a in self.agent_regressions
            ],
        }


class TraceReplayer:
    """Replay AEL trace events with timing information."""

    def __init__(self, log: TraceLog) -> None:
        self.log = log

    def replay(self) -> ReplayResult:
        """Walk trace events, computing per-event latency and cumulative time."""
        profiler = Profiler(self.log)
        report = profiler.profile()

        result = ReplayResult(
            total_ms=report.overall_ms,
            total_events=report.total_events,
            report=report,
        )

        events = self.log.events
        cumulative = 0.0

        for i, ev in enumerate(events):
            agent = getattr(ev, "agent", None) or "unknown"

            # Calculate latency since previous event for this agent
            prev_ts = None
            for j in range(i - 1, -1, -1):
                if getattr(events[j], "agent", None) == agent and getattr(events[j], "ts", None) is not None:
                    prev_ts = events[j].ts
                    break

            latency_ms = 0.0
            if prev_ts is not None and ev.ts is not None:
                latency_ms = (ev.ts - prev_ts) * 1000

            cumulative += latency_ms

            tool_name = getattr(ev, "tool", None) if isinstance(ev, ActEvent) else None
            desc = ""
            if ev.t == "think":
                content = getattr(ev, "content", "")
                desc = content[:60] if content else ""
            elif isinstance(ev, ActEvent):
                desc = f"act {ev.tool}"
            elif ev.t == "store":
                key = getattr(ev, "key", "")
                desc = f"store {key}"
            elif ev.t == "observe":
                name = getattr(ev, "name", "")
                desc = f"observe {name}"

            result.steps.append(ReplayStep(
                index=i,
                event_type=ev.t,
                agent=agent,
                tool=tool_name,
                latency_ms=latency_ms,
                description=desc,
                cumulative_ms=cumulative,
            ))

        return result


def compare_traces(
    baseline: TraceLog,
    candidate: TraceLog,
    *,
    regression_threshold_pct: float = 10.0,
) -> RegressionReport:
    """Compare two trace logs and detect regressions.

    Args:
        baseline: The baseline (previous) trace log.
        candidate: The candidate (new) trace log.
        regression_threshold_pct: Percentage increase threshold to flag as
            regression (default 10%).

    Returns:
        RegressionReport with per-tool and per-agent comparisons.
    """
    baseline_report = Profiler(baseline).profile()
    candidate_report = Profiler(candidate).profile()

    report = RegressionReport(
        baseline_total_ms=baseline_report.overall_ms,
        candidate_total_ms=candidate_report.overall_ms,
        baseline_events=baseline_report.total_events,
        candidate_events=candidate_report.total_events,
        event_delta=candidate_report.total_events - baseline_report.total_events,
    )

    # Overall comparison
    if baseline_report.overall_ms > 0:
        report.overall_delta_ms = candidate_report.overall_ms - baseline_report.overall_ms
        report.overall_delta_pct = (report.overall_delta_ms / baseline_report.overall_ms) * 100.0
        report.overall_regressed = report.overall_delta_pct >= regression_threshold_pct

    # Per-tool comparison
    baseline_tools = set(baseline_report.tools.keys())
    candidate_tools = set(candidate_report.tools.keys())
    report.new_tools = sorted(candidate_tools - baseline_tools)
    report.removed_tools = sorted(baseline_tools - candidate_tools)

    for tool_name in sorted(baseline_tools & candidate_tools):
        bt = baseline_report.tools[tool_name]
        ct = candidate_report.tools[tool_name]
        delta_ms = ct.avg_ms - bt.avg_ms
        delta_pct = (delta_ms / bt.avg_ms * 100.0) if bt.avg_ms > 0 else 0.0
        report.tool_regressions.append(ToolRegression(
            tool=tool_name,
            baseline_avg_ms=bt.avg_ms,
            candidate_avg_ms=ct.avg_ms,
            delta_ms=delta_ms,
            delta_pct=delta_pct,
            baseline_p95_ms=bt.p95_ms,
            candidate_p95_ms=ct.p95_ms,
            regressed=delta_pct >= regression_threshold_pct,
        ))

    # Per-agent comparison
    baseline_agents = set(baseline_report.agents.keys())
    candidate_agents = set(candidate_report.agents.keys())
    report.new_agents = sorted(candidate_agents - baseline_agents)
    report.removed_agents = sorted(baseline_agents - candidate_agents)

    for agent_name in sorted(baseline_agents & candidate_agents):
        ba = baseline_report.agents[agent_name]
        ca = candidate_report.agents[agent_name]
        delta_ms = ca.total_ms - ba.total_ms
        delta_pct = (delta_ms / ba.total_ms * 100.0) if ba.total_ms > 0 else 0.0
        report.agent_regressions.append(AgentRegression(
            agent=agent_name,
            baseline_total_ms=ba.total_ms,
            candidate_total_ms=ca.total_ms,
            delta_ms=delta_ms,
            delta_pct=delta_pct,
            baseline_events=ba.event_count,
            candidate_events=ca.event_count,
            regressed=delta_pct >= regression_threshold_pct,
        ))

    return report


def replay_trace(trace_path: str | Path) -> ReplayResult:
    """Convenience: replay a trace file directly."""
    log = read_trace_file(trace_path)
    return TraceReplayer(log).replay()


def compare_trace_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    regression_threshold_pct: float = 10.0,
) -> RegressionReport:
    """Convenience: compare two trace files directly."""
    baseline = read_trace_file(baseline_path)
    candidate = read_trace_file(candidate_path)
    return compare_traces(baseline, candidate, regression_threshold_pct=regression_threshold_pct)
