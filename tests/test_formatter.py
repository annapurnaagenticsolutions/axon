from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from axon.formatter import (
    check_format_source,
    format_file,
    format_param,
    format_source,
    write_formatted_file,
)
from axon.parser import parse

ROOT = Path(__file__).resolve().parents[1]


def test_format_param_with_default():
    assert format_param(parse('tool T(x: Int = 5) -> Int { /// D\nx }')[0].params[0]) == "x: Int = 5"


def test_format_simple_tool_canonicalizes_spacing():
    source = 'tool Greet( name: Str )-> Str {\n/// Says hello.\n"Hello, {name}!"\n}'
    formatted = format_source(source)
    assert formatted == '''tool Greet(name: Str) -> Str {
    /// Says hello.

    "Hello, {name}!"
}
'''
    # The formatter output should remain parseable.
    assert parse(formatted)[0].name == "Greet"


def test_format_agent_with_method_and_memory():
    source = '''
agent Bot {
model: @anthropic/claude-4
tools: [Search]
memory: Memory<ShortTerm>(capacity: 500)
@schedule(every: 5.minutes)
fn run(q: Str) -> Result<Str, AgentError> { Ok(q) }
}
'''
    formatted = format_source(source)
    assert "agent Bot {" in formatted
    assert "    model: @anthropic/claude-4" in formatted
    assert "    tools: [Search]" in formatted
    assert "    memory: Memory<ShortTerm>(capacity: 500)" in formatted
    assert "    @schedule(every: 5.minutes)" in formatted
    assert "    fn run(q: Str) -> Result<Str, AgentError> {" in formatted
    assert "        Ok(q)" in formatted


def test_format_type_alias_record():
    source = 'type Issue = { id: Int, title: Str, labels: List<Str> }'
    assert format_source(source) == '''type Issue = {
    id: Int,
    title: Str,
    labels: List<Str>,
}
'''


def test_format_prompt_with_budget_annotation():
    source = '''
prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {
"""
Summarize:
{text}
"""
}
'''
    formatted = format_source(source)
    assert "prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {" in formatted
    assert '    """' in formatted
    assert "    Summarize:" in formatted
    assert "    {text}" in formatted


def test_format_rag_and_flow_examples_are_parseable():
    for rel in ["examples/rag.ax", "examples/flow.ax"]:
        formatted = format_file(ROOT / rel)
        assert formatted.endswith("\n")
        assert parse(formatted)


def test_check_format_source_detects_unformatted_and_formatted():
    source = 'tool T(x:Str)->Str{/// D\nx}'
    result = check_format_source(source)
    assert not result.formatted
    assert "not formatted" in result.message

    second = check_format_source(result.formatted_source)
    assert second.formatted
    assert "already formatted" in second.message


def test_write_formatted_file(tmp_path: Path):
    path = tmp_path / "demo.ax"
    path.write_text('tool T(x:Str)->Str{/// D\nx}', encoding="utf-8")
    written = write_formatted_file(path)
    assert written == path
    assert path.read_text(encoding="utf-8") == format_source(path.read_text(encoding="utf-8"))


def test_cli_format_stdout_and_check(tmp_path: Path):
    path = tmp_path / "demo.ax"
    path.write_text('tool T(x:Str)->Str{/// D\nx}', encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    stdout = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(path)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert stdout.returncode == 0
    assert "tool T(x: Str) -> Str" in stdout.stdout

    check = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(path), "--check"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 1
    assert "not formatted" in check.stdout

    write = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(path), "--write"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert "Formatted AXON source" in write.stdout

    check_after = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(path), "--check"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check_after.returncode == 0
    assert "already formatted" in check_after.stdout


def test_cli_format_rejects_check_and_write_together(tmp_path: Path):
    path = tmp_path / "demo.ax"
    path.write_text('tool T(x: Str) -> Str { /// D\nx }', encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "format", str(path), "--check", "--write"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "choose only one" in completed.stderr
