# RFC #023 — Polyglot Architecture & AXON Intermediate Representation

**Status:** Draft  
**Phase:** 12 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Transform AXON from a Python-specific framework into a **declarative, language-agnostic agent specification**. After deep analysis of the current codebase, AXON is already a sophisticated DSL with: typed agent declarations, RAG pipelines, prompt templates, flow orchestration, multi-agent memory, and an expression language. The missing piece is a **portable Intermediate Representation (IR)** that separates the *what* (`.ax` source) from the *how* (runtime implementation).

The IR is a **faithful serialization of the AST** — every construct in the language has an IR counterpart. Runtimes in any language (Python, Rust, JS/WASM, Go) consume IR and execute it against pluggable backends.

### IR and the Runtime Boundary

This RFC operates **inside the non-executing compiler boundary** defined by Runtime RFC #001 (`docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`) and `docs/RUNTIME_BOUNDARY.md`. The IR compiler is a pure AST → JSON transformation. It does not:

- execute method bodies
- call model providers
- dispatch tools
- mutate memory
- index or retrieve RAG data
- execute flows
- replay traces
- resolve secrets
- import FastMCP or provider SDKs

The IR is essentially a **formalized, versioned successor to the runtime plan** (`docs/RUNTIME_PLAN.md`). Where the runtime plan produces inspection-only JSON summaries, the IR produces a portable, schema-versioned artifact that any runtime can consume. Both answer the same safe question: *"Given a parsed and validated `.ax` file, what would a runtime need to know?*"

## Vision: SQL for Agents

| SQL | AXON source | IR construct |
|-----|-------------|--------------|
| `CREATE TABLE` | `type SupportResponse = {...}` | `TypeAliasDef` |
| `CREATE FUNCTION` | `tool CreateTicket(...) {...}` | `ToolDef` + expression body |
| `CREATE VIEW` | `prompt AnswerFromDocs(...) {...}` | `PromptDef` |
| `CREATE INDEX` | `rag ProductDocs {...}` | `RagDef` |
| Stored procedure | `agent ... { fn handle(...) {...} }` | `AgentDef` + `MethodDef` |
| Query planner | `flow ResearchPipeline {...}` | `FlowDef` (stage DAG) |
| `INSERT/SELECT` | `remember` / `recall` | Runtime memory ops |
| `JOIN` | `delegate`, `send`/`receive`, `act` | Cross-agent invocation |
| Query planner | `axon compile` | IR optimizer |

## Current Language Surface (Analyzed)

After reading `src/axon/parser.py`, `src/axon/ast_nodes.py`, `src/axon/runtime.py`, and all examples:

### Top-level declarations
- `import { Chunk } from "axon:types"` — module imports
- `type SupportResponse = { answer: Str, ... }` — type aliases with generics
- `rag ProductDocs { source, chunker, embedder, store, fn retrieve(...) {...} }` — RAG pipelines
- `prompt AnswerFromDocs(...) -> T { """...""" }` — typed prompt templates with `@budget` annotations
- `tool CreateTicket(...) -> Result<Str, ToolError> { ... }` — tools with docstrings (`///`) and expression bodies
- `agent CustomerSupportAgent { model, tools, memory, fn handle(...) {...} }` — agents with methods
- `flow ResearchPipeline { stage Research, stage Write, Research -> Write }` — flow DAGs

