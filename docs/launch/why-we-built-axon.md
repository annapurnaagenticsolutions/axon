# Why We Built a Programming Language for AI Agents

**AXON: A typed DSL where agents, tools, memory, RAG, and orchestration are first-class language constructs — not framework boilerplate.**

---

## The Problem

Every agent framework today is a library sitting on top of a language that was never designed for agents. The result:

- **No type safety** — tool signatures, agent inputs, and flow stages are checked at runtime, not compile time. You discover a type mismatch when your agent crashes in production.
- **Boilerplate everywhere** — defining a tool, an agent, a RAG pipeline, and a multi-agent flow in LangChain requires importing 15+ classes, wiring them manually, and writing 500+ lines of glue code.
- **No compilation** — you can't target Python and TypeScript from the same source. You write your agent logic twice.
- **Framework lock-in** — your agents are written in framework-specific abstractions. Switching frameworks means rewriting everything.

We've been here before. Before SQL, every database query was imperative code. Before React, every UI was manual DOM manipulation. Before Kubernetes, every deployment was a custom script.

**The pattern: when a domain becomes complex enough, it gets its own language.**

AI agents have reached that point.

---

## What AXON Is

AXON is a programming language where the five primitives of agentic systems are first-class language constructs:

1. **Agents** — `agent Name { model, tools, memory, fn run() }`
2. **Tools** — `tool Name(input: Type) -> Result<Output, Error>`
3. **RAG** — `rag Name { source, chunker, embedder, store, fn retrieve() }`
4. **Flows** — `flow Name(input) { stage A -> stage B -> stage C }`
5. **Memory** — `Memory<Episodic>(max_events: 500)`

You write `.ax` files. The AXON compiler type-checks them, then compiles to **Python MCP servers** or **TypeScript modules**. One source, multiple targets.

---

## Side-by-Side: Multi-Agent Research Pipeline

### AXON (189 lines)

```axon
type ResearchQuery = { topic: Str, depth: "quick" | "deep" = "quick" }
type SearchResult = { source: Str, snippet: Str, relevance: Float }
type FactCheckResult = { claim: Str, verdict: "confirmed" | "plausible" | "disputed" | "unverified", confidence: Float }
type ResearchReport = { topic: Str, summary: Str, sources: List<SearchResult>, facts: List<FactCheckResult>, confidence: Float }

tool WebSearch(query: Str, max_results: Int = 5) -> Result<List<SearchResult>, ToolError> {
    http.get("https://api.search.example/v1", { q: query, limit: max_results })
        |> map(result => { source: result.url, snippet: result.snippet, relevance: result.score })
}

rag ResearchDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 1024, overlap: 128)
    embedder: @openai/text-embed-3
    store: VectorDB::in_memory()
}

agent QueryPlanner {
    model: @openai/gpt-4o-mini
    tools: [ResearchDocs.retrieve]
    fn plan(query: ResearchQuery) -> Result<List<Str>, AgentError> { ... }
}

agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch, ResearchDocs.retrieve]
    memory: Memory<Episodic>(max_events: 500)
    fn investigate(sub_query: Str, depth: Str) -> Result<List<SearchResult>, AgentError> { ... }
}

flow ResearchPipeline(input: ResearchQuery) -> ResearchReport {
    stage Plan -> Investigate -> Summarize -> Verify -> Compile
}
```

### Equivalent in LangChain (~500+ lines of Python)

```python
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional, Literal
from pydantic import BaseModel
import asyncio

class ResearchQuery(BaseModel):
    topic: str
    depth: Literal["quick", "deep"] = "quick"

class SearchResult(BaseModel):
    source: str
    snippet: str
    relevance: float

class FactCheckResult(BaseModel):
    claim: str
    verdict: Literal["confirmed", "plausible", "disputed", "unverified"]
    confidence: float

class ResearchReport(BaseModel):
    topic: str
    summary: str
    sources: List[SearchResult]
    facts: List[FactCheckResult]
    confidence: float

class PipelineState(TypedDict):
    query: ResearchQuery
    sub_queries: List[str]
    results: List[SearchResult]
    summary: str
    facts: List[FactCheckResult]
    report: Optional[ResearchReport]

@tool
def web_search(query: str, max_results: int = 5) -> List[dict]:
    # ... 20 lines of HTTP call + parsing ...

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=128)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = InMemoryVectorStore(embedding=embeddings)

def query_planner(state: PipelineState) -> PipelineState:
    llm = ChatOpenAI(model="gpt-4o-mini")
    # ... 15 lines of prompt construction + parsing ...

def research_agent(state: PipelineState) -> PipelineState:
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    # ... 30 lines of parallel search + memory management ...

def summarizer(state: PipelineState) -> PipelineState:
    llm = ChatAnthropic(model="claude-3-5-haiku-20241022")
    # ... 15 lines of summarization ...

def fact_checker(state: PipelineState) -> PipelineState:
    llm = ChatOpenAI(model="gpt-4o-mini")
    # ... 25 lines of claim extraction + verification ...

def compile_report(state: PipelineState) -> PipelineState:
    # ... 15 lines of report assembly ...

workflow = StateGraph(PipelineState)
workflow.add_node("plan", query_planner)
workflow.add_node("investigate", research_agent)
workflow.add_node("summarize", summarizer)
workflow.add_node("verify", fact_checker)
workflow.add_node("compile", compile_report)
workflow.add_edge("plan", "investigate")
workflow.add_edge("investigate", "summarize")
workflow.add_edge("summarize", "verify")
workflow.add_edge("verify", "compile")
workflow.add_edge("compile", END)
workflow.set_entry_point("plan")
app = workflow.compile()

# No type checking on tool signatures.
# No compile-time validation of flow stages.
# No multi-target compilation.
# No built-in memory primitives.
# No RAG as a first-class construct.
```

