import json
from pathlib import Path

from axon.ast_nodes import AgentDecl, ToolDecl
from axon.ast_snapshot import (
    check_snapshot_file,
    declaration_to_dict,
    declarations_to_json,
    source_file_to_snapshot_json,
    source_to_snapshot_json,
    write_snapshot_file,
)
from axon.cli import main
from axon.parser import parse


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SNAPSHOTS = ROOT / "tests" / "snapshots"


def test_declaration_to_dict_includes_node_and_fields():
    decls = parse('''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello"
}
''')

    snapshot = declaration_to_dict(decls[0])

    assert snapshot["node"] == "ToolDecl"
    assert snapshot["name"] == "Greet"
    assert snapshot["params"][0]["node"] == "Param"
    assert snapshot["params"][0]["name"] == "name"
    assert snapshot["docstrings"] == ["Says hello."]
    assert snapshot["line"] == 2


def test_declaration_to_dict_can_omit_line_numbers():
    decls = parse('''
agent Bot {
    model: @anthropic/claude-4
    tools: []
    fn run() -> Str { "ok" }
}
''')

    snapshot = declaration_to_dict(decls[0], include_lines=False)

    assert snapshot["node"] == "AgentDecl"
    assert "line" not in snapshot


def test_declarations_to_json_is_stable_pretty_json():
    decls = parse('''
tool T(x: Str) -> Str { /// D. x }
''')

    text = declarations_to_json(decls)
    parsed = json.loads(text)

    assert text.endswith("\n")
    assert parsed[0]["node"] == "ToolDecl"
    assert parsed[0]["name"] == "T"


def test_source_to_snapshot_json_parses_mixed_source():
    source = '''
import { Search } from "axon:tools/web"
type Priority = "low" | "high"
prompt P(name: Str, @budget(tokens: 50)) -> Str {
    """
    Hi {name}
    """
}
tool T(x: Str) -> Str { /// D. x }
agent A {
    model: @anthropic/claude-4
    tools: [T, Search]
    fn run(q: Str) -> Str { q }
}
'''

    snapshot = json.loads(source_to_snapshot_json(source))

    assert [node["node"] for node in snapshot] == [
        "ImportDecl",
        "TypeAliasDecl",
        "PromptDecl",
        "ToolDecl",
        "AgentDecl",
    ]


def test_example_snapshots_match_checked_in_files():
    for name in ["hello", "prompts", "rag", "flow"]:
        result = check_snapshot_file(EXAMPLES / f"{name}.ax", SNAPSHOTS / f"{name}.ast.json")
        assert result.matched, result.message


def test_write_snapshot_file_creates_parent_dirs(tmp_path):
    destination = tmp_path / "snapshots" / "hello.ast.json"

    written = write_snapshot_file(EXAMPLES / "hello.ax", destination)

    assert written == destination
    assert destination.exists()
    assert json.loads(destination.read_text(encoding="utf-8"))[0]["node"] == "ToolDecl"


def test_check_snapshot_file_detects_mismatch(tmp_path):
    bad = tmp_path / "bad.ast.json"
    bad.write_text("[]\n", encoding="utf-8")

    result = check_snapshot_file(EXAMPLES / "hello.ax", bad)

    assert not result.matched
    assert "AST snapshot mismatch" in result.message


def test_source_file_to_snapshot_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.ax"

    try:
        source_file_to_snapshot_json(missing)
    except FileNotFoundError as exc:
        assert "source file not found" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_main_ast_prints_json(capsys):
    exit_code = main(["ast", str(EXAMPLES / "hello.ax")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"node": "ToolDecl"' in captured.out
    assert '"node": "AgentDecl"' in captured.out


def test_main_ast_no_lines_omits_line_numbers(capsys):
    exit_code = main(["ast", str(EXAMPLES / "hello.ax"), "--no-lines"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"line"' not in captured.out


def test_main_ast_write_and_check(tmp_path, capsys):
    snapshot = tmp_path / "hello.ast.json"

    write_code = main(["ast", str(EXAMPLES / "hello.ax"), "--write", str(snapshot)])
    write_out = capsys.readouterr()
    check_code = main(["ast", str(EXAMPLES / "hello.ax"), "--check", str(snapshot)])
    check_out = capsys.readouterr()

    assert write_code == 0
    assert "Wrote AST snapshot" in write_out.out
    assert check_code == 0
    assert "OK: AST snapshot matches" in check_out.out


def test_main_ast_check_mismatch_returns_nonzero(tmp_path, capsys):
    snapshot = tmp_path / "bad.ast.json"
    snapshot.write_text("[]\n", encoding="utf-8")

    exit_code = main(["ast", str(EXAMPLES / "hello.ax"), "--check", str(snapshot)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "AST snapshot mismatch" in captured.out


def test_main_ast_rejects_write_and_check_together(tmp_path, capsys):
    snapshot = tmp_path / "x.ast.json"

    exit_code = main([
        "ast",
        str(EXAMPLES / "hello.ax"),
        "--write",
        str(snapshot),
        "--check",
        str(snapshot),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "choose only one" in captured.err
