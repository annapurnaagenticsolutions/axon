# AXON Architecture Deep-Dive

**Version:** 1.0  
**Status:** Prototype  
**License:** MIT

This document describes the internal architecture of the AXON compiler, runtime, and tooling. It is intended for contributors and anyone who wants to understand how AXON works under the hood.

---

## 1. System Overview

AXON is structured as a pipeline: source text enters at one end, passes through parsing, validation, and code generation, and emerges as runnable Python or TypeScript. A parallel runtime path executes compiled agents directly.

```
 .ax source
     │
     ▼
 ┌──────────┐     ┌────────────┐     ┌──────────────┐
 │  Parser  │────▶│ Validator  │────▶│  Codegen     │
 └──────────┘     └────────────┘     └──────────────┘
      │               │                     │
      │               │                     ├─▶ Python server
      │               │                     ├─▶ TypeScript client
      │               │                     ├─▶ Governance JSON
      │               │                     └─▶ MCP server
      │               │
      ▼               ▼
 ┌──────────┐   ┌────────────┐
 │ Formatter│   │ Type Checker│
 └──────────┘   └────────────┘
      │
      ▼
 ┌──────────────┐
 │  Snapshots   │
 └──────────────┘

 ┌─────────────────────────────────────────────────┐
 │                Runtime Layer                     │
 │  ┌───────┐  ┌────────┐  ┌───────┐  ┌─────────┐ │
 │  │Router │  │Runtime │  │Trace  │  │Governance│ │
 │  │       │  │Executor│  │Emitter│  │  Gates  │ │
 │  └───────┘  └────────┘  └───────┘  └─────────┘ │
 └─────────────────────────────────────────────────┘
```

---

## 2. Compiler Core

The compiler core is **stdlib-only**. No external dependencies. This is enforced by the dependency audit.

### 2.1 Parser (`parser.py`)

The parser is a hand-written recursive descent parser. It does not use a grammar generator — the grammar is small enough that direct code is clearer and produces better error messages.

**Entry point:** `parse(source: str, parse_expressions: bool = False) -> list[Declaration]`

**Responsibilities:**
- Tokenize and parse top-level declarations: `import`, `type`, `tool`, `prompt`, `rag`, `flow`, `agent`
- Handle annotations (`@name(args)`) and attach them to the next declaration
- Extract `///` doc comments from declaration bodies via `_extract_docstrings_and_body`
- Skip `//` line comments and whitespace via `_skip_ws_and_regular_comments`
- Parse balanced delimiters `()`, `{}`, `<>` via `_read_balanced_content`
- Optionally parse expression ASTs via `expression_parser.py`

**Output:** A list of dataclass instances from `ast_nodes.py`:
- `ImportDecl`, `TypeAliasDecl`, `ToolDecl`, `PromptDecl`, `RagDecl`, `FlowDecl`, `AgentDecl`

**Error handling:** Raises `SyntaxError` with line numbers on malformed input.

### 2.2 AST Nodes (`ast_nodes.py`)

All AST nodes are frozen dataclasses:

| Node | Fields |
|------|--------|
| `Param` | name, type_str, default |
| `Annotation` | name, args |
| `ToolDecl` | name, params, return_type, docstrings, body, annotations, line, parsed_body |
| `ImportDecl` | names, source |
| `TypeAliasDecl` | name, type_params, value, fields, line |
| `PromptDecl` | name, params, return_type, template, annotations, line |
| `MemoryDecl` | kind, options |
| `MethodDecl` | name, params, return_type, annotations, body, parsed_body |
| `RagDecl` | name, source, chunker, embedder, store, annotations, methods, line |
| `StageDecl` | name, params, return_type, line |
| `FlowDecl` | name, params, return_type, annotations, stages, body, parsed_body, line |
| `AgentDecl` | name, model, tools, memory, annotations, methods, workers, line |

### 2.3 Expression Parser (`expression_parser.py`)

Parses tool and method bodies into a typed expression AST (`expression_ast.py`). Supports:
- Literals (string, int, float, bool)
- Identifiers and field access
- Function calls with named arguments
- Pipeline (`|>`) expressions
- `let` bindings, `for` loops, `if`/`match` conditionals
- `act`, `think`, `observe`, `store`, `spawn`, `await`, `pool` keywords
- `Ok()` result constructors
- String interpolation

