"""Utilities for reading and summarising AXON AEL JSONL trace logs.

This module is intentionally inspection-only. It does not replay traces, execute
agent logic, dispatch tools, or call model providers. It gives Phase 1 tooling a
safe way to validate trace files, filter events, and present compact summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

from axon.trace import AELTraceEvent, TraceEventType, TraceLog


@dataclass(frozen=True)
class TraceSummary:
    """Compact statistics for one filtered or unfiltered trace log."""

    total_events: int
    counts_by_type: dict[str, int] = field(default_factory=dict)
    counts_by_agent: dict[str, int] = field(default_factory=dict)
    first_ts: int | float | None = None
    last_ts: int | float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "counts_by_type": dict(self.counts_by_type),
            "counts_by_agent": dict(self.counts_by_agent),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
        }


def read_trace_file(path: str | Path) -> TraceLog:
    """Read and validate one AXON JSONL trace file.

    Args:
        path: File containing one JSON trace event per line.

    Raises:
        FileNotFoundError: when the path does not exist.
        IsADirectoryError: when the path is a directory.
        TraceFormatError: propagated from ``TraceLog.from_jsonl`` for malformed
            JSON or invalid trace event fields.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"trace file not found: {source}")
    if not source.is_file():
        raise IsADirectoryError(f"trace path is not a file: {source}")
    return TraceLog.read(source)


def filter_trace_log(
    log: TraceLog,
    *,
    event_type: TraceEventType | None = None,
    agent: str | None = None,
) -> TraceLog:
    """Return a new TraceLog containing only events matching all filters."""
    events: list[AELTraceEvent] = []
    for event in log.events:
        if event_type is not None and event.t != event_type:
            continue
        if agent is not None and event.agent != agent:
            continue
        events.append(event)
    return TraceLog(events=events)


def summarize_trace_log(log: TraceLog) -> TraceSummary:
    """Compute counts by event type and agent plus timestamp bounds."""
    counts_by_type: dict[str, int] = {}
    counts_by_agent: dict[str, int] = {}
    timestamps: list[int | float] = []

    for event in log.events:
        counts_by_type[event.t] = counts_by_type.get(event.t, 0) + 1
        if event.agent:
            counts_by_agent[event.agent] = counts_by_agent.get(event.agent, 0) + 1
        if event.ts is not None:
            timestamps.append(event.ts)

    return TraceSummary(
        total_events=len(log.events),
        counts_by_type=dict(sorted(counts_by_type.items())),
        counts_by_agent=dict(sorted(counts_by_agent.items())),
        first_ts=min(timestamps) if timestamps else None,
        last_ts=max(timestamps) if timestamps else None,
    )


def trace_events_to_dicts(log: TraceLog) -> list[dict[str, Any]]:
    """Return JSON-serialisable dictionaries for all events in a log."""
    return [event.to_dict() for event in log.events]


def trace_report_to_json(log: TraceLog, *, source: str | Path | None = None) -> str:
    """Return a JSON report containing summary and event objects."""
    payload: dict[str, Any] = {
        "summary": summarize_trace_log(log).to_dict(),
        "events": trace_events_to_dicts(log),
    }
    if source is not None:
        payload["source"] = str(source)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def format_trace_summary(
    log: TraceLog,
    *,
    source: str | Path | None = None,
    include_events: bool = False,
) -> str:
    """Format a trace log as a human-readable summary."""
    summary = summarize_trace_log(log)
    lines: list[str] = []
    heading = "AEL trace log"
    if source is not None:
        heading += f": {source}"
    lines.append(heading)
    lines.append(f"events: {summary.total_events}")

    if summary.counts_by_type:
        type_counts = ", ".join(f"{name}={count}" for name, count in summary.counts_by_type.items())
        lines.append(f"by type: {type_counts}")
    else:
        lines.append("by type: <none>")

    if summary.counts_by_agent:
        agent_counts = ", ".join(f"{name}={count}" for name, count in summary.counts_by_agent.items())
        lines.append(f"by agent: {agent_counts}")
    else:
        lines.append("by agent: <none>")

    if summary.first_ts is not None or summary.last_ts is not None:
        lines.append(f"time range: {summary.first_ts} -> {summary.last_ts}")

    if include_events:
        lines.append("")
        lines.append("events:")
        if log.events:
            for index, event in enumerate(log.events, start=1):
                lines.append(f"  {index}. {_format_event(event)}")
        else:
            lines.append("  <none>")

    return "\n".join(lines)


def _format_event(event: AELTraceEvent) -> str:
    prefix = event.t
    if event.agent:
        prefix += f" [{event.agent}]"

    if event.t == "think":
        text = event.content
        return f"{prefix}: {text}"
    if event.t == "act":
        args = ", ".join(f"{key}={value!r}" for key, value in event.args.items())
        return f"{prefix}: {event.tool}({args})"
    if event.t == "observe":
        if event.count is not None:
            return f"{prefix}: {event.name} count={event.count}"
        if event.value is not None:
            return f"{prefix}: {event.name} value={event.value!r}"
        return f"{prefix}: {event.name}"
    if event.t == "store":
        if event.value is not None:
            return f"{prefix}: {event.key} = {event.value!r}"
        return f"{prefix}: {event.key}"

    # All current event types are covered above. Keep a defensive fallback for
    # future event classes so trace inspection remains robust.
    return f"{prefix}: {event.to_dict()}"
