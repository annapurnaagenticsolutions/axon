"""Tests for the AXON TypeScript code generator."""

from __future__ import annotations

from axon.codegen.typescript import generate_typescript, _axon_type_to_ts
from axon.parser import parse


SIMPLE_AGENT = """
agent Bot {
    model: @mock/model
    tools: []

    fn run(query: Str) -> Str {
        "Hello, " + query
    }
}
"""

AGENT_WITH_TOOL = """
tool Search(query: Str) -> Result<List<Str>, Error> {
    /// Search for items.
}

agent ResearchBot {
    model: @anthropic/claude-4
    tools: [Search]

    fn search(query: Str) -> Result<List<Str>, Error> {
        act Search(query: query)
    }
}
"""

FLOW_DECL = """
flow Pipeline(input: Str) -> Str {
    stage Process(input: Str) -> Str
    stage Analyze(data: Str) -> Str

    Process -> Analyze
}
"""


def test_generate_typescript_contains_types() -> None:
    declarations = parse(SIMPLE_AGENT)
    ts = generate_typescript(declarations)
    assert "export type Result" in ts
    assert "export type Option" in ts


def test_generate_typescript_agent_class() -> None:
    declarations = parse(SIMPLE_AGENT)
    ts = generate_typescript(declarations)
    assert "export class Bot" in ts
    assert 'readonly model = "@mock/model"' in ts
    assert "async run(" in ts


def test_generate_typescript_tool_interface() -> None:
    declarations = parse(AGENT_WITH_TOOL)
    ts = generate_typescript(declarations)
    assert "export interface SearchInput" in ts
    assert "export type SearchOutput" in ts
    assert "export interface Search" in ts


def test_generate_typescript_flow_class() -> None:
    declarations = parse(FLOW_DECL)
    ts = generate_typescript(declarations)
    assert "export class PipelineFlow" in ts
    assert "async run(input: string)" in ts


def test_axon_type_to_ts_primitives() -> None:
    assert _axon_type_to_ts("Str") == "string"
    assert _axon_type_to_ts("Int") == "number"
    assert _axon_type_to_ts("Float") == "number"
    assert _axon_type_to_ts("Bool") == "boolean"
    assert _axon_type_to_ts("Any") == "any"
    assert _axon_type_to_ts("()") == "void"


def test_axon_type_to_ts_generics() -> None:
    assert _axon_type_to_ts("List<Str>") == "Array<string>"
    assert _axon_type_to_ts("Map<Str, Int>") == "Map<string, number>"
    assert _axon_type_to_ts("Result<Str, Error>") == "Result<string, any>"
    assert _axon_type_to_ts("Option<Int>") == "Option<number>"
    assert _axon_type_to_ts("Stream<Str>") == "AsyncIterable<string>"
