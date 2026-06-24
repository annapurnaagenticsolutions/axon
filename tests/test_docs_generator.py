"""Tests for AXON documentation generator."""

from axon.parser import parse
from axon.docs_generator import (
    generate_docs,
    DocumentationSection,
)


def test_generate_docs_empty():
    source = ""
    docs = generate_docs(source)
    assert docs == ""


def test_generate_docs_with_tool():
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}
'''
    docs = generate_docs(source)
    assert "## Tools" in docs
    assert "Greet" in docs
    assert "Says hello to someone" in docs
    assert "Greet(name: Str) -> Str" in docs


def test_generate_docs_with_agent():
    source = '''
agent Bot {
    model: @anthropic/claude-4
    tools: []

    fn run(query: Str) -> Str {
        Ok(query)
    }
}
'''
    docs = generate_docs(source)
    assert "## Agents" in docs
    assert "Bot" in docs
    assert "@anthropic/claude-4" in docs
    assert "run(query: Str) -> Str" in docs


def test_generate_docs_with_prompt():
    source = '''
prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {
    """
    Summarize the text: {text}
    """
}
'''
    docs = generate_docs(source)
    assert "## Prompts" in docs
    assert "Summarize" in docs
    assert "Summarize the text:" in docs
    assert "@budget" in docs


def test_generate_docs_with_type_alias():
    source = '''
type IssueId = Int
type Priority = "low" | "medium" | "high"
'''
    docs = generate_docs(source)
    assert "## Type Aliases" in docs
    assert "IssueId" in docs
    assert "Priority" in docs


def test_generate_docs_with_record_type():
    source = '''
type Issue = {
    id: Int,
    title: Str,
    labels: List<Str>
}
'''
    docs = generate_docs(source)
    assert "## Type Aliases" in docs
    assert "Issue" in docs
    assert "id: Int" in docs
    assert "title: Str" in docs
    assert "labels: List<Str>" in docs


def test_generate_docs_multiple_sections():
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @anthropic/claude-4
    tools: []
    fn run(q: Str) -> Str { q }
}

type Status = "active" | "inactive"
'''
    docs = generate_docs(source)
    assert "## Tools" in docs
    assert "## Agents" in docs
    assert "## Type Aliases" in docs
    assert "Greet" in docs
    assert "Bot" in docs
    assert "Status" in docs


def test_generate_docs_with_source_path():
    source = '''
tool Test() -> Str {
    /// Test tool.
    "test"
}
'''
    docs = generate_docs(source, source_path="test_file.ax")
    assert "# Test File" in docs
    assert "## Tools" in docs


def test_documentation_section():
    section = DocumentationSection("Test", "Content", level=3)
    assert section.title == "Test"
    assert section.content == "Content"
    assert section.level == 3
