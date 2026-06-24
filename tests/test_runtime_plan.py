from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from axon.parser import parse
from axon.runtime_plan import (
    build_runtime_plan,
    build_runtime_plan_from_file,
    build_runtime_plan_from_source,
    default_runtime_capabilities,
    format_runtime_plan,
    runtime_plan_to_json,
)


ROOT = Path(__file__).resolve().parents[1]


SOURCE = '''
type Priority = "low" | "high"

prompt Summarize(text: Str, @budget(tokens: 200)) -> Str {
    """
    Summarize {text}
    """
}

tool Search(query: Str, max_results: Int = 5) -> Result<List<Any>, ToolError> {
    /// Searches safely.
    http.get(query)
}

rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @ollama/nomic-embed-text
    store: VectorDB::sqlite("./index.db")

    fn retrieve(query: Str) -> List<Chunk> {
        store.search(embed(query), 5)
    }
}

flow AnswerFlow(question: Str) -> Str {
    stage Retrieve(query: Str) -> List<Chunk>
    stage Answer(chunks: List<Chunk>, question: Str) -> Str

    Retrieve -> Answer
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Search]
    memory: Memory<ShortTerm>(capacity: 500)

    fn run(q: Str) -> Result<Str, AgentError> {
        let result = act Search(query: q)?
        Ok(result)
    }
}
'''


def test_runtime_plan_summarizes_all_supported_declarations():
    plan = build_runtime_plan_from_source(SOURCE, source_path="memory.ax")

    assert plan.source_path == "memory.ax"
    assert plan.counts()["type_aliases"] == 1
    assert plan.counts()["prompts"] == 1
    assert plan.counts()["tools"] == 1
    assert plan.counts()["agents"] == 1
    assert plan.counts()["rags"] == 1
    assert plan.counts()["flows"] == 1
    assert plan.agents[0].name == "Bot"
    assert plan.agents[0].model == "@anthropic/claude-4"
    assert plan.agents[0].tools == ["Search"]
    assert plan.agents[0].memory_kind == "ShortTerm"
    assert plan.agents[0].memory_options["capacity"] == "500"
    assert plan.agents[0].executable is False
    assert plan.tools[0].executable is False
    assert plan.rags[0].indexing_enabled is False
    assert plan.rags[0].retrieval_enabled is False
    assert plan.flows[0].executable is False


def test_default_runtime_capabilities_keep_execution_disabled():
    capabilities = {capability.name: capability for capability in default_runtime_capabilities()}

    assert capabilities["declaration_inspection"].enabled is True
    for name in [
        "method_execution",
        "provider_calls",
        "tool_dispatch",
        "memory_mutation",
        "rag_indexing",
        "rag_retrieval",
        "flow_execution",
        "trace_replay",
        "secret_resolution",
        "fastmcp_runtime_import",
    ]:
        assert capabilities[name].enabled is False
        assert capabilities[name].reason


def test_runtime_plan_json_is_secret_safe_and_stable():
    plan = build_runtime_plan(parse(SOURCE), source_path="memory.ax")
    data = json.loads(runtime_plan_to_json(plan))

    assert data["source_path"] == "memory.ax"
    assert data["counts"]["agents"] == 1
    assert data["agents"][0]["model"] == "@anthropic/claude-4"
    assert data["agents"][0]["executable"] is False
    assert "api_key" not in json.dumps(data).lower()


def test_runtime_plan_human_format_mentions_non_executing_boundary():
    plan = build_runtime_plan_from_source(SOURCE, source_path="memory.ax")
    text = format_runtime_plan(plan)

    assert "AXON runtime plan (non-executing)" in text
    assert "Bot" in text
    assert "provider_calls: disabled" in text
    assert "tool_dispatch: disabled" in text
    assert "runtime plan is inspection-only" in text


def test_runtime_plan_from_file_validates_source():
    plan = build_runtime_plan_from_file(ROOT / "examples" / "hello.ax")

    assert plan.source_path.endswith("hello.ax")
    assert plan.counts()["agents"] == 1
    assert plan.counts()["tools"] >= 1


def test_runtime_plan_cli_human_output():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "runtime-plan", str(ROOT / "examples" / "hello.ax")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "AXON runtime plan (non-executing)" in completed.stdout
    assert "Capabilities:" in completed.stdout


def test_runtime_plan_cli_json_output():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "runtime-plan", str(ROOT / "examples" / "hello.ax"), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data["counts"]["agents"] == 1
    assert any(cap["name"] == "method_execution" and cap["enabled"] is False for cap in data["capabilities"])