This is optional — the parser can run with `parse_expressions=False` to skip expression parsing and keep bodies as raw strings.

### 2.4 Validator (`validator.py`)

Runs semantic checks on parsed declarations. Produces typed `Diagnostic` objects with severity, message, code, line, and hint.

**Checks:**
- Tools must have `///` docstrings
- Agents must have `model:` and at least one `fn` method
- Agent tool references must resolve to defined tools or imports
- No duplicate method/tool/stage names
- `@budget` annotations require positive integer `tokens`
- Prompt template variables must reference declared parameters
- Flow stage references must resolve to declared stages
- Annotations must be in the known set

### 2.5 Type Checker (`type_checker.py`)

Performs static type analysis on parsed declarations and expression ASTs. Validates:
- Type compatibility of tool parameters and return types
- Record field types
- Union type membership
- Generic type parameter constraints
- Pipeline expression type flow

---

## 3. Code Generation (`codegen/`)

### 3.1 Python Codegen (in `cli.py`)

The primary compilation target. Generates a self-contained Python module with:
- FastAPI app with endpoints for each agent method
- Pydantic models for typed records
- Async tool execution wrappers
- Trace emission hooks
- Provider integration via `provider_plugin.py`

**Entry point:** `build_to_stdout(source_path) -> str`

### 3.2 TypeScript Codegen (`codegen/typescript.py`)

Generates TypeScript client code:
- Interfaces matching AXON types
- API client functions for agent methods
- Union types for discriminated unions
- Fetch-based HTTP calls

### 3.3 Governance Codegen (`codegen/governance.py`)

Generates governance JSON from AXON declarations:
- Infers domain from tools and agent name
- Extracts risk indicators and policy gates
- Produces a governance manifest compatible with AgentOps Mesh

### 3.4 MCP Codegen (`codegen/mcp.py`)

Generates an MCP (Model Context Protocol) server from AXON tools:
- Each tool becomes an MCP tool definition
- Agent methods become MCP resources
- RAG blocks become MCP knowledge sources

---

## 4. Runtime Layer

### 4.1 Runtime (`runtime.py`)

The execution engine for compiled AXON programs. Responsibilities:
- Resolve provider models (via `model_router.py`)
- Execute agent methods with tool calls
- Manage async execution context
- Emit trace events

### 4.2 Model Router (`model_router.py`)

Routes `@provider/model` references to actual provider implementations:
- `@anthropic/*` → `providers/anthropic_provider.py`
- `@openai/*` → `providers/openai_provider.py`
- `@mock/*` → `providers/mock_provider.py` (for testing)

Provider plugins implement a common interface (`provider_plugin.py`). The router falls back to mock providers when SDKs aren't installed.

### 4.3 Provider Plugins (`providers/`)

Each provider plugin wraps a vendor SDK:
- `anthropic_provider.py` — Anthropic Claude SDK
- `openai_provider.py` — OpenAI SDK
- `mock_provider.py` — Deterministic mock for testing

Providers are **optional** — the compiler core never imports them. They live in the `providers/` directory which is skipped by the dependency audit.

### 4.4 Flow Executor (`flow_executor.py`)

Executes flow pipelines by:
- Resolving stage dependencies from the orchestration body
- Running stages in topological order
- Passing typed outputs between stages
- Supporting parallel execution for fan-out patterns

### 4.5 Agent Lifecycle (`agent_lifecycle.py`)

Manages agent state transitions:
- `created` → `initialized` → `running` → `completed`/`failed`
- Checkpoint support via `checkpoint_manager.py`
- Graceful shutdown via `graceful_shutdown.py`
- Agent supervision via `agent_supervisor.py`

### 4.6 Worker Pool (`worker_pool.py`)

Manages pools of agent instances for parallel execution:
- `pool(size: N, target: AgentName)` creates N agent instances
- Work distribution across instances
- Result aggregation

### 4.7 Memory Store (`memory_store.py`)

In-memory and persistent memory backends:
- `ShortTerm` — working memory with capacity limit
- `Semantic` — long-term knowledge with TTL
- `Episodic` — event log with max_events

### 4.8 RAG Subsystem

