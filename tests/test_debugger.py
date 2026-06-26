"""Tests for the AXON Debugger."""

from __future__ import annotations

from axon.debugger import Breakpoint, DebugSession, Debugger, Watch
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


def test_breakpoint_matches_mem_key() -> None:
    bp = Breakpoint(mem_key="result")
    log = _make_log()
    memory = {"result": "found"}
    assert bp.matches(log.events[3], memory=memory)
    assert not bp.matches(log.events[3], memory={})


def test_breakpoint_matches_mem_key_value() -> None:
    bp = Breakpoint(mem_key="result", mem_value="found")
    log = _make_log()
    memory = {"result": "found"}
    assert bp.matches(log.events[3], memory=memory)
    memory_wrong = {"result": "not_found"}
    assert not bp.matches(log.events[3], memory=memory_wrong)


def test_breakpoint_once_removed_on_hit() -> None:
    bp = Breakpoint(event_type="act", once=True)
    session = DebugSession(log=_make_log())
    session.add_breakpoint(bp)
    session.goto(1)
    hit = session.check_breakpoint()
    assert hit is not None
    assert len(session.breakpoints) == 0


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


# --- New feature tests ---


def test_continue_until_breakpoint() -> None:
    session = DebugSession(log=_make_log())
    session.add_breakpoint(Breakpoint(event_type="store"))
    stepped, bp = session.continue_until_breakpoint()
    assert bp is not None
    assert bp.event_type == "store"
    assert stepped == 2
    assert session.index == 2


def test_continue_until_end_no_breakpoint() -> None:
    session = DebugSession(log=_make_log())
    stepped, bp = session.continue_until_breakpoint()
    assert bp is None
    assert stepped == 4
    assert session.index == 4


def test_watch_detects_initial_value() -> None:
    session = DebugSession(log=_make_log())
    session.goto(2)  # memory now has result=found
    session.add_watch("result")
    changes = session._check_watches()
    assert len(changes) == 1
    key, old, new = changes[0]
    assert key == "result"
    assert old is None
    assert new == "found"


def test_watch_detects_change() -> None:
    log = TraceLog(
        events=[
            StoreEvent(key="x", value=1, agent="Bot"),
            StoreEvent(key="x", value=2, agent="Bot"),
        ]
    )
    session = DebugSession(log=log)
    session.goto(0)
    session.add_watch("x")
    session._check_watches()  # initialize
    session.goto(1)
    changes = session._check_watches()
    assert len(changes) == 1
    key, old, new = changes[0]
    assert key == "x"
    assert old == 1
    assert new == 2


def test_watch_no_change() -> None:
    log = TraceLog(
        events=[
            StoreEvent(key="x", value=1, agent="Bot"),
            ThinkEvent(content="noop", agent="Bot"),
        ]
    )
    session = DebugSession(log=log)
    session.goto(0)
    session.add_watch("x")
    session._check_watches()  # initialize
    session.goto(1)
    changes = session._check_watches()
    assert len(changes) == 0


def test_add_and_remove_watch() -> None:
    session = DebugSession(log=_make_log())
    session.add_watch("result")
    assert len(session.watches) == 1
    assert session.remove_watch(0)
    assert len(session.watches) == 0
    assert not session.remove_watch(0)


def test_format_watches() -> None:
    session = DebugSession(log=_make_log())
    assert "(none)" in session.format_watches()
    session.add_watch("result")
    text = session.format_watches()
    assert "result" in text
    assert "Watches:" in text


def test_filter_events_by_type() -> None:
    session = DebugSession(log=_make_log())
    events = session.filter_events(event_type="think")
    assert len(events) == 2
    assert events[0][0] == 0
    assert events[1][0] == 4


def test_filter_events_by_agent() -> None:
    log = TraceLog(
        events=[
            ThinkEvent(content="a", agent="Bot"),
            ThinkEvent(content="b", agent="Other"),
        ]
    )
    session = DebugSession(log=log)
    events = session.filter_events(agent="Other")
    assert len(events) == 1
    assert events[0][1].agent == "Other"


def test_format_event_list() -> None:
    session = DebugSession(log=_make_log())
    events = session.filter_events(event_type="act")
    text = session.format_event_list(events)
    assert "ACT" in text
    assert "Search" in text


def test_format_event_list_empty() -> None:
    session = DebugSession(log=_make_log())
    events = session.filter_events(event_type="nonexistent")
    text = session.format_event_list(events)
    assert "no matching" in text


def test_format_range() -> None:
    session = DebugSession(log=_make_log())
    session.goto(2)
    text = session.format_range(before=1, after=1)
    assert "=> " in text
    assert "STORE" in text


def test_format_stats() -> None:
    session = DebugSession(log=_make_log())
    text = session.format_stats()
    assert "Total events: 5" in text
    assert "think" in text
    assert "act" in text
    assert "Bot" in text


def test_format_backtrace() -> None:
    session = DebugSession(log=_make_log())
    session.goto(2)
    session.goto(4)
    text = session.format_backtrace()
    assert "Backtrace:" in text
    assert "*" in text  # current position marker


def test_format_backtrace_empty() -> None:
    session = DebugSession(log=_make_log())
    text = session.format_backtrace()
    assert "(empty)" in text


def test_export_filtered() -> None:
    session = DebugSession(log=_make_log())
    text = session.export_filtered(event_type="think")
    lines = [l for l in text.split("\n") if l]
    assert len(lines) == 2
    import json
    for line in lines:
        d = json.loads(line)
        assert d["t"] == "think"


def test_export_memory() -> None:
    session = DebugSession(log=_make_log())
    session.goto(2)
    text = session.export_memory()
    import json
    d = json.loads(text)
    assert d["result"] == "found"


def test_format_summary_includes_watches() -> None:
    session = DebugSession(log=_make_log())
    session.add_watch("result")
    text = session.format_summary()
    assert "Watches: 1" in text


def test_step_backward_rebuilds_memory() -> None:
    session = DebugSession(log=_make_log())
    session.goto(2)
    assert "result" in session.memory
    session.prev()
    session.prev()
    assert "result" not in session.memory


def test_search_not_found() -> None:
    session = DebugSession(log=_make_log())
    idx = session.search("nonexistent_text_xyz")
    assert idx is None
