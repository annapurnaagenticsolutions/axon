"""Tests for AXON agent lifecycle manager."""

from pathlib import Path

from result import Ok, Err

from axon.agent_lifecycle import AgentLifecycleManager, AgentStatus


def test_spawn_and_status(tmp_path: Path) -> None:
    # Create a minimal .ax source
    source = tmp_path / "test_agent.ax"
    source.write_text(
        'agent TestBot {\n'
        '    model: @mock/gpt\n'
        '    tools: []\n'
        '    fn run(q: Str) -> Str { q }\n'
        '}\n',
        encoding="utf-8",
    )

    mgr = AgentLifecycleManager()
    result = mgr.spawn(source, name="bot-1", args={"q": "hello"}, mock=True)
    assert isinstance(result, Ok)
    assert result.ok_value

    status_result = mgr.status("bot-1")
    assert isinstance(status_result, Ok)
    inst = status_result.ok_value
    assert inst.name == "bot-1"
    assert inst.status in (AgentStatus.IDLE, AgentStatus.RUNNING, AgentStatus.TERMINATED)


def test_pause_resume_terminate(tmp_path: Path) -> None:
    source = tmp_path / "test_agent.ax"
    source.write_text(
        'agent TestBot {\n'
        '    model: @mock/gpt\n'
        '    tools: []\n'
        '    fn run(q: Str) -> Str { q }\n'
        '}\n',
        encoding="utf-8",
    )

    mgr = AgentLifecycleManager()
    mgr.spawn(source, name="bot-2", args={"q": "hello"}, mock=True)

    # Pause
    pause_res = mgr.pause("bot-2")
    assert isinstance(pause_res, Ok)
    status = mgr.status("bot-2").ok_value
    assert status.status == AgentStatus.PAUSED

    # Resume
    resume_res = mgr.resume("bot-2")
    assert isinstance(resume_res, Ok)
    status = mgr.status("bot-2").ok_value
    assert status.status == AgentStatus.RUNNING

    # Terminate
    terminate_res = mgr.terminate("bot-2")
    assert isinstance(terminate_res, Ok)
    status = mgr.status("bot-2").ok_value
    assert status.status == AgentStatus.TERMINATED


def test_terminate_unknown_agent() -> None:
    mgr = AgentLifecycleManager()
    result = mgr.terminate("nonexistent")
    assert isinstance(result, Err)
    assert "not found" in result.err_value.lower()


def test_list_agents(tmp_path: Path) -> None:
    source = tmp_path / "test_agent.ax"
    source.write_text(
        'agent TestBot {\n'
        '    model: @mock/gpt\n'
        '    tools: []\n'
        '    fn run(q: Str) -> Str { q }\n'
        '}\n',
        encoding="utf-8",
    )

    mgr = AgentLifecycleManager()
    mgr.spawn(source, name="bot-a", args={"q": "hello"}, mock=True)
    mgr.spawn(source, name="bot-b", args={"q": "world"}, mock=True)

    agents = mgr.list_agents()
    names = {a.name for a in agents}
    assert "bot-a" in names
    assert "bot-b" in names

    mgr.terminate("bot-a")
    agents_after = mgr.list_agents()
    names_after = {a.name for a in agents_after}
    assert "bot-a" not in names_after
    assert "bot-b" in names_after


def test_duplicate_spawn_rejected(tmp_path: Path) -> None:
    source = tmp_path / "test_agent.ax"
    source.write_text(
        'agent TestBot {\n'
        '    model: @mock/gpt\n'
        '    tools: []\n'
        '    fn run(q: Str) -> Str { q }\n'
        '}\n',
        encoding="utf-8",
    )

    mgr = AgentLifecycleManager()
    mgr.spawn(source, name="bot-c", args={"q": "hello"}, mock=True)
    result = mgr.spawn(source, name="bot-c", args={"q": "world"}, mock=True)
    assert isinstance(result, Err)
    assert "already exists" in result.err_value


def test_trace_events_emitted(tmp_path: Path) -> None:
    source = tmp_path / "test_agent.ax"
    source.write_text(
        'agent TestBot {\n'
        '    model: @mock/gpt\n'
        '    tools: []\n'
        '    fn run(q: Str) -> Str { q }\n'
        '}\n',
        encoding="utf-8",
    )

    mgr = AgentLifecycleManager()
    result = mgr.spawn(source, name="bot-d", args={"q": "hello"}, mock=True)
    assert isinstance(result, Ok)

    inst = mgr.status("bot-d").ok_value
    assert inst.trace_emitter is not None
    events = inst.trace_emitter.events
    event_types = [e["event_type"] for e in events]
    assert "agent_start" in event_types

    mgr.pause("bot-d")
    events = inst.trace_emitter.events
    event_types = [e["event_type"] for e in events]
    assert "agent_pause" in event_types

    mgr.resume("bot-d")
    events = inst.trace_emitter.events
    event_types = [e["event_type"] for e in events]
    assert "agent_resume" in event_types

    mgr.terminate("bot-d")
    events = inst.trace_emitter.events
    event_types = [e["event_type"] for e in events]
    assert "agent_terminate" in event_types
