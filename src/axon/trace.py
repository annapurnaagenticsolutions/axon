"""AEL trace data model for AXON.

This module intentionally models trace events only. It does not execute AXON
agent methods, dispatch tools, call model providers, or interpret AXON source.

AEL traces are line-oriented JSON records that can be read by humans, replayed
by future tooling, and inspected by tests. The event shape follows the Phase 0
spec vocabulary:

- think   — trace-only reasoning note
- act     — external tool invocation
- observe — named intermediate observation
- store   — memory write
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, TypeAlias
import json
import time


TraceEventType: TypeAlias = Literal["think", "act", "observe", "store"]


class TraceFormatError(ValueError):
    """Raised when a trace JSON object cannot be interpreted as an AEL event."""


@dataclass(frozen=True)
class BaseTraceEvent:
    """Common fields shared by all AEL trace events.

    Concrete event classes set ``t`` to one of the AXON AEL event names. ``ts``
    is optional in the data model so tests and offline tooling can construct
    deterministic events. ``TraceRecorder`` fills it automatically.
    """

    t: TraceEventType
    agent: str | None = None
    ts: int | float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a compact JSON-serialisable dictionary for this event."""
        raise NotImplementedError

    def to_json(self) -> str:
        """Serialise this event as one compact JSON object."""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class ThinkEvent(BaseTraceEvent):
    """A trace-only reasoning note.

    ``think`` does not call a model and does not return a value. It records why
    an agent is about to do something.
    """

    content: str = ""
    tokens: int | None = None

    def __init__(
        self,
        content: str,
        *,
        agent: str | None = None,
        ts: int | float | None = None,
        tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "t", "think")
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "ts", ts)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "tokens", tokens)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "t": self.t,
                "content": self.content,
                "agent": self.agent,
                "ts": self.ts,
                "tokens": self.tokens,
                "metadata": _json_safe(self.metadata) if self.metadata else None,
            }
        )


@dataclass(frozen=True)
class ActEvent(BaseTraceEvent):
    """An external tool invocation.

    ``args`` are preserved as structured JSON where possible. Non-serialisable
    values are converted to ``repr(value)`` by ``to_dict`` so trace writing never
    fails because of a preview object.
    """

    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        agent: str | None = None,
        ts: int | float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "t", "act")
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "ts", ts)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "args", dict(args or {}))

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "t": self.t,
                "tool": self.tool,
                "args": _json_safe(self.args),
                "agent": self.agent,
                "ts": self.ts,
                "metadata": _json_safe(self.metadata) if self.metadata else None,
            }
        )


@dataclass(frozen=True)
class ObserveEvent(BaseTraceEvent):
    """A named observation produced during an agent run."""

    name: str = ""
    value: Any = None
    count: int | None = None

    def __init__(
        self,
        name: str,
        value: Any = None,
        *,
        count: int | None = None,
        agent: str | None = None,
        ts: int | float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "t", "observe")
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "ts", ts)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "count", count)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "t": self.t,
                "name": self.name,
                "value": _json_safe(self.value) if self.value is not None else None,
                "count": self.count,
                "agent": self.agent,
                "ts": self.ts,
                "metadata": _json_safe(self.metadata) if self.metadata else None,
            }
        )


@dataclass(frozen=True)
class StoreEvent(BaseTraceEvent):
    """A memory write event."""

    key: str = ""
    value: Any = None

    def __init__(
        self,
        key: str,
        value: Any = None,
        *,
        agent: str | None = None,
        ts: int | float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "t", "store")
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "ts", ts)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "value", value)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "t": self.t,
                "key": self.key,
                "value": _json_safe(self.value) if self.value is not None else None,
                "agent": self.agent,
                "ts": self.ts,
                "metadata": _json_safe(self.metadata) if self.metadata else None,
            }
        )


AELTraceEvent: TypeAlias = ThinkEvent | ActEvent | ObserveEvent | StoreEvent


@dataclass
class TraceLog:
    """A small in-memory collection of AEL trace events."""

    events: list[AELTraceEvent] = field(default_factory=list)

    def append(self, event: AELTraceEvent) -> AELTraceEvent:
        self.events.append(event)
        return event

    def extend(self, events: Iterable[AELTraceEvent]) -> None:
        self.events.extend(events)

    def by_type(self, event_type: TraceEventType) -> list[AELTraceEvent]:
        return [event for event in self.events if event.t == event_type]

    def by_agent(self, agent: str) -> list[AELTraceEvent]:
        return [event for event in self.events if event.agent == agent]

    def to_jsonl(self) -> str:
        if not self.events:
            return ""
        return "\n".join(event.to_json() for event in self.events) + "\n"

    @classmethod
    def from_jsonl(cls, text: str) -> "TraceLog":
        events: list[AELTraceEvent] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise TraceFormatError(f"invalid JSON on trace line {line_number}: {exc}") from exc
            events.append(event_from_dict(raw, line_number=line_number))
        return cls(events=events)

    def write(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_jsonl(), encoding="utf-8")
        return destination

    @classmethod
    def read(cls, path: str | Path) -> "TraceLog":
        source = Path(path)
        return cls.from_jsonl(source.read_text(encoding="utf-8"))


