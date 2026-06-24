import sys

from axon.codegen.mcp import generate_mcp_server
from axon.parser import parse
from axon.smoke import (
    report_to_json,
    smoke_test_declarations,
    smoke_test_generated_code,
    smoke_test_or_raise,
)


SIMPLE_SOURCE = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}
agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]
    memory: Memory<ShortTerm>(capacity: 100)
    fn run(q: Str) -> Str { q }
}
'''


def test_smoke_generated_code_passes_without_fastmcp_installed(monkeypatch):
    # The smoke harness injects its own fake fastmcp module and restores any
    # previous module afterwards.
    previous = sys.modules.pop("fastmcp", None)
    try:
        code = generate_mcp_server(parse(SIMPLE_SOURCE))
        report = smoke_test_generated_code(code, expected_tools=["greet"])
    finally:
        if previous is not None:
            sys.modules["fastmcp"] = previous

    assert report.passed is True
    assert report.server_name == "Bot"
    assert report.registered_tools == ["greet"]
    assert report.metadata["AXON_AGENT_MODEL"] == "@anthropic/claude-4"
    assert report.metadata["AXON_AGENT_MEMORY"] == "ShortTerm"


def test_smoke_declarations_derives_expected_tool_names():
    report = smoke_test_declarations(parse(SIMPLE_SOURCE))

    assert report.passed is True
    assert "greet" in report.registered_tools


def test_smoke_reports_generated_python_syntax_error():
    report = smoke_test_generated_code("def broken(:\n", expected_tools=[])

    assert report.passed is False
    assert report.diagnostics[0].code == "generated-python-syntax-error"


def test_smoke_reports_missing_expected_registered_tool():
    code = generate_mcp_server(parse(SIMPLE_SOURCE))
    report = smoke_test_generated_code(code, expected_tools=["missing_tool"])

    assert report.passed is False
    assert any(d.code == "missing-generated-function" for d in report.diagnostics)
    assert any(d.code == "missing-registered-tool" for d in report.diagnostics)


def test_smoke_does_not_call_mcp_run_during_load():
    code = generate_mcp_server(parse(SIMPLE_SOURCE))
    report = smoke_test_generated_code(code, expected_tools=["greet"])

    assert report.passed is True
    assert not any(d.code == "run-called-during-load" for d in report.diagnostics)


def test_smoke_or_raise_allows_passing_report():
    report = smoke_test_declarations(parse(SIMPLE_SOURCE))

    smoke_test_or_raise(report)


def test_report_to_json_contains_registered_tools():
    report = smoke_test_declarations(parse(SIMPLE_SOURCE))
    payload = report_to_json(report)

    assert '"passed": true' in payload
    assert '"registered_tools": [' in payload
    assert '"greet"' in payload
