"""Tests for AXON flow execution engine (RFC #005)."""

from pathlib import Path

from axon.cli import run_file


def test_linear_flow_execution(tmp_path: Path):
    """Test a simple linear flow: A -> B."""
    source = '''flow Pipeline(name: Str) -> Str {
        stage Echo(text: Str) -> Str
        stage Shout(msg: Str) -> Str
        Echo -> Shout
    }

    tool Echo(text: Str) -> Str {
        "echo: " + text
    }

    tool Shout(msg: Str) -> Str {
        "shout: " + msg
    }
    '''
    p = tmp_path / "flow.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, args={"name": "world"}, flow_name="Pipeline")
    assert code == 0
    assert output == "shout: echo: world"


def test_parallel_branch_flow_execution(tmp_path: Path):
    """Test a parallel-branch flow: [A, B] -> C."""
    source = '''flow MergeFlow(topic: Str) -> Str {
        stage Pro(query: Str) -> Str
        stage Con(query: Str) -> Str
        stage Synthesize(results: List<Str>) -> Str
        [Pro, Con] -> Synthesize
    }

    tool Pro(query: Str) -> Str {
        "pro: " + query
    }

    tool Con(query: Str) -> Str {
        "con: " + query
    }

    tool Synthesize(results: List<Str>) -> Str {
        results[0] + " | " + results[1]
    }
    '''
    p = tmp_path / "flow.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, args={"topic": "AI"}, flow_name="MergeFlow")
    assert code == 0
    assert "pro: AI" in output
    assert "con: AI" in output


def test_flow_trace_events(tmp_path: Path):
    """Test that flow execution emits correct trace events."""
    source = '''flow TracedFlow(x: Str) -> Str {
        stage Upper(text: Str) -> Str
        stage Greet(msg: Str) -> Str
        Upper -> Greet
    }

    tool Upper(text: Str) -> Str {
        text
    }

    tool Greet(msg: Str) -> Str {
        "hello " + msg
    }
    '''
    p = tmp_path / "flow.ax"
    p.write_text(source, encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"

    code, output = run_file(
        p, args={"x": "hi"}, flow_name="TracedFlow", trace_output=trace_path
    )
    assert code == 0
    assert trace_path.exists()

    import json
    events = [json.loads(line) for line in trace_path.read_text().strip().split("\n")]
    event_types = [e["event_type"] for e in events]

    assert "flow_start" in event_types
    assert "stage_start" in event_types
    assert "stage_end" in event_types
    assert "flow_end" in event_types


def test_flow_not_found(tmp_path: Path):
    """Test error when flow name does not exist."""
    source = '''flow RealFlow(x: Str) -> Str {
        stage A(text: Str) -> Str
        A -> A
    }
    '''
    p = tmp_path / "flow.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, args={"x": "hi"}, flow_name="MissingFlow")
    assert code == 1
    assert "not found" in output.lower()


def test_stage_not_found(tmp_path: Path):
    """Test error when a stage has no matching tool or agent."""
    source = '''flow BadFlow(x: Str) -> Str {
        stage A(text: Str) -> Str
        stage MissingTool(msg: Str) -> Str
        A -> MissingTool
    }

    tool A(text: Str) -> Str {
        text
    }
    '''
    p = tmp_path / "flow.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, args={"x": "hi"}, flow_name="BadFlow")
    assert code == 1
    assert "not found" in output.lower() or "dispatch failed" in output.lower()
