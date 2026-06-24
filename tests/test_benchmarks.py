"""Performance benchmarks for AXON runtime operations.

These tests measure the performance of key operations to detect regressions.
"""

from __future__ import annotations

import time

from axon.parser import parse
from axon.type_checker import check_types
from axon.validator import validate


# Sample AXON source for benchmarking
SIMPLE_AGENT = '''
agent Bot {
    model: @anthropic/claude-4
    tools: []

    fn run(query: Str) -> Str {
        "Hello, " + query
    }
}
'''

COMPLEX_AGENT = '''
tool Search(query: Str) -> Result<List<Str>, Error> {
    /// Search for items.
}

tool Fetch(id: Int) -> Result<Str, Error> {
    /// Fetch item by id.
}

agent ResearchBot {
    model: @anthropic/claude-4
    tools: [Search, Fetch]

    fn search(query: Str) -> Result<List<Str>, Error> {
        act Search(query: query)
    }

    fn fetch_item(id: Int) -> Result<Str, Error> {
        act Fetch(id: id)
    }

    fn run(query: Str) -> Result<Str, Error> {
        let results = search(query: query)?
        let first = results[0]
        fetch_item(id: 1)
    }
}
'''

FLOW_SOURCE = '''
flow Pipeline(input: Str) -> Str {
    stage Process(input: Str) -> Str
    stage Analyze(data: Str) -> Str
    stage Format(result: Str) -> Str

    Process -> Analyze
    Analyze -> Format
}
'''


def _benchmark(func, *args, iterations: int = 3, **kwargs) -> float:
    """Run a function multiple times and return average time in ms."""
    start = time.perf_counter()
    for _ in range(iterations):
        func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000  # Convert to ms


class TestParseBenchmarks:
    """Benchmarks for parsing operations."""

    def test_parse_simple_agent(self) -> None:
        """Benchmark parsing a simple agent declaration."""
        avg_ms = _benchmark(parse, SIMPLE_AGENT)
        assert avg_ms < 10.0, f"Parse simple agent too slow: {avg_ms:.2f}ms"

    def test_parse_complex_agent(self) -> None:
        """Benchmark parsing a complex agent with multiple methods."""
        avg_ms = _benchmark(parse, COMPLEX_AGENT)
        assert avg_ms < 20.0, f"Parse complex agent too slow: {avg_ms:.2f}ms"

    def test_parse_flow(self) -> None:
        """Benchmark parsing a flow declaration."""
        avg_ms = _benchmark(parse, FLOW_SOURCE)
        assert avg_ms < 10.0, f"Parse flow too slow: {avg_ms:.2f}ms"


class TestTypeCheckBenchmarks:
    """Benchmarks for type checking operations."""

    def test_type_check_simple_agent(self) -> None:
        """Benchmark type checking a simple agent."""
        declarations = parse(SIMPLE_AGENT)
        avg_ms = _benchmark(check_types, declarations)
        assert avg_ms < 10.0, f"Type check simple agent too slow: {avg_ms:.2f}ms"

    def test_type_check_complex_agent(self) -> None:
        """Benchmark type checking a complex agent."""
        declarations = parse(COMPLEX_AGENT)
        avg_ms = _benchmark(check_types, declarations)
        assert avg_ms < 20.0, f"Type check complex agent too slow: {avg_ms:.2f}ms"


class TestValidateBenchmarks:
    """Benchmarks for validation operations."""

    def test_validate_simple_agent(self) -> None:
        """Benchmark validating a simple agent."""
        declarations = parse(SIMPLE_AGENT)
        avg_ms = _benchmark(validate, declarations, False)
        assert avg_ms < 15.0, f"Validate simple agent too slow: {avg_ms:.2f}ms"


class TestExpressionParseBenchmarks:
    """Benchmarks for expression parsing with type checking."""

    def test_parse_with_expressions(self) -> None:
        """Benchmark parsing with expression AST generation."""
        avg_ms = _benchmark(parse, COMPLEX_AGENT, parse_expressions=True)
        assert avg_ms < 30.0, f"Parse with expressions too slow: {avg_ms:.2f}ms"

    def test_type_check_with_expressions(self) -> None:
        """Benchmark type checking with expression parsing."""
        declarations = parse(COMPLEX_AGENT, parse_expressions=True)
        avg_ms = _benchmark(check_types, declarations)
        assert avg_ms < 30.0, f"Type check with expressions too slow: {avg_ms:.2f}ms"