### Expression language
- `act ToolName(args)` — tool dispatch (RFC #004)
- `delegate Agent.method(args)` — cross-agent delegation (RFC #008)
- `model.complete(Prompt(...))` — provider completion (RFC #004)
- `remember(key, value)` / `recall(query, k)` — memory ops (RFC #009)
- `send(to, content)` / `receive()` — message bus (RFC #008)
- `let x = expr` / `if cond { ... }` — local bindings and control flow
- `expr |> func(args)` — pipes
- `http.post(url, body)` / `fs.read(path)` — built-ins
- `env.VAR_NAME` — environment access

### Type system
- Primitives: `Str`, `Int`, `Float`, `Bool`, `Bytes`
- Collections: `List<T>`, `Map<K, V>`, `Set<T>`
- Results: `Result<T, E>`, `Option<T>`
- Records: `{ field: Type }`
- Unions: `"low" | "medium" | "high"`
- Defaults: `param: Type = default_value`

## IR Coverage of Implemented Runtime Features

The IR schema captures every construct needed by the executing runtimes defined in RFCs #004–#009:

| Runtime RFC | Feature | IR Construct |
|---|---|---|
| **RFC #004** | Agent execution, mock tool dispatch, expression evaluation | `AgentDef` (with `MethodDef` methods), `ToolDef` (with raw `body`) |
| **RFC #005** | Flow DAG execution, stage composition | `FlowDef` (with `StageDef` stages and `FlowEdge` edges) |
| **RFC #006** | RAG indexing, chunking, embedding, retrieval | `RagDef` (with `source`, `chunker`, `embedder`, `store`, `methods`) |
| **RFC #007** | Trace replay from AEL JSONL | Not an IR construct — trace replay operates at runtime, not compile time |
| **RFC #008** | Multi-agent message passing, named agent execution | `AgentDef` (all agents with `name`, `tools`, `memory`), `FlowDef` (pipeline composition) |
| **RFC #009** | Persistent semantic memory (remember/recall/forget) | `AgentDef.memory` (`MemoryDecl`), `MemorySchema` |

Expression bodies in `MethodDef` and `ToolDef` are stored as **raw text** in IR v0.2. A future version may optionally include a parsed expression AST (from `EXPRESSION_PARSER.md`) as an extension field, but raw text is sufficient for all current runtimes.

## IR Design Principle

> **The IR is a complete, lossless serialization of the AST.** No construct is simplified or omitted. Runtimes have full fidelity to reproduce execution semantics.

This is different from a "simplified" IR like LLVM IR. AXON IR is closer to Protocol Buffers for AST nodes — structured, typed, versioned.

## IR Schema v0.2 (Complete)

### Top-level document
```json
{
  "version": "0.2.0",
  "imports": [...],
  "type_aliases": [...],
  "rags": [...],
  "prompts": [...],
  "tools": [...],
  "agents": [...],
  "flows": [...],
  "metadata": {...}
}
```

### ImportDef
```json
{
  "kind": "import",
  "names": ["Chunk", "WebSearch"],
  "source": "axon:types"
}
```

### TypeAliasDef
```json
{
  "kind": "type_alias",
  "name": "SupportResponse",
  "type_params": [],
  "value": "{ answer: Str, confidence: Float, escalated: Bool }",
  "fields": [
    { "name": "answer", "type_str": "Str" },
    { "name": "confidence", "type_str": "Float" },
    { "name": "escalated", "type_str": "Bool" }
  ]
}
```

### RagDef
```json
{
  "kind": "rag",
  "name": "ProductDocs",
  "source": "\"./knowledge_base/**/*.md\"",
  "chunker": "Chunker::sliding(size: 512, overlap: 64)",
  "embedder": "@openai/text-embed-3",
  "store": "VectorDB::sqlite(\"./data/product_docs.db\")",
  "methods": [
    {
      "name": "retrieve",
      "params": [
        { "name": "query", "type_str": "Str" },
        { "name": "top_k", "type_str": "Int = 5", "default": "5" }
      ],
      "return_type": "List<Chunk>",
      "body": "store.search(embed(query), top_k) |> rerank(...)"
    }
  ],
  "annotations": []
}
```

### PromptDef
```json
{
  "kind": "prompt",
  "name": "AnswerFromDocs",
  "params": [
    { "name": "question", "type_str": "Str" },
    { "name": "context", "type_str": "List<Chunk>" }
  ],
  "return_type": "SupportResponse",
  "template": "Answer the customer question using only...",
  "annotations": [
    { "name": "budget", "args": { "tokens": "900" } }
  ]
}
```

### ToolDef
```json
{
  "kind": "tool",
  "name": "CreateSupportTicket",
  "params": [
    { "name": "title", "type_str": "Str" },
    { "name": "description", "type_str": "Str" },
    { "name": "priority", "type_str": "\"low\" | \"medium\" | \"high\" = \"medium\"", "default": "\"medium\"" }
  ],
  "return_type": "Result<Str, ToolError>",
  "docstrings": ["Creates a support ticket in the service desk.", "Use when documentation is missing..."],
  "body": "http.post(env.SUPPORT_TICKET_API, { title, description, priority })",
  "annotations": []
}
```

### AgentDef
```json
{
  "kind": "agent",
  "name": "CustomerSupportAgent",
  "model": "@anthropic/claude-4",
  "tools": ["ProductDocs.retrieve", "CreateSupportTicket"],
  "memory": { "kind": "Semantic", "options": {} },
  "methods": [
    {
      "name": "handle",
      "params": [{ "name": "question", "type_str": "Str" }],
      "return_type": "Result<SupportResponse, AgentError>",
      "body": "let context = act ProductDocs.retrieve(...)...",
      "annotations": []
    }
  ],
  "annotations": [],
  "workers": null
}
```

### FlowDef
```json
{
  "kind": "flow",
  "name": "ResearchPipeline",
  "params": [{ "name": "topic", "type_str": "Str" }],
  "return_type": "Str",
  "stages": [
    { "name": "Research", "params": [{ "name": "topic", "type_str": "Str" }], "return_type": "Str" },
    { "name": "Write", "params": [{ "name": "topic", "type_str": "Str" }], "return_type": "Str" }
  ],
  "edges": [
    { "from": "Research", "to": "Write" }
  ],
  "annotations": []
}
```

## Compilation Pipeline

```
.ax source text
    ↓
Parser (language-specific: Python regex now → Rust nom later)
    ↓
AST (language-specific dataclasses / structs)
    ↓
Validator (language-specific, same rules)
    ↓
IR Serializer (language-specific AST → JSON IR)
    ↓
.axonir (portable JSON)
    ↓
Any Runtime (Python, Rust, JS, Go)
    ↓
Backend Providers (OpenAI, Anthropic, Ollama)
    ↓
Backend Memory (SQLite, PostgreSQL, Redis)
    ↓
Backend Tools (WASM, Docker, REST, in-process)
```

**Key invariant:** Two parsers (Python and Rust) parsing the same `.ax` file must emit **bit-identical `.axonir` JSON** (modulo key ordering). This is the conformance test.

## Runtime Architecture

Each runtime implements:

```
┌─────────────────────────────────────────┐
│           Runtime Core (any lang)        │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│  │  Agent   │ │  Flow   │ │  Tool    │  │
│  │ Executor │ │ Executor│ │ Executor │  │
│  └────┬────┘ └────┬────┘ └────┬─────┘  │
│       └──────────┬───────────┘          │
│                  ↓                       │
│  ┌──────────────────────────────────┐   │
│  │       Backend Interfaces         │   │
│  │  ProviderBackend  MemoryBackend   │   │
│  │  ToolExecutor     TransportLayer  │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

Backend interfaces are also defined in IR (or a companion spec) so backends can be swapped without changing agent source.

## Polyglot Runtime Roadmap

| Phase | Runtime | Deliverable | Timeline |
|-------|---------|-------------|----------|
| **A** | Python | IR compiler + runtime consumes IR | Now |
| **B** | Python | Refactor `axon run` to load `.axonir` | +1 month |
| **C** | Rust | `axon-parser` crate (`.ax` → `.axonir`) | +3 months |
| **D** | Rust | `axon-runtime` crate (execute `.axonir`) | +6 months |
| **E** | Rust | CLI binary `axon` (compile + run + serve) | +9 months |
| **F** | JS/WASM | Browser runtime for edge deployment | +12 months |
| **G** | Go | Community runtime for K8s operators | +15 months |

## Module System & Registry

```bash
# Install from registry
axon install agent/customer-support@1.2.0
axon install tool/web-search@0.5.1
axon install prompt/qa-template@0.3.0

# axon.toml dependencies
[dependencies]
agent/customer-support = "1.2.0"
tool/web-search = "0.5.1"
prompt/qa-template = "0.3.0"
```

Package structure:
```
customer-support@1.2.0/
  manifest.json
  customer_support.axonir
  schemas/
    support_response.json
  wasm/
    search_kb.wasm
```

## Security Model

Capability-based, encoded in IR:

```json
{
  "kind": "agent",
  "name": "CustomerSupportAgent",
  "security": {
    "capabilities": [
      { "resource": "tool:ProductDocs.retrieve", "action": "allow" },
      { "resource": "tool:CreateSupportTicket", "action": "allow" },
      { "resource": "tool:exec_shell", "action": "deny" },
      { "resource": "memory:semantic", "action": "allow" }
    ],
    "approval_gates": [
      { "tool_id": "CreateSupportTicket", "timeout_seconds": 300 }
    ]
  }
}
```

Tool executors verify capabilities before execution. WASM tools run in WASI sandbox. Docker tools run with restricted filesystem and network.

## Adoption Strategy

1. **No breaking changes to `.ax` syntax.** IR is additive.
2. **Python stays the default runtime.** `axon run file.ax` works exactly as before.
3. **IR is opt-in.** `axon compile --ir` for cross-runtime deployment.
4. **Gradual migration.** Phase B refactors Python runtime to consume IR internally; users see no difference.

## Foundation Audit Verification

The IR compiler is verified to operate inside the non-executing compiler boundary:

```bash
$ axon foundation-audit . --json
{
  "passed": true,
  "issues": [],
  "non_execution_guarantee": "foundation audit is inspection-only: it does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces",
  "disabled_runtime_capabilities": [
    "method_execution", "provider_calls", "tool_dispatch",
    "memory_mutation", "rag_indexing", "rag_retrieval",
    "flow_execution", "trace_replay", "secret_resolution",
    "fastmcp_runtime_import"
  ]
}
```

The IR compiler (`src/axon/ir_compiler.py`) is a pure AST → JSON transformation. It calls `parse()` and `validate()` (both inspection-only) and walks the resulting dataclasses to populate `AxonIR`. No execution boundary is crossed.

## Testing Strategy

- **IR roundtrip:** Parse `.ax` → emit IR → re-serialize → diff against original IR
- **Cross-parser conformance:** Same `.ax` parsed by Python and Rust emit identical IR
- **Backend swap:** Same `.axonir` executed with SQLite vs PostgreSQL memory backend
- **Capability enforcement:** Agent denied `tool:exec_shell` fails predictably in all runtimes
- **Cross-runtime delegation:** Python agent delegates to Rust agent via shared transport

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| IR schema churn | Versioned schema (`"version": "0.2.0"`). Runtimes reject incompatible IR. |
| Rust runtime lag | IR is the contract. Feature parity enforced by conformance tests. |
| Expression parsing complexity | Expression AST is also serialized in IR. Runtimes share expression evaluator spec. |
| Python ecosystem lock-in | Python bindings remain first-class. Rust is additive. |

## Immediate Next Steps

1. **Expand IR schema** to cover all AST nodes (imports, type aliases, RAGs, prompts, flows)
2. **Expand IR compiler** to extract all declaration types from parser output
3. **Refactor Python runtime** to optionally consume `.axonir` instead of `.ax`
4. **Rust parser crate** — start with `Cargo.toml` + `src/lib.rs` that parses a subset
5. **IR conformance test** — Python parser output vs expected IR JSON

## References

### Source code
- `src/axon/parser.py` — current parser (regex-based, Python)
- `src/axon/ast_nodes.py` — AST dataclasses
- `src/axon/runtime.py` — current runtime executor
- `src/axon/expression_parser.py` — expression AST parser (Phase 2 static analysis)
- `src/axon/ir_schema.py` — IR schema v0.2 (this RFC)
- `src/axon/ir_compiler.py` — IR compiler (this RFC)
- `examples/` — full language surface examples

### Foundational project documents
- `README.md` — project overview, primitives, current capabilities
- `ROADMAP.md` — Phase 1/2 roadmap, runtime RFC process
- `RUNTIME_PLAN.md` — runtime-plan workflow (inspection-only JSON summaries)
- `RUNTIME_BOUNDARY.md` — execution boundary between compiler and runtime
- `EXPRESSION_PARSER.md` — expression AST nodes and static analysis
- `TYPE_SYSTEM_GUIDE.md` — primitives, generics, unions, records
- `FOUNDATION_AUDIT.md` — Phase 1 foundation checkpoint

### Early runtime RFCs (IR coverage verified)
- `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md` — non-executing boundary (RFC #001)
- `docs/runtime-rfcs/0004-minimal-executing-agent-runtime.md` — agent execution (RFC #004)
- `docs/runtime-rfcs/0005-flow-execution-engine.md` — flow DAG execution (RFC #005)
- `docs/runtime-rfcs/0006-rag-indexing-retrieval-runtime.md` — RAG indexing/retrieval (RFC #006)
- `docs/runtime-rfcs/0007-trace-replay-runtime.md` — trace replay (RFC #007)
- `docs/runtime-rfcs/0008-multi-agent-message-passing-runtime.md` — multi-agent messaging (RFC #008)
- `docs/runtime-rfcs/0009-persistent-agent-memory.md` — persistent memory (RFC #009)

### External references
- WASI — https://wasi.dev
- Capability-based security — https://en.wikipedia.org/wiki/Capability-based_security