### The Difference

| Dimension | AXON | LangChain/LangGraph |
|-----------|------|-------------------|
| Lines of code | 189 | 500+ |
| Type safety | Compile-time | Runtime only |
| Multi-target compilation | Python + TypeScript | Python only |
| RAG as first-class construct | Yes (`rag` declaration) | No (manual wiring) |
| Memory as first-class construct | Yes (`Memory<Episodic>`) | No (manual checkpointing) |
| Flow validation | Compile-time stage checking | Runtime graph validation |
| Tool signature checking | Compiler catches mismatches | Discovered at runtime |
| Boilerplate per agent | ~10 lines | ~30-50 lines |
| Switching LLM provider | Change `@openai/gpt-4o` → `@anthropic/claude-4` | Change import + class + config |

---

## What AXON Is Not

- **Not a framework** — it's a language with a compiler. You don't `pip install axon` and import classes. You write `.ax` files and compile them.
- **Not a replacement for Python** — AXON compiles **to** Python (and TypeScript). Your existing Python code, libraries, and infrastructure work as-is.
- **Not vaporware** — 1100+ tests, 16 examples, working CLI, Docker/K8s deployment, VS Code extension with LSP, debugger, profiler.

---

## Quick Start

```bash
git clone https://github.com/annapurnaagenticsolutions/axon.git
cd axon
pip install -e ".[dev]"
```

Write your first agent:

```axon
// hello.ax
tool Greet(name: Str) -> Str {
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(q: Str) -> Str { q }
}
```

Compile and run:

```bash
axon syntax hello.ax        # Syntax check
axon validate hello.ax      # Type check
axon run hello.ax --mock    # Run with mock LLM (no API key needed)
axon compile --target ts    # Compile to TypeScript
```

---

## What's in the Repo

- **1100+ tests** — parser, type checker, codegen, CLI, runtime
- **16 examples** — research pipeline, GitHub triage, invoice extraction, monitoring alerts, data analysis, multi-agent memory, and more
- **CLI tools** — `axon run`, `axon compile`, `axon build`, `axon deploy`, `axon debug`, `axon profile`, `axon serve-api`, `axon supervisor`
- **Docker + Kubernetes** — production deployment configs included
- **VS Code extension** — syntax highlighting, LSP, autocomplete
- **Debugger** — trace execution, inspect agent state, set breakpoints
- **Profiler** — token usage, latency, cost per agent/tool/flow

---

## The Roadmap

**Now (v0.1):** Parser, type checker, Python codegen, CLI, 16 examples, 1100+ tests
**Next (v0.2):** Web playground (try AXON in your browser, no install)
**Then (v0.3):** TypeScript codegen production-ready, MCP server auto-generation
**Future:** Plugin system, custom codegen targets, agent marketplace

---

## Why MIT?

Because we want you to use it, fork it, build with it, and tell us what breaks. No CLA, no dual license, no "commercial use requires a paid plan." MIT. Period.

---

## Try It

```bash
git clone https://github.com/annapurnaagenticsolutions/axon.git
cd axon
pip install -e ".[dev]"
axon run examples/hello.ax --mock
```

No API key needed for `--mock` mode. 1100+ tests pass. 16 examples work.

**GitHub:** [github.com/annapurnaagenticsolutions/axon](https://github.com/annapurnaagenticsolutions/axon)
**License:** MIT

---

*Built by Annapurna Agentic Solutions. Built in India, for the world.*
