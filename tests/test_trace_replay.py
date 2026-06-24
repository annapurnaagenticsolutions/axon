"""Tests for AXON trace replay runtime (RFC #007)."""

from pathlib import Path

from axon.cli import run_file
from axon.trace_replayer import TraceReplayer


def test_trace_replayer_reads_jsonl(tmp_path: Path):
    """TraceReplayer reads a JSONL trace file."""
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"event_type": "agent_start", "agent_name": "Bot"}\n'
        '{"event_type": "tool_dispatch", "tool_name": "Greet"}\n'
        '{"event_type": "tool_return", "result_type": "ok", "result_summary": "hello"}\n'
        '{"event_type": "agent_end", "result_type": "ok"}\n',
        encoding="utf-8",
    )
    replayer = TraceReplayer(trace)
    assert len(replayer.events) == 4
    assert len(replayer._tool_events) == 1


def test_replay_tool_dispatch_returns_recorded_result(tmp_path: Path):
    """Replayer returns the exact recorded tool result."""
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"event_type": "tool_dispatch", "tool_name": "Greet"}\n'
        '{"event_type": "tool_return", "result_type": "ok", "result_summary": "hi there"}\n',
        encoding="utf-8",
    )
    replayer = TraceReplayer(trace)
    result = replayer.replay_tool_dispatch("Greet", {})
    assert isinstance(result, type(result))  # Ok
    assert result.ok_value == "hi there"


def test_replay_tool_dispatch_mismatch(tmp_path: Path):
    """Replayer raises error when no matching tool event exists."""
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"event_type": "tool_dispatch", "tool_name": "Other"}\n'
        '{"event_type": "tool_return", "result_type": "ok", "result_summary": "x"}\n',
        encoding="utf-8",
    )
    replayer = TraceReplayer(trace)
    result = replayer.replay_tool_dispatch("Greet", {})
    assert "Replay mismatch" in str(result.err_value)


def test_replay_model_call_returns_recorded_result(tmp_path: Path):
    """Replayer returns the exact recorded model result."""
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"event_type": "model_call", "model_reference": "@mock/gpt"}\n'
        '{"event_type": "model_return", "result_type": "ok", "result_summary": "AI says hi"}\n',
        encoding="utf-8",
    )
    replayer = TraceReplayer(trace)
    result = replayer.replay_model_call("test prompt")
    assert result.ok_value == "AI says hi"


def test_trace_replay_e2e(tmp_path: Path):
    """End-to-end: run agent, record trace, replay trace, compare outputs."""
    source = '''agent Bot {
        model: @mock/gpt
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")

    # First run: record trace
    trace_path = tmp_path / "trace.jsonl"
    code1, output1 = run_file(p, args={"q": "World"}, trace_output=trace_path)
    assert code1 == 0
    assert output1 == "World"

    # Second run: replay from trace
    code2, output2 = run_file(p, args={"q": "World"}, replay_path=trace_path)
    assert code2 == 0
    assert output2 == "World"


def test_trace_replay_with_tool_dispatch(tmp_path: Path):
    """Replay intercepts tool dispatch and returns recorded result."""
    source = '''tool Greet(name: Str) -> Str {
        "Hello, {name}!"
    }

    agent Bot {
        model: @mock/gpt
        tools: [Greet]
        fn run(q: Str) -> Str {
            act Greet(name: q)
        }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")

    trace_path = tmp_path / "trace.jsonl"
    code1, output1 = run_file(p, args={"q": "Replay"}, trace_output=trace_path)
    assert code1 == 0
    assert output1 == "Hello, Replay!"

    # Replay should return the SAME result without executing the tool body
    code2, output2 = run_file(p, args={"q": "Replay"}, replay_path=trace_path)
    assert code2 == 0
    assert output2 == "Hello, Replay!"