| Module | Responsibility |
|--------|---------------|
| `rag_chunker.py` | Text chunking strategies (sliding window, sentence-based) |
| `rag_embedder.py` | Embedding generation via provider models |
| `rag_indexer.py` | Index management and search |
| `rag_registry.py` | RAG block registration and lookup |
| `vector_store.py` | Vector storage backends (in-memory, postgres) |

---

## 5. Observability

### 5.1 Trace System

| Module | Responsibility |
|--------|---------------|
| `trace.py` | Trace data structures and serialization |
| `trace_emitter.py` | Event emission during execution |
| `trace_context.py` | Thread-local trace context |
| `trace_reader.py` | Read and query trace files |
| `trace_extract.py` | Extract insights from traces |
| `trace_replayer.py` | Replay traces for debugging |

### 5.2 Debugger (`debugger.py`)

Analyzes `.axontrace` files:
- Step-through execution timeline
- Tool call inspection
- Token usage breakdown
- Error chain analysis

### 5.3 Profiler (`profiler.py`)

Performance profiling of traces:
- Per-stage timing
- Token consumption per agent
- Tool call latency distribution
- JSON output for CI integration

### 5.4 Metrics (`metrics.py`, `metrics_exporter.py`)

Runtime metrics collection and export:
- Prometheus-compatible metrics
- Per-agent, per-tool, per-flow dimensions
- Optional OTel/OTLP export via `otel_exporter.py` and `otlp_exporter.py`

---

## 6. Governance

### 6.1 Runtime Governance (`runtime_governance.py`)

Enforces policy gates during execution:
- Budget limits (token, cost, time)
- Tool allow/deny lists
- Approval workflows
- Audit trail generation

### 6.2 Governance Evidence (`runtime_governance_evidence.py`)

Collects and formats evidence for governance decisions:
- Tool call logs
- Model outputs
- Policy evaluation results

---

## 7. Infrastructure

### 7.1 API Server (`api_server.py`)

Optional FastAPI server that exposes compiled AXON agents via REST:
- `GET /health` — health check
- `POST /agents/{name}/{method}` — invoke agent method
- `GET /trace/{id}` — retrieve execution trace
- WebSocket support for streaming responses

### 7.2 Distributed Bus (`distributed_bus.py`)

Optional message bus for multi-node agent communication:
- Redis-backed pub/sub
- NATS-backed request/reply
- Channel-based agent-to-agent messaging

### 7.3 Service Registry (`service_registry.py`)

Registers and discovers AXON services across a cluster.

### 7.4 Secret Manager (`secret_manager.py`)

Manages API keys and credentials:
- Environment variable injection
- HashiCorp Vault integration (optional via `hvac`)
- OS keyring integration (optional via `keyring`)

### 7.5 Persistence (`persistence_store.py`, `postgres_store.py`)

Optional persistent storage backends:
- SQLite (default)
- PostgreSQL (optional via `psycopg`)

---

## 8. Tooling

### 8.1 Formatter (`formatter.py`)

Auto-formats `.ax` source code:
- Consistent indentation (4 spaces)
- Normalized spacing around operators
- Sorted import order
- Aligned record fields

### 8.2 Snapshots (`ast_snapshot.py`, `format_snapshot.py`)

Golden-file testing infrastructure:
- `ast_snapshot.py` — JSON snapshots of parsed ASTs
- `format_snapshot.py` — Formatted source snapshots

Snapshots ensure parser and formatter changes are intentional and reviewed.

### 8.3 Smoke Test (`smoke.py`)

End-to-end validation: parse → validate → compile → import → instantiate → execute with mock provider. Runs on every example file.

### 8.4 Check Project (`check_project.py`)

Project-level quality gate that runs:
- Syntax check on all `.ax` files
- Validation
- AST snapshot comparison
- Smoke test
- Config check

Excludes `snapshots/`, `fixtures/`, and standard vendor directories.

### 8.5 Dependency Audit (`dependency_audit.py`)

Enforces the stdlib-only compiler core rule:
- Scans all `src/axon/*.py` files for external imports
- Provider SDKs allowed only in `providers/` directory
- Optional runtime modules (fastapi, uvicorn, redis, etc.) allowed in designated optional files
- Checks `pyproject.toml` extras configuration
- Verifies no secrets in dependency declarations

### 8.6 Hygiene Checks (`hygiene.py`)

