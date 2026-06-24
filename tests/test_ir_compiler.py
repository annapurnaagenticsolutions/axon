"""Tests for the AXON IR compiler."""

from pathlib import Path

import pytest

from axon.ir_compiler import IRCompileError, compile_to_ir
from axon.ir_schema import AxonIR


class TestCompileToIR:
    def test_compile_empty_file(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.ax"
        src.write_text("")
        ir = compile_to_ir(src)
        assert isinstance(ir, AxonIR)
        assert ir.version == "0.2.0"
        assert ir.agents == []
        assert ir.tools == []
        assert ir.imports == []
        assert ir.type_aliases == []
        assert ir.rags == []
        assert ir.prompts == []
        assert ir.flows == []

    def test_compile_agent_with_provider(self, tmp_path: Path) -> None:
        src = tmp_path / "agent_provider.ax"
        src.write_text('''
agent Greeter {
    model: @openai/gpt-4
    memory: Memory<ShortTerm>(capacity: 100)
    fn run(name: Str) -> Str {
        return "Hello, " + name
    }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.agents) == 1
        assert ir.agents[0].name == "Greeter"
        assert ir.agents[0].model == "openai/gpt-4"
        assert ir.agents[0].tools == []
        assert ir.agents[0].memory is not None
        assert ir.agents[0].memory.kind == "ShortTerm"
        assert len(ir.agents[0].methods) == 1
        assert ir.agents[0].methods[0].name == "run"
        assert ir.agents[0].methods[0].return_type == "Str"

    def test_compile_agent_tools(self, tmp_path: Path) -> None:
        src = tmp_path / "agent_tools.ax"
        src.write_text('''
tool WebSearch(query: Str) -> Str {
    /// Search the web for a query.
    return "results"
}

agent Searcher {
    model: @openai/gpt-4
    tools: [WebSearch]
    memory: Memory<ShortTerm>(capacity: 100)
    fn run(query: Str) -> Str {
        return "done"
    }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.agents) == 1
        assert "WebSearch" in ir.agents[0].tools
        assert len(ir.tools) == 1
        assert ir.tools[0].name == "WebSearch"
        assert ir.tools[0].docstrings == ["Search the web for a query."]

    def test_compile_invalid_source(self, tmp_path: Path) -> None:
        src = tmp_path / "bad.ax"
        src.write_text("not valid axon syntax !!!")
        with pytest.raises(IRCompileError):
            compile_to_ir(src)

    def test_ir_serialization_roundtrip(self, tmp_path: Path) -> None:
        src = tmp_path / "roundtrip.ax"
        src.write_text('''
agent Greeter {
    model: @openai/gpt-4
    memory: Memory<ShortTerm>(capacity: 100)
    fn run(name: Str) -> Str {
        return "Hello, " + name
    }
}
''')
        ir = compile_to_ir(src)
        serialized = ir.to_dict()
        restored = AxonIR.from_dict(serialized)
        assert restored.agents[0].name == ir.agents[0].name
        assert restored.agents[0].model == ir.agents[0].model
        assert restored.agents[0].methods[0].body == ir.agents[0].methods[0].body

    def test_compile_import(self, tmp_path: Path) -> None:
        src = tmp_path / "imports.ax"
        src.write_text('''
import { Chunk } from "axon:types"
import { WebSearch } from "axon:tools/web"

agent TestAgent {
    model: @mock/gpt
    fn run() -> Str { "ok" }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.imports) == 2
        assert ir.imports[0].names == ["Chunk"]
        assert ir.imports[0].source == "axon:types"
        assert ir.imports[1].names == ["WebSearch"]
        assert ir.imports[1].source == "axon:tools/web"

    def test_compile_type_alias(self, tmp_path: Path) -> None:
        src = tmp_path / "type_alias.ax"
        src.write_text('''
type SupportResponse = {
    answer: Str,
    confidence: Float,
    escalated: Bool
}

agent TestAgent {
    model: @mock/gpt
    fn run() -> SupportResponse { { answer: "hi", confidence: 1.0, escalated: false } }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.type_aliases) == 1
        assert ir.type_aliases[0].name == "SupportResponse"
        assert len(ir.type_aliases[0].fields) == 3
        assert ir.type_aliases[0].fields[0].name == "answer"

    def test_compile_rag(self, tmp_path: Path) -> None:
        src = tmp_path / "rag.ax"
        src.write_text('''
rag ProductDocs {
    source: "./kb/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./data/db")

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}

agent TestAgent {
    model: @mock/gpt
    tools: [ProductDocs.retrieve]
    fn run() -> Str { "ok" }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.rags) == 1
        rag = ir.rags[0]
        assert rag.name == "ProductDocs"
        assert rag.source == '"./kb/**/*.md"'
        assert rag.chunker == "Chunker::sliding(size: 512, overlap: 64)"
        assert rag.embedder == "@openai/text-embed-3"
        assert rag.store == 'VectorDB::sqlite("./data/db")'
        assert len(rag.methods) == 1
        assert rag.methods[0].name == "retrieve"
        assert rag.methods[0].return_type == "List<Chunk>"

    def test_compile_prompt(self, tmp_path: Path) -> None:
        src = tmp_path / "prompt.ax"
        src.write_text('''
prompt AnswerFromDocs(question: Str, context: List<Chunk>) -> Str {
    """
    Answer the question using the context.

    Question: {question}
    Context: {context}
    """
}

agent TestAgent {
    model: @mock/gpt
    fn run() -> Str { "ok" }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.prompts) == 1
        prompt = ir.prompts[0]
        assert prompt.name == "AnswerFromDocs"
        assert prompt.return_type == "Str"
        assert "Answer the question" in prompt.template
        assert len(prompt.params) == 2
        assert prompt.params[0].name == "question"

    def test_compile_flow(self, tmp_path: Path) -> None:
        src = tmp_path / "flow.ax"
        src.write_text('''
flow ResearchPipeline(topic: Str) -> Str {
    stage Research(topic: Str) -> Str
    stage Write(chunks: List<Chunk>) -> Str

    Research -> Write
}

agent TestAgent {
    model: @mock/gpt
    fn run() -> Str { "ok" }
}
''')
        ir = compile_to_ir(src)
        assert len(ir.flows) == 1
        flow = ir.flows[0]
        assert flow.name == "ResearchPipeline"
        assert flow.return_type == "Str"
        assert len(flow.stages) == 2
        assert flow.stages[0].name == "Research"
        assert flow.stages[1].name == "Write"
        assert len(flow.edges) == 1
        assert flow.edges[0].from_stage == "Research"
        assert flow.edges[0].to_stage == "Write"

    def test_compile_full_example(self, tmp_path: Path) -> None:
        src = tmp_path / "full.ax"
        src.write_text('''
import { Chunk } from "axon:types"

type SupportResponse = {
    answer: Str,
    confidence: Float,
    escalated: Bool
}

rag ProductDocs {
    source: "./kb/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./data/db")

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}

prompt AnswerFromDocs(question: Str, context: List<Chunk>) -> SupportResponse {
    """
    Answer the question.
    """
}

tool CreateTicket(title: Str, description: Str) -> Result<Str, ToolError> {
    /// Creates a ticket.
    http.post(env.API, { title, description })
}

agent CustomerSupport {
    model: @anthropic/claude-4
    tools: [ProductDocs.retrieve, CreateTicket]
    memory: Memory<Semantic>

    fn handle(question: Str) -> Result<SupportResponse, AgentError> {
        let context = act ProductDocs.retrieve(query: question, top_k: 5)?
        Ok({ answer: "hi", confidence: 1.0, escalated: false })
    }
}

flow Pipeline(topic: Str) -> Str {
    stage Research(topic: Str) -> Str
    stage Write(topic: Str) -> Str
    Research -> Write
}
''')
        ir = compile_to_ir(src)
        assert ir.version == "0.2.0"
        assert len(ir.imports) == 1
        assert len(ir.type_aliases) == 1
        assert len(ir.rags) == 1
        assert len(ir.prompts) == 1
        assert len(ir.tools) == 1
        assert len(ir.agents) == 1
        assert len(ir.flows) == 1

        agent = ir.agents[0]
        assert agent.name == "CustomerSupport"
        assert agent.model == "anthropic/claude-4"
        assert "ProductDocs.retrieve" in agent.tools
        assert "CreateTicket" in agent.tools
        assert agent.memory is not None
        assert agent.memory.kind == "Semantic"
        assert len(agent.methods) == 1
        assert agent.methods[0].name == "handle"

        tool = ir.tools[0]
        assert tool.name == "CreateTicket"
        assert tool.docstrings == ["Creates a ticket."]
        assert "http.post" in tool.body

        flow = ir.flows[0]
        assert flow.name == "Pipeline"
        assert len(flow.stages) == 2
        assert len(flow.edges) == 1