class TraceRecorder:
    """Convenience helper that records events with shared agent and clock.

    It is intentionally tiny and deterministic. Tests can inject ``clock`` to
    avoid wall-clock dependence. Future runtime work can reuse this class when
    AXON method execution exists.
    """

    def __init__(
        self,
        *,
        agent: str | None = None,
        clock: Callable[[], int | float] | None = None,
    ) -> None:
        self.agent = agent
        self.clock = clock or (lambda: int(time.time()))
        self.log = TraceLog()

    @property
    def events(self) -> list[AELTraceEvent]:
        return self.log.events

    def think(self, content: str, *, tokens: int | None = None, metadata: dict[str, Any] | None = None) -> ThinkEvent:
        return self.log.append(
            ThinkEvent(content, agent=self.agent, ts=self.clock(), tokens=tokens, metadata=metadata)
        )

    def act(self, tool: str, args: dict[str, Any] | None = None, *, metadata: dict[str, Any] | None = None) -> ActEvent:
        return self.log.append(ActEvent(tool, args, agent=self.agent, ts=self.clock(), metadata=metadata))

    def observe(
        self,
        name: str,
        value: Any = None,
        *,
        count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ObserveEvent:
        return self.log.append(
            ObserveEvent(name, value, count=count, agent=self.agent, ts=self.clock(), metadata=metadata)
        )

    def store(self, key: str, value: Any = None, *, metadata: dict[str, Any] | None = None) -> StoreEvent:
        return self.log.append(StoreEvent(key, value, agent=self.agent, ts=self.clock(), metadata=metadata))

    def to_trace_log(self) -> TraceLog:
        return TraceLog(events=list(self.events))


def event_from_dict(data: dict[str, Any], *, line_number: int | None = None) -> AELTraceEvent:
    """Create a concrete trace event from a dictionary.

    Args:
        data: Decoded JSON object with a ``t`` field.
        line_number: Optional JSONL line number used in error messages.
    """
    if not isinstance(data, dict):
        raise TraceFormatError(_with_line("trace event must be a JSON object", line_number))

    event_type = data.get("t")
    if event_type == "think":
        return ThinkEvent(
            _require_str(data, "content", line_number),
            agent=_optional_str(data, "agent", line_number),
            ts=_optional_number(data, "ts", line_number),
            tokens=_optional_int(data, "tokens", line_number),
            metadata=_optional_dict(data, "metadata", line_number),
        )
    if event_type == "act":
        return ActEvent(
            _require_str(data, "tool", line_number),
            _optional_dict(data, "args", line_number) or {},
            agent=_optional_str(data, "agent", line_number),
            ts=_optional_number(data, "ts", line_number),
            metadata=_optional_dict(data, "metadata", line_number),
        )
    if event_type == "observe":
        return ObserveEvent(
            _require_str(data, "name", line_number),
            data.get("value"),
            count=_optional_int(data, "count", line_number),
            agent=_optional_str(data, "agent", line_number),
            ts=_optional_number(data, "ts", line_number),
            metadata=_optional_dict(data, "metadata", line_number),
        )
    if event_type == "store":
        return StoreEvent(
            _require_str(data, "key", line_number),
            data.get("value"),
            agent=_optional_str(data, "agent", line_number),
            ts=_optional_number(data, "ts", line_number),
            metadata=_optional_dict(data, "metadata", line_number),
        )

    raise TraceFormatError(_with_line(f"unknown trace event type: {event_type!r}", line_number))


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _json_safe(value: Any) -> Any:
    """Return ``value`` if JSON-serialisable, otherwise a readable repr."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(v) for v in value]
        return repr(value)


def _require_str(data: dict[str, Any], key: str, line_number: int | None) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise TraceFormatError(_with_line(f"trace field '{key}' must be a string", line_number))
    return value


def _optional_str(data: dict[str, Any], key: str, line_number: int | None) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TraceFormatError(_with_line(f"trace field '{key}' must be a string", line_number))
    return value


def _optional_int(data: dict[str, Any], key: str, line_number: int | None) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TraceFormatError(_with_line(f"trace field '{key}' must be an integer", line_number))
    return value


def _optional_number(data: dict[str, Any], key: str, line_number: int | None) -> int | float | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TraceFormatError(_with_line(f"trace field '{key}' must be a number", line_number))
    return value


def _optional_dict(data: dict[str, Any], key: str, line_number: int | None) -> dict[str, Any] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TraceFormatError(_with_line(f"trace field '{key}' must be an object", line_number))
    return dict(value)


def _with_line(message: str, line_number: int | None) -> str:
    return f"line {line_number}: {message}" if line_number is not None else message
