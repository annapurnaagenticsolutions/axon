from pathlib import Path

from axon.golden_errors import (
    check_error_snapshot_file,
    error_snapshot,
    snapshot_to_json,
    source_to_snapshot_json,
    syntax_error_snapshot,
    validation_error_snapshot,
)

GOLDEN_DIR = Path(__file__).parent / "golden_errors"

CASES = {
    "syntax_missing_arrow": (
        "syntax",
        '''
tool Bad(name: Str) Str {
    /// Missing arrow.
    "Hello"
}
''',
    ),
    "syntax_agent_typo": (
        "syntax",
        '''
agnt Bot {
    model: @anthropic/claude-4
}
''',
    ),
    "syntax_unclosed_tool_body": (
        "syntax",
        '''
tool Bad(name: Str) -> Str {
    /// Says hello.
    "Hello"
''',
    ),
    "validation_missing_tool_docstring": (
        "validation",
        '''
tool T(x: Str) -> Str { x }
agent A {
    model: @anthropic/claude-4
    tools: [T]
    fn run(q: Str) -> Str { q }
}
''',
    ),
    "validation_unknown_agent_tool": (
        "validation",
        '''
agent A {
    model: @anthropic/claude-4
    tools: [MissingTool]
    fn run(q: Str) -> Str { q }
}
''',
    ),
    "validation_prompt_unknown_variable": (
        "validation",
        '''
prompt P(name: Str, @budget(tokens: 50)) -> Str {
    """
    Hello {missing}.
    """
}
''',
    ),
    "validation_flow_unknown_stage_warning": (
        "validation",
        '''
flow F(q: Str) -> Str {
    stage A(q: Str) -> Str
    A -> Missing
}
''',
    ),
}


def test_syntax_error_snapshot_shape():
    snapshot = syntax_error_snapshot('agnt Bot {}', filename="case.ax")
    assert snapshot["kind"] == "syntax"
    assert snapshot["ok"] is False
    assert snapshot["diagnostics"][0]["severity"] == "error"
    assert snapshot["diagnostics"][0]["hint"] == "Did you mean `agent`?"


def test_validation_error_snapshot_shape():
    snapshot = validation_error_snapshot('tool T(x: Str) -> Str { x }')
    assert snapshot["kind"] == "validation"
    assert snapshot["ok"] is False
    assert snapshot["diagnostics"][0]["code"] == "missing-tool-docstring"


def test_snapshot_json_is_deterministic_and_ends_with_newline():
    snapshot = error_snapshot('agnt Bot {}', mode="syntax", filename="case.ax")
    first = snapshot_to_json(snapshot)
    second = snapshot_to_json(snapshot)
    assert first == second
    assert first.endswith("\n")
    assert '"kind": "syntax"' in first


def test_source_to_snapshot_json_dispatches_modes():
    syntax_json = source_to_snapshot_json('agnt Bot {}', mode="syntax", filename="case.ax")
    validation_json = source_to_snapshot_json('tool T(x: Str) -> Str { x }', mode="validation")
    assert '"kind": "syntax"' in syntax_json
    assert '"kind": "validation"' in validation_json


def test_all_golden_error_snapshots_match_checked_in_files():
    for name, (mode, source) in CASES.items():
        result = check_error_snapshot_file(
            source,
            GOLDEN_DIR / f"{name}.json",
            mode=mode,
            filename=f"{name}.ax",
        )
        assert result.matched, result.format()


def test_golden_snapshot_mismatch_reports_expected_and_actual(tmp_path: Path):
    bad_snapshot = tmp_path / "bad.json"
    bad_snapshot.write_text('{"not":"the expected snapshot"}\n', encoding="utf-8")
    result = check_error_snapshot_file(
        'agnt Bot {}',
        bad_snapshot,
        mode="syntax",
        filename="case.ax",
    )
    assert result.matched is False
    formatted = result.format()
    assert "differs" in formatted
    assert "--- expected ---" in formatted
    assert "--- actual ---" in formatted
