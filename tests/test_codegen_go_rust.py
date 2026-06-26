"""Tests for AXON Go and Rust code generators."""

from axon.ast_nodes import AgentDecl, Annotation, MemoryDecl, MethodDecl, Param, ToolDecl, TypeAliasDecl
from axon.codegen.go import generate_go, _axon_type_to_go
from axon.codegen.rust import generate_rust, _axon_type_to_rust


def _sample_decls():
    return [
        TypeAliasDecl(
            name="Issue",
            type_params=[],
            value="{ id: Int, title: Str }",
            fields=[
                Param(name="id", type_str="Int"),
                Param(name="title", type_str="Str"),
            ],
            line=0,
        ),
        ToolDecl(
            name="FetchIssues",
            params=[Param(name="repo", type_str="Str")],
            return_type="List<Issue>",
            docstrings=["Fetch issues from a repo"],
            body='[Issue(id: 1, title: "test")]',
            annotations=[],
            line=0,
        ),
        AgentDecl(
            name="IssueBot",
            model="@anthropic/claude-4",
            tools=["FetchIssues"],
            memory=None,
            annotations=[],
            methods=[
                MethodDecl(
                    name="run",
                    params=[Param(name="q", type_str="Str")],
                    return_type="Result<Str, AgentError>",
                    annotations=[],
                    body="Ok(q)",
                )
            ],
            version="1.2.0",
            line=0,
        ),
    ]


# ── Go tests ──────────────────────────────────────────────────────────────────

def test_go_type_mapping():
    assert _axon_type_to_go("Str") == "string"
    assert _axon_type_to_go("Int") == "int64"
    assert _axon_type_to_go("Float") == "float64"
    assert _axon_type_to_go("Bool") == "bool"
    assert _axon_type_to_go("List<Str>") == "[]string"
    assert _axon_type_to_go("Map<Str, Int>") == "map[string]int64"
    assert _axon_type_to_go("Option<Str>") == "*string"
    assert _axon_type_to_go("Result<Str, AgentError>") == "Result[string, AgentError]"


def test_generate_go_basic():
    decls = _sample_decls()
    code = generate_go(decls, output_name="test_app")
    assert "package test_app" in code
    assert "type Issue struct" in code
    assert "func FetchIssues" in code
    assert "type IssueBot struct" in code
    assert "func NewIssueBot" in code
    assert "claude-4" in code
    assert "1.2.0" in code


def test_generate_go_tool_stub():
    decls = _sample_decls()
    code = generate_go(decls)
    assert "TODO: implement FetchIssues" in code
    assert "not implemented" in code


def test_generate_go_agent_method():
    decls = _sample_decls()
    code = generate_go(decls)
    assert "func (a *IssueBot) Run" in code


# ── Rust tests ────────────────────────────────────────────────────────────────

def test_rust_type_mapping():
    assert _axon_type_to_rust("Str") == "String"
    assert _axon_type_to_rust("Int") == "i64"
    assert _axon_type_to_rust("Float") == "f64"
    assert _axon_type_to_rust("Bool") == "bool"
    assert _axon_type_to_rust("List<Str>") == "Vec<String>"
    assert _axon_type_to_rust("Map<Str, Int>") == "HashMap<String, i64>"
    assert _axon_type_to_rust("Option<Str>") == "Option<String>"
    assert _axon_type_to_rust("Result<Str, AgentError>") == "Result<String, AgentError>"


def test_generate_rust_basic():
    decls = _sample_decls()
    code = generate_rust(decls, output_name="test_app")
    assert "pub mod test_app" in code
    assert "pub struct Issue" in code
    assert "pub fn fetch_issues" in code
    assert "pub struct IssueBot" in code
    assert "impl IssueBot" in code
    assert "claude-4" in code
    assert "1.2.0" in code


def test_generate_rust_tool_stub():
    decls = _sample_decls()
    code = generate_rust(decls)
    assert "TODO: implement FetchIssues" in code
    assert "not implemented" in code


def test_generate_rust_agent_method():
    decls = _sample_decls()
    code = generate_rust(decls)
    assert "pub fn run" in code
    assert "TODO: implement run" in code


def test_generate_rust_type_alias_simple():
    decls = [
        TypeAliasDecl(name="IssueId", type_params=[], value="Int", fields=[], line=0),
    ]
    code = generate_rust(decls)
    assert "pub type IssueId = i64;" in code


def test_generate_go_type_alias_simple():
    decls = [
        TypeAliasDecl(name="IssueId", type_params=[], value="Int", fields=[], line=0),
    ]
    code = generate_go(decls)
    assert "type IssueId = int64" in code
