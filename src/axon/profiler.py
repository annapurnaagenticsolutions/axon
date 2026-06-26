"""AXON Profiler — execution time profiling per agent, tool, and method.

Reads AEL trace logs and computes timing breakdowns for:
- Per-agent total and average time
- Per-tool act call latency with percentile stats (p50/p95/p99)
- Per-think event timing with token throughput
- Method-level breakdowns when trace metadata includes method names
- Hotspot detection (slowest events and tools)
- CSV export for spreadsheet analysis
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axon.trace import ActEvent, TraceLog
from axon.trace_reader import read_trace_file


def _percentile(data: list[float], pct: float) -> float:
    """Compute the p-th percentile of a sorted-unsorted list."""
    if not data:
        return 0.0
    s = sorted(data)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


@dataclass
class ToolProfile:
    """Timing profile for a single tool across all agents."""

    tool: str
    call_count: int = 0
    total_ms: float = 0.0
    latencies: list[float] = field(default_factory=list)

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.call_count if self.call_count else 0.0

    @property
    def p50_ms(self) -> float:
        return _percentile(self.latencies, 50.0)

    @property
    def p95_ms(self) -> float:
        return _percentile(self.latencies, 95.0)

    @property
    def p99_ms(self) -> float:
        return _percentile(self.latencies, 99.0)


@dataclass
class ThinkProfile:
    """Timing profile for think events."""

    count: int = 0
    total_ms: float = 0.0
    latencies: list[float] = field(default_factory=list)
    total_tokens: int = 0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    @property
    def p50_ms(self) -> float:
        return _percentile(self.latencies, 50.0)

    @property
    def p95_ms(self) -> float:
        return _percentile(self.latencies, 95.0)

    @property
    def p99_ms(self) -> float:
        return _percentile(self.latencies, 99.0)

    @property
    def tokens_per_sec(self) -> float:
        if self.total_ms <= 0 or self.total_tokens <= 0:
            return 0.0
        return self.total_tokens / (self.total_ms / 1000.0)


@dataclass
class Hotspot:
    """A single hotspot event."""

    index: int
    event_type: str
    agent: str
    tool: str | None
    latency_ms: float
    description: str


@dataclass
class AgentProfile:
    """Timing profile for a single agent."""

    agent: str
    total_ms: float = 0.0
    event_count: int = 0
    act_calls: int = 0
    act_total_ms: float = 0.0
    think_tokens: int = 0
    think_count: int = 0
    think_total_ms: float = 0.0
    method_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class ProfileReport:
    """Full profiler report for a trace log."""

    agents: dict[str, AgentProfile] = field(default_factory=dict)
    tools: dict[str, ToolProfile] = field(default_factory=dict)
    think: ThinkProfile = field(default_factory=ThinkProfile)
    hotspots: list[Hotspot] = field(default_factory=list)
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
                    "think_count": p.think_count,
                    "think_total_ms": round(p.think_total_ms, 3),
                    "method_breakdown": {
                        k: round(v, 3) for k, v in p.method_breakdown.items()
                    },
                }
                for name, p in self.agents.items()
            },
            "tools": {
                name: {
                    "call_count": p.call_count,
                    "total_ms": round(p.total_ms, 3),
                    "avg_ms": round(p.avg_ms, 3),
                    "p50_ms": round(p.p50_ms, 3),
                    "p95_ms": round(p.p95_ms, 3),
                    "p99_ms": round(p.p99_ms, 3),
                }
                for name, p in self.tools.items()
            },
            "think": {
                "count": self.think.count,
                "total_ms": round(self.think.total_ms, 3),
                "avg_ms": round(self.think.avg_ms, 3),
                "p50_ms": round(self.think.p50_ms, 3),
                "p95_ms": round(self.think.p95_ms, 3),
                "p99_ms": round(self.think.p99_ms, 3),
                "total_tokens": self.think.total_tokens,
                "tokens_per_sec": round(self.think.tokens_per_sec, 1),
            },
            "hotspots": [
                {
                    "index": h.index,
                    "event_type": h.event_type,
                    "agent": h.agent,
                    "tool": h.tool,
                    "latency_ms": round(h.latency_ms, 3),
                    "description": h.description,
                }
                for h in self.hotspots
            ],
        }

    def to_csv(self) -> str:
        """Export per-event timing data as CSV."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["index", "event_type", "agent", "tool", "latency_ms", "tokens", "description"])
        for h in self._event_rows:
            writer.writerow(h)
        return buf.getvalue()

    def to_tool_csv(self) -> str:
        """Export per-tool summary as CSV."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["tool", "call_count", "total_ms", "avg_ms", "p50_ms", "p95_ms", "p99_ms"])
        for name, p in sorted(self.tools.items(), key=lambda kv: kv[1].total_ms, reverse=True):
            writer.writerow([name, p.call_count, round(p.total_ms, 3), round(p.avg_ms, 3), round(p.p50_ms, 3), round(p.p95_ms, 3), round(p.p99_ms, 3)])
        return buf.getvalue()


class Profiler:
    """Profile AXON trace logs for performance insights."""

    def __init__(self, log: TraceLog, hotspot_threshold_ms: float = 100.0, max_hotspots: int = 10) -> None:
        self.log = log
        self.hotspot_threshold_ms = hotspot_threshold_ms
        self.max_hotspots = max_hotspots

    def profile(self) -> ProfileReport:
        """Compute timing profile from the trace log."""
        report = ProfileReport(total_events=len(self.log.events))
        events = self.log.events
        report._event_rows = []

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
            delta_ms = 0.0
            if prev_ts is not None and ev.ts is not None:
                delta_ms = (ev.ts - prev_ts) * 1000
                profile.total_ms += delta_ms

            # Build description for CSV/hotspot
            tool_name = getattr(ev, "tool", None) if isinstance(ev, ActEvent) else None
            tokens = getattr(ev, "tokens", None) if ev.t == "think" else None
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

            report._event_rows.append([
                i,
                ev.t,
                agent,
                tool_name or "",
                round(delta_ms, 3),
                tokens or "",
                desc,
            ])

            # Hotspot detection
            if delta_ms >= self.hotspot_threshold_ms:
                report.hotspots.append(Hotspot(
                    index=i,
                    event_type=ev.t,
                    agent=agent,
                    tool=tool_name,
                    latency_ms=delta_ms,
                    description=desc,
                ))

            if isinstance(ev, ActEvent):
                profile.act_calls += 1
                if delta_ms > 0:
                    profile.act_total_ms += delta_ms

                # Per-tool profile
                tool = ev.tool
                if tool not in report.tools:
                    report.tools[tool] = ToolProfile(tool=tool)
                tp = report.tools[tool]
                tp.call_count += 1
                tp.total_ms += delta_ms
                tp.latencies.append(delta_ms)

            if ev.t == "think":
                profile.think_count += 1
                report.think.count += 1
                if delta_ms > 0:
                    profile.think_total_ms += delta_ms
                    report.think.total_ms += delta_ms
                    report.think.latencies.append(delta_ms)
                if tokens is not None:
                    profile.think_tokens += tokens
                    report.think.total_tokens += tokens

            # Method breakdown from metadata
            metadata = getattr(ev, "metadata", None) or {}
            method = metadata.get("method")
            if method:
                if method not in profile.method_breakdown:
                    profile.method_breakdown[method] = 0.0
                if delta_ms > 0:
                    profile.method_breakdown[method] += delta_ms

        # Sort hotspots by latency descending, keep top N
        report.hotspots.sort(key=lambda h: h.latency_ms, reverse=True)
        report.hotspots = report.hotspots[:self.max_hotspots]

        return report


def profile_trace(
    trace_path: str | Path,
    *,
    hotspot_threshold_ms: float = 100.0,
    max_hotspots: int = 10,
) -> ProfileReport:
    """Convenience: profile a trace file directly."""
    log = read_trace_file(trace_path)
    return Profiler(log, hotspot_threshold_ms=hotspot_threshold_ms, max_hotspots=max_hotspots).profile()
