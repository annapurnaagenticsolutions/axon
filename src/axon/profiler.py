"""AXON Profiler — execution time profiling per agent and method.

Reads AEL trace logs and computes timing breakdowns for:
- Per-agent total and average time
- Per-tool act call latency
- Method-level breakdowns when trace metadata includes method names
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axon.trace import ActEvent, TraceLog
from axon.trace_reader import read_trace_file


@dataclass
class AgentProfile:
    """Timing profile for a single agent."""

    agent: str
    total_ms: float = 0.0
    event_count: int = 0
    act_calls: int = 0
    act_total_ms: float = 0.0
    think_tokens: int = 0
    method_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class ProfileReport:
    """Full profiler report for a trace log."""

    agents: dict[str, AgentProfile] = field(default_factory=dict)
    overall_ms: float = 0.0
    total_events: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_ms": round(self.overall_ms, 3),
            "total_events": self.total_events,
            "agents": {
                name: {
                    "total_ms": round(p.total_ms, 3),
                    "event_count": p.event_count,
                    "act_calls": p.act_calls,
                    "act_avg_ms": round(p.act_total_ms / p.act_calls, 3) if p.act_calls else 0,
                    "think_tokens": p.think_tokens,
                    "method_breakdown": {
                        k: round(v, 3) for k, v in p.method_breakdown.items()
                    },
                }
                for name, p in self.agents.items()
            },
        }


class Profiler:
    """Profile AXON trace logs for performance insights."""

    def __init__(self, log: TraceLog) -> None:
        self.log = log

    def profile(self) -> ProfileReport:
        """Compute timing profile from the trace log."""
        report = ProfileReport(total_events=len(self.log.events))
        events = self.log.events

        if not events:
            return report

        # Overall span from first to last timestamp
        first_ts = getattr(events[0], "ts", None)
        last_ts = getattr(events[-1], "ts", None)
        if first_ts is not None and last_ts is not None:
            report.overall_ms = (last_ts - first_ts) * 1000

        # Per-agent breakdown
        for i, ev in enumerate(events):
            agent = getattr(ev, "agent", None) or "unknown"
            if agent not in report.agents:
                report.agents[agent] = AgentProfile(agent=agent)
            profile = report.agents[agent]
            profile.event_count += 1

            # Calculate time since previous event for this agent
            prev_ts = None
            for j in range(i - 1, -1, -1):
                if getattr(events[j], "agent", None) == agent and getattr(events[j], "ts", None) is not None:
                    prev_ts = events[j].ts
                    break
            if prev_ts is not None and ev.ts is not None:
                delta = (ev.ts - prev_ts) * 1000
                profile.total_ms += delta

            if isinstance(ev, ActEvent):
                profile.act_calls += 1
                if prev_ts is not None and ev.ts is not None:
                    profile.act_total_ms += (ev.ts - prev_ts) * 1000

            if ev.t == "think":
                tokens = getattr(ev, "tokens", None)
                if tokens is not None:
                    profile.think_tokens += tokens

            # Method breakdown from metadata
            metadata = getattr(ev, "metadata", None) or {}
            method = metadata.get("method")
            if method:
                if method not in profile.method_breakdown:
                    profile.method_breakdown[method] = 0.0
                if prev_ts is not None and ev.ts is not None:
                    profile.method_breakdown[method] += (ev.ts - prev_ts) * 1000

        return report


def profile_trace(trace_path: str | Path) -> ProfileReport:
    """Convenience: profile a trace file directly."""
    log = read_trace_file(trace_path)
    return Profiler(log).profile()
