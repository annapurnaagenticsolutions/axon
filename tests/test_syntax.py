import json
from pathlib import Path

from axon.syntax import check_syntax, check_syntax_file, diagnostic_from_syntax_error


def test_check_syntax_ok_returns_declarations():
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello"
}
'''
    result = check_syntax(source, filename="ok.ax")
    assert result.ok is True
    assert len(result.declarations) == 1
    assert result.diagnostics == []
    assert "parsed 1 declaration" in result.format()


def test_missing_arrow_diagnostic_has_snippet_pointer_and_hint():
    source = '''
tool Bad(name: Str) Str {
    /// Missing arrow.
    "Hello"
}
'''
    result = check_syntax(source, filename="bad.ax")
    assert result.ok is False
    diagnostic = result.diagnostics[0]
    assert diagnostic.filename == "bad.ax"
    assert diagnostic.line == 2
    assert diagnostic.column >= 1
    assert "Expected '->'" in diagnostic.message
    assert "tool Bad" in diagnostic.snippet
    assert "^" in diagnostic.pointer
    assert "-> ReturnType" in diagnostic.hint
    assert "bad.ax:2:" in diagnostic.format()


def test_unexpected_token_typo_hint():
    source = '''
agnt Bot {
    model: @anthropic/claude-4
}
'''
    result = check_syntax(source)
    assert not result.ok
    assert result.diagnostics[0].line == 2
    assert result.diagnostics[0].hint == "Did you mean `agent`?"


def test_unclosed_body_hint():
    source = '''
tool Bad(name: Str) -> Str {
    /// Says hello.
    "Hello"
'''
    result = check_syntax(source)
    assert not result.ok
    assert "Unclosed" in result.diagnostics[0].message
    assert "missing closing delimiter" in result.diagnostics[0].hint


def test_syntax_result_json_is_stable():
    source = 'tool Bad(name: Str) Str { "Hello" }'
    result = check_syntax(source, filename="bad.ax")
    payload = json.loads(result.to_json())
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["severity"] == "error"
    assert payload["diagnostics"][0]["filename"] == "bad.ax"


def test_check_syntax_file(tmp_path: Path):
    path = tmp_path / "hello.ax"
    path.write_text('tool T(x: Str) -> Str { /// D. x }', encoding="utf-8")
    result = check_syntax_file(path)
    assert result.ok
    assert len(result.declarations) == 1
