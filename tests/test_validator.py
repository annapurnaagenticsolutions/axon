from axon.parser import parse
from axon.validator import AxonValidationError, has_errors, validate, validate_or_raise


VALID_SOURCE = '''
import { Chunk } from "axon:types"

rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")

    fn retrieve(query: Str) -> List<Chunk> { Ok([]) }
}

prompt GreetPrompt(name: Str, @budget(tokens: 100)) -> Str {
    """
    Write a greeting for {name}.
    """
}

tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Greet, Docs.retrieve]

    fn run(q: Str) -> Str { q }
}
'''


def _codes(source: str) -> list[str]:
    return [d.code for d in validate(parse(source))]


def test_valid_project_has_no_diagnostics():
    diagnostics = validate(parse(VALID_SOURCE), enable_type_check=False)
    assert diagnostics == []
    assert not has_errors(diagnostics)


def test_missing_tool_docstring_is_error():
    source = '''
tool T(x: Str) -> Str { x }
agent A { model: @anthropic/claude-4 tools: [T] fn run(q: Str) -> Str { q } }
'''
    diagnostics = validate(parse(source))
    assert any(d.code == "missing-tool-docstring" and d.severity == "error" for d in diagnostics)


def test_unknown_agent_tool_is_error():
    source = '''
agent A {
    model: @anthropic/claude-4
    tools: [MissingTool]
    fn run(q: Str) -> Str { q }
}
'''
    diagnostics = validate(parse(source))
    assert any(d.code == "unknown-agent-tool" for d in diagnostics)


def test_imported_tool_reference_is_allowed():
    source = '''
import { WebSearch } from "axon:tools/web"
agent A {
    model: @anthropic/claude-4
    tools: [WebSearch]
    fn run(q: Str) -> Str { q }
}
'''
    assert "unknown-agent-tool" not in _codes(source)


def test_rag_method_tool_reference_is_allowed():
    source = '''
rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")
    fn retrieve(query: Str) -> List<Chunk> { Ok([]) }
}
agent A {
    model: @anthropic/claude-4
    tools: [Docs.retrieve]
    fn run(q: Str) -> Str { q }
}
'''
    assert "unknown-agent-tool" not in _codes(source)


def test_duplicate_top_level_declarations_are_errors():
    source = '''
tool Same(x: Str) -> Str { /// D. x }
agent Same { model: @anthropic/claude-4 tools: [Same] fn run(q: Str) -> Str { q } }
'''
    diagnostics = validate(parse(source))
    assert any(d.code == "duplicate-declaration" for d in diagnostics)


def test_duplicate_agent_methods_are_errors():
    source = '''
tool T(x: Str) -> Str { /// D. x }
agent A {
    model: @anthropic/claude-4
    tools: [T]
    fn run(q: Str) -> Str { q }
    fn run(x: Int) -> Int { x }
}
'''
    assert "duplicate-agent-method" in _codes(source)


def test_agent_without_methods_is_error():
    source = '''
tool T(x: Str) -> Str { /// D. x }
agent A {
    model: @anthropic/claude-4
    tools: [T]
}
'''
    assert "missing-agent-method" in _codes(source)


def test_prompt_unknown_template_variable_is_error():
    source = '''
prompt P(name: Str, @budget(tokens: 50)) -> Str {
    """
    Hello {missing}.
    """
}
'''
    assert "unknown-prompt-variable" in _codes(source)


def test_prompt_invalid_budget_is_error():
    source = '''
prompt P(name: Str, @budget(tokens: zero)) -> Str {
    """
    Hello {name}.
    """
}
'''
    assert "invalid-budget-tokens" in _codes(source)


def test_duplicate_flow_stage_is_error():
    source = '''
flow F(q: Str) -> Str {
    stage A(q: Str) -> Str
    stage A(q: Str) -> Str
    A -> A
}
'''
    assert "duplicate-flow-stage" in _codes(source)


def test_unknown_flow_stage_is_warning():
    source = '''
flow F(q: Str) -> Str {
    stage A(q: Str) -> Str
    A -> Missing
}
'''
    diagnostics = validate(parse(source))
    assert any(d.code == "unknown-flow-stage" and d.severity == "warning" for d in diagnostics)


def test_validate_or_raise_raises_on_errors():
    source = '''
agent A {
    model: @anthropic/claude-4
    tools: [Missing]
    fn run(q: Str) -> Str { q }
}
'''
    try:
        validate_or_raise(parse(source))
    except AxonValidationError as exc:
        assert any(d.code == "unknown-agent-tool" for d in exc.diagnostics)
    else:
        raise AssertionError("expected AxonValidationError")


def test_validate_or_raise_can_treat_warnings_as_errors():
    source = '''
flow F(q: Str) -> Str {
    stage A(q: Str) -> Str
    A -> Missing
}
'''
    diagnostics = validate(parse(source))
    assert not has_errors(diagnostics)
    try:
        validate_or_raise(parse(source), warnings_as_errors=True)
    except AxonValidationError as exc:
        assert any(d.code == "unknown-flow-stage" for d in exc.diagnostics)
    else:
        raise AssertionError("expected AxonValidationError")
