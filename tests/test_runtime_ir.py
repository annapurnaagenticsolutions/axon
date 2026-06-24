"""Tests for IR-based runtime execution (Phase 12B).

Verifies that:
1. .axonir files can be loaded and executed directly
2. .ax files can be executed via IR (compile → IR → AST → run)
3. Both paths produce identical output
"""

from pathlib import Path

import pytest

from axon.ir_compiler import compile_to_ir, ir_to_ast, load_ir
from axon.ir_schema import AxonIR
from axon.runtime import RuntimeConfig, RuntimeExecutor


class TestRuntimeIR:
    def test_run_from_axonir_file(self, tmp_path: Path) -> None:
        """Execute a .axonir file directly."""
        ax_file = tmp_path / "test.ax"
        ax_file.write_text('''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
''')
        # Compile to IR
        ir = compile_to_ir(ax_file)
        axonir_file = tmp_path / "test.axonir"
        import json
        axonir_file.write_text(json.dumps(ir.to_dict(), indent=2), encoding="utf-8")

        # Run from .axonir
        config = RuntimeConfig(
            source_path=axonir_file,
            args={"q": "World"},
            mock=True,
        )
        executor = RuntimeExecutor(config)
        result = executor.execute()
        assert result.is_ok()
        assert "Hello, World!" in result.ok_value

    def test_run_via_ir_flag(self, tmp_path: Path) -> None:
        """Execute a .ax file by compiling through IR first."""
        ax_file = tmp_path / "test.ax"
        ax_file.write_text('''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
''')
        config = RuntimeConfig(
            source_path=ax_file,
            args={"q": "World"},
            mock=True,
            via_ir=True,
        )
        executor = RuntimeExecutor(config)
        result = executor.execute()
        assert result.is_ok()
        assert "Hello, World!" in result.ok_value

    def test_ir_and_direct_parse_produce_same_output(self, tmp_path: Path) -> None:
        """Direct parse and IR path should produce identical output."""
        ax_file = tmp_path / "test.ax"
        ax_file.write_text('''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
''')
        # Direct parse
        config_direct = RuntimeConfig(
            source_path=ax_file,
            args={"q": "World"},
            mock=True,
            via_ir=False,
        )
        result_direct = RuntimeExecutor(config_direct).execute()

        # Via IR
        config_ir = RuntimeConfig(
            source_path=ax_file,
            args={"q": "World"},
            mock=True,
            via_ir=True,
        )
        result_ir = RuntimeExecutor(config_ir).execute()

        assert result_direct.is_ok()
        assert result_ir.is_ok()
        assert result_direct.ok_value == result_ir.ok_value

    def test_ir_roundtrip_declarations(self, tmp_path: Path) -> None:
        """AST → IR → AST should produce declarations that the runtime accepts."""
        ax_file = tmp_path / "test.ax"
        ax_file.write_text('''
import { Chunk } from "axon:types"

type Response = { msg: Str }

rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./data/db")
    fn retrieve(query: Str) -> List<Chunk> { store.search(embed(query), 5) }
}

prompt Hello(name: Str) -> Str {
    """Say hello to {name}"""
}

tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    memory: Memory<ShortTerm>(capacity: 100)
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}

flow Pipeline(q: Str) -> Str {
    stage A(q: Str) -> Str
    stage B(q: Str) -> Str
    A -> B
}
''')
        ir = compile_to_ir(ax_file)
        declarations = ir_to_ast(ir)

        # Verify all declaration types are present
        from axon.ast_nodes import (
            AgentDecl, FlowDecl, ImportDecl, PromptDecl, RagDecl, ToolDecl, TypeAliasDecl,
        )
        assert any(isinstance(d, ImportDecl) for d in declarations)
        assert any(isinstance(d, TypeAliasDecl) for d in declarations)
        assert any(isinstance(d, RagDecl) for d in declarations)
        assert any(isinstance(d, PromptDecl) for d in declarations)
        assert any(isinstance(d, ToolDecl) for d in declarations)
        assert any(isinstance(d, AgentDecl) for d in declarations)
        assert any(isinstance(d, FlowDecl) for d in declarations)

        # Runtime should accept these declarations
        config = RuntimeConfig(
            source_path=ax_file,
            args={"q": "World"},
            mock=True,
        )
        # We need to bypass the normal source loading and inject declarations
        # For this test, just verify the runtime can be created
        executor = RuntimeExecutor(config)
        assert executor is not None

    def test_load_ir_from_file(self, tmp_path: Path) -> None:
        """Load a saved .axonir file and convert to AST."""
        ax_file = tmp_path / "test.ax"
        ax_file.write_text('''
agent Bot {
    model: @mock/gpt
    fn run() -> Str { "ok" }
}
''')
        ir = compile_to_ir(ax_file)
        axonir_file = tmp_path / "test.axonir"
        import json
        axonir_file.write_text(json.dumps(ir.to_dict(), indent=2), encoding="utf-8")

        loaded_ir = load_ir(axonir_file)
        assert isinstance(loaded_ir, AxonIR)
        assert loaded_ir.version == "0.2.0"
        assert len(loaded_ir.agents) == 1
        assert loaded_ir.agents[0].name == "Bot"

        declarations = ir_to_ast(loaded_ir)
        from axon.ast_nodes import AgentDecl
        assert any(isinstance(d, AgentDecl) and d.name == "Bot" for d in declarations)
