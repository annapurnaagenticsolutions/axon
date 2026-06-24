"""Tests for the AXON Debugger."""

from __future__ import annotations

from axon.debugger import Breakpoint, DebugSession, Debugger
from axon.trace import ActEvent, ObserveEvent, StoreEvent, ThinkEvent, TraceLog


def _make_log() -> TraceLog:
    return TraceLog(
        events=[
            ThinkEvent(content="start", agent="Bot"),
            ActEvent(tool="Search", args={"q": "hello"}, agent="Bot"),
            StoreEvent(key="result", value="found", agent="Bot"),
            ObserveEvent(name="done", value=True, agent="Bot"),
            ThinkEvent(content="finish", agent="Bot"),
        ]
    )


def test_debug_session_step() -> None:
    session = DebugSession(log=_make_log())
    assert session.index == 0
    assert session.current.t == "think"
    ev = session.next()
    assert ev is not None
    assert ev.t == "act"
    assert session.index == 1


def test_debug_session_prev() -> None:
    session = DebugSession(log=_make_log(), index=2)
    ev = session.prev()
    assert ev is not None
    assert ev.t == "act"
    assert session.index == 1


def test_debug_session_goto_rebuilds_memory() -> None:
    session = DebugSession(log=_make_log())
    session.goto(3)
    assert "result" in session.memory
    assert session.memory["result"] == "found"


def test_debug_session_search() -> None:
    session = DebugSession(log=_make_log())
    idx = session.search("Search")
    assert idx == 1
    assert session.current.t == "act"


def test_breakpoint_matches_event_type() -> None:
    bp = Breakpoint(event_type="act")
    log = _make_log()
    assert bp.matches(log.events[1])
    assert not bp.matches(log.events[0])


def test_breakpoint_matches_agent() -> None:
    bp = Breakpoint(agent="Bot", event_type="think")
    log = _make_log()
    assert bp.matches(log.events[0])
    assert not bp.matches(ThinkEvent(content="x", agent="Other"))


def test_breakpoint_matches_tool() -> None:
    bp = Breakpoint(tool="Search")
    log = _make_log()
    assert bp.matches(log.events[1])
    assert not bp.matches(log.events[0])


def test_debug_session_check_breakpoint() -> None:
    session = DebugSession(log=_make_log())
    session.add_breakpoint(Breakpoint(event_type="act"))
    session.goto(1)
    hit = session.check_breakpoint()
    assert hit is not None
    assert hit.event_type == "act"


def test_debugger_loads_trace() -> None:
    import tempfile
    from pathlib import Path
    log = _make_log()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(log.to_jsonl())
        path = f.name
    dbg = Debugger(path)
    assert dbg.session.total == 5
    Path(path).unlink()


def test_debug_session_format_current() -> None:
    session = DebugSession(log=_make_log())
    text = session.format_current()
    assert "THINK" in text
    assert "start" in text


def test_debug_session_format_memory() -> None:
    session = DebugSession(log=_make_log())
    session.goto(2)
    text = session.format_memory()
    assert "result" in text
    assert "found" in text