Project hygiene validation:
- Required files present (README, LICENSE, CHANGELOG)
- No debug artifacts committed
- Line ending consistency

### 8.7 LSP Server (`lsp_server.py`)

Language Server Protocol implementation for IDE integration:
- Diagnostics on save
- Go-to-definition
- Hover documentation
- Auto-formatting

### 8.8 Contributor Tools (`contributor.py`)

Task ticket generation for contributors:
- Self-contained implementation tickets
- JSON and Markdown output
- Validation commands included

---

## 9. Configuration (`config.py`)

Loads `axon.toml` project configuration:

```toml
[defaults]
model = "@anthropic/claude-4"

[providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"

[limits]
max_tokens = 4096
max_tools = 20
```

Provides `AxonConfig` dataclass with typed access to all settings.

---

## 10. Module Dependency Graph

```
parser.py ◀── ast_nodes.py
    │
    ├──▶ expression_parser.py ◀── expression_ast.py
    │
    ▼
validator.py ──▶ type_checker.py
    │
    ▼
codegen/
    ├── governance.py
    ├── mcp.py
    └── typescript.py
    │
    ▼
runtime.py
    ├── model_router.py ──▶ providers/*
    ├── flow_executor.py
    ├── agent_lifecycle.py
    ├── worker_pool.py
    ├── memory_store.py
    ├── rag_registry.py ──▶ rag_chunker.py, rag_embedder.py, rag_indexer.py
    ├── trace_emitter.py
    └── runtime_governance.py
    │
    ▼
api_server.py (optional, requires fastapi+uvicorn)
distributed_bus.py (optional, requires redis/nats)
```

**Key invariant:** Nothing in the parser → validator → codegen path imports any external package. External dependencies are isolated in `providers/`, optional runtime files, and `codegen/mcp.py` (which requires `fastmcp` from the `serve` extra).

---

## 11. Testing Strategy

### 11.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_parser.py` | Parser declarations, error cases |
| `test_validator.py` | All diagnostic codes |
| `test_type_checker.py` | Type compatibility rules |
| `test_formatter.py` | Formatting rules |
| `test_expression_parser.py` | Expression AST parsing |
| `test_dependency_audit.py` | Import boundary enforcement |

### 11.2 Corpus Tests

| Test File | Coverage |
|-----------|----------|
| `test_example_corpus.py` | Every `.ax` example: parse, validate, compile, smoke test, AST snapshot |
| `test_formatter_corpus.py` | Every example formats without errors |
| `test_formatter_snapshots.py` | Formatted output matches checked-in snapshots |

### 11.3 Integration Tests

| Test File | Coverage |
|-----------|----------|
| `test_check_project.py` | Full project quality gate |
| `test_contributor.py` | CLI task-template command |
| `test_ci_template_explain.py` | CI template generation, diagnostic explanation |
| `test_cli_help_consistency.py` | CLI help text matches expected commands |
| `test_governance_codegen.py` | Governance JSON generation |

### 11.4 Snapshot Strategy

AST and formatter snapshots are checked into `tests/snapshots/`. When the parser or formatter contract changes intentionally:
1. Regenerate snapshots using `source_file_to_snapshot_json()` / `write_format_snapshot_file()`
2. Review the diff
3. Commit the updated snapshots

Snapshots ensure that parser changes are visible in code review and not accidentally merged.

---

## 12. Extension Points

### 12.1 Adding a Provider

1. Create `src/axon/providers/<name>_provider.py`
2. Implement the provider interface from `provider_plugin.py`
3. Register in `provider_registry.py`
4. The dependency audit automatically skips `providers/` for external imports

### 12.2 Adding a CLI Command

1. Add a handler function in `cli.py`
2. Add a subparser in `_make_arg_parser()`
3. Add the command to `EXPECTED_COMMANDS` in `test_cli_help_consistency.py`
4. Write tests in a new `test_<command>.py` file

### 12.3 Adding a Validation Rule

1. Add a check function in `validator.py`
2. Define a diagnostic code
3. Add the code to the explain command's diagnostic dictionary in `cli.py`
4. Write a test in `test_validator.py`

---

*AXON's architecture prioritizes simplicity and correctness over feature breadth. The compiler core is small enough to read in an afternoon, and every extension point is documented with tests that enforce its contract.*
