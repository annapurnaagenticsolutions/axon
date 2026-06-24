# AXON Language Specification

**Version:** 1.0  
**Status:** Prototype  
**License:** MIT

AXON is a typed domain-specific language for defining autonomous agent systems. It provides native primitives for agents, tools, prompts, RAG pipelines, typed flows, and memory — replacing framework boilerplate with declarative syntax that compiles to Python and TypeScript.

---

## 1. Design Principles

- **Declarative over imperative.** Describe *what* agents do, not *how* to wire them.
- **Typed by default.** Every parameter, return type, and field has a type. The compiler catches mismatches before runtime.
- **One source, multiple targets.** An `.ax` file compiles to a Python server, a TypeScript client, or a CI pipeline — no manual porting.
- **Tooling is a language concern.** Formatting, validation, dependency auditing, and smoke testing are built-in CLI commands, not external plugins.
- **Compiler core is stdlib-only.** The AXON compiler has zero runtime dependencies. Provider SDKs and external libraries live in optional extras.

---

## 2. Lexical Structure

### 2.1 Comments

| Syntax | Purpose |
|--------|---------|
| `// text` | Line comment — ignored by parser |
| `/// text` | Doc comment — attached to the enclosing declaration as documentation |

Line comments are stripped during parsing. Doc comments are collected into the `docstrings` field of the enclosing tool, method, or declaration body.

### 2.2 Identifiers

Identifiers start with a letter or underscore, followed by letters, digits, or underscores:

```
[A-Za-z_][A-Za-z0-9_]*
```

### 2.3 Keywords

| Keyword | Context |
|---------|---------|
| `import` | Module import |
| `type` | Type alias declaration |
| `tool` | Tool declaration |
| `prompt` | Prompt template declaration |
| `rag` | RAG knowledge base declaration |
| `flow` | Flow orchestration declaration |
| `agent` | Agent declaration |
| `fn` | Method declaration inside agents, RAG blocks |
| `stage` | Stage declaration inside flows |
| `let` | Variable binding |
| `for` | Loop |
| `if` | Conditional |
| `match` | Pattern match |
| `act` | Tool invocation |
| `think` | Reasoning trace |
| `observe` | Observation logging |
| `store` | Memory write |
| `spawn` | Agent instantiation |
| `await` | Async wait |
| `pool` | Worker pool creation |
| `Ok` | Success result constructor |
| `model` | Model field in agent |
| `tools` | Tools field in agent |
| `memory` | Memory field in agent |

### 2.4 Operators

| Operator | Purpose |
|----------|---------|
| `->` | Return type arrow, flow stage connection |
| `<-` | Channel receive (future) |
| `\|>` | Pipeline forward |
| `?` | Error propagation |
| `@` | Annotation prefix, model reference |
| `::` | Namespace/enum access |
| `\|` | Union type separator |

### 2.5 String Interpolation

Strings support `{variable}` interpolation:

```
"Hello, {name}!"
f"Found {len(results)} results for: {query}"
```

Prefix `f` strings are also supported for explicit interpolation.

---

## 3. Type System

### 3.1 Primitive Types

| Type | Description |
|------|-------------|
| `Str` | String |
| `Int` | Integer |
| `Float` | Floating-point number |
| `Bool` | Boolean |
| `()` | Unit (no value) |

### 3.2 Composite Types

| Syntax | Description |
|--------|-------------|
| `List<T>` | List of type T |
| `Result<T, E>` | Success (`Ok(T)`) or error (`Err(E)`) |
| `Option<T>` | Present or absent |
| `Dict<K, V>` | Key-value mapping |
| `{ field: T, ... }` | Record type |

### 3.3 Union Types

Discriminated unions via `|`:

```
type Priority = "low" | "medium" | "high"
type Verdict = "confirmed" | "plausible" | "disputed" | "unverified"
```

### 3.4 Generic Type Parameters

```
type PagedList<T> = {
    items: List<T>,
    total: Int,
    page: Int
}
```

### 3.5 Default Values

Parameters may have default values:

```
tool Search(query: Str, max_results: Int = 5) -> Result<List<Str>, ToolError> { ... }
```

---

## 4. Declarations

A `.ax` file is a sequence of top-level declarations. Declarations may be preceded by annotations.

### 4.1 Import

```
import { Chunk } from "axon:types"
import { now } from "axon:time"
import { WebSearch, WebFetch } from "axon:tools/web"
```

Imports bring types, tools, or utilities from AXON standard modules into scope.

### 4.2 Type Alias

```
type UserName = Str

type Priority = "low" | "medium" | "high"

type Issue = {
    id: Int,
    title: Str,
    priority: Priority,
    labels: List<Str>
}

type PagedList<T> = {
    items: List<T>,
    total: Int,
    page: Int
}
```

Type aliases define named types. Record types use `{ field: Type, ... }` syntax. Generic parameters use `<T>`.

### 4.3 Tool

```
tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

tool CreateTicket(
    title: Str,
    priority: "low" | "medium" | "high" = "medium"
) -> Result<Str, ToolError> {
    /// Creates a support ticket.
    /// Use when product documentation does not answer the user's question.
    http.post(env.TICKET_API, { title, priority })
}
```

Tools are typed functions that agents call. **Every tool must include at least one `///` docstring line** — this is enforced by the validator (`missing-tool-docstring`).

Tool bodies contain expressions: string literals, function calls, pipeline expressions, HTTP calls, etc.

### 4.4 Prompt

```
prompt DraftGreeting(
    name: Str,
    tone: "friendly" | "formal" = "friendly",
    @budget(tokens: 120)
) -> Str {
    """
    Write a {tone} greeting for {name}.
    Keep it short.
    """
}

prompt ClassifyIssue(
    issue: Issue,
    team_context: Str,
    @budget(tokens: 700)
) -> IssueDecision {
    """
    Classify this GitHub issue and choose an assignee.

    Issue title: {issue.title}
    Issue body: {issue.body}
    Team context: {team_context}

    Return priority, assignee, and rationale.
    """
}
```

Prompts are typed LLM template declarations. The body is a triple-quoted template string with `{variable}` interpolation. Parameters can include inline annotations like `@budget(tokens: N)`.

The validator checks:
- `@budget` annotations require a positive integer `tokens` argument
- Template variables must reference declared parameters

### 4.5 RAG

```
rag ProductDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::postgres(env.PGVECTOR_URL)

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(chunk => chunk.score > 0.72)
    }
}
```

RAG declarations define retrieval-augmented generation pipelines. Required fields:

| Field | Description |
|-------|-------------|
| `source` | Glob pattern or path to documents |
| `chunker` | Chunking strategy (e.g., `Chunker::sliding`) |
| `embedder` | Embedding model reference |
| `store` | Vector store backend |

A RAG block must define at least one `fn` method (typically `retrieve`). RAG methods are callable as tools by agents (e.g., `ProductDocs.retrieve`).

### 4.6 Flow

```
flow AnswerFlow(question: Str) -> Str {
    stage Retrieve(query: Str) -> List<Chunk>
    stage Answer(chunks: List<Chunk>, question: Str) -> Str

    Retrieve -> Answer
}

flow ResearchPipeline(input: ResearchQuery) -> ResearchReport {
    stage Plan(q: ResearchQuery) -> List<Str>
    stage Investigate(queries: List<Str>) -> List<SearchResult>
    stage Summarize(results: List<SearchResult>) -> Str
    stage Verify(summary: Str) -> List<FactCheckResult>
    stage Compile(facts: List<FactCheckResult>, summary: Str, sources: List<SearchResult>) -> ResearchReport

    Plan -> Investigate -> Summarize -> Verify -> Compile
}
```

Flows define multi-stage pipelines. Each `stage` has a name, typed parameters, and a return type. The orchestration body connects stages with `->` arrows.

The validator checks for:
- Duplicate stage names
- References to undeclared stages in the orchestration body

### 4.7 Agent

```
agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]

    fn run(q: Str) -> Str { q }
}

agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch, ResearchDocs.retrieve]
    memory: Memory<Episodic>(max_events: 500)

    fn investigate(sub_query: Str, depth: Str) -> Result<List<SearchResult>, AgentError> {
        /// Search and synthesize findings for a sub-query.
        let web_results = act WebSearch(query: sub_query, max_results: 5)?
        let docs = act ResearchDocs.retrieve(query: sub_query, top_k: 3)?

        think f"Found {len(web_results)} web results and {len(docs)} internal docs for: {sub_query}"

        store memory.append({ sub_query, web_results, docs })
        Ok(web_results)
    }
}
```

Agents are the core computational unit. Required fields:

| Field | Description |
|-------|-------------|
| `model` | LLM provider reference (e.g., `@anthropic/claude-4`) |
| `tools` | List of tool names available to the agent |
| `memory` | Optional memory declaration |

An agent must define at least one `fn` method. The validator checks:
- `model` must be present (`missing-agent-model`)
- At least one method (`missing-agent-method`)
- All referenced tools must exist (`unknown-agent-tool`)
- No duplicate tool references or method names

### 4.8 Memory

Memory is declared inside agents:

```
memory: Memory<ShortTerm>(capacity: 1000)
memory: Memory<Episodic>(max_events: 500)
memory: Memory<Semantic>(ttl: 3600)
```

Memory kinds: `ShortTerm`, `Semantic`, `Episodic`. Options vary by kind.

---

## 5. Annotations

Annotations attach metadata to declarations. They appear before the declaration:

```
@budget(tokens: 600)
@schedule(cron: "0 9 * * *")
@trace(enabled: true)
@managed
@retry(max: 3)
@timeout(seconds: 30)
@cache(ttl: 300)
```

Known annotations (validated by the compiler):

| Annotation | Scope | Description |
|------------|-------|-------------|
| `@budget` | Prompt | Token budget for LLM calls |
| `@schedule` | Agent, Flow | Cron-based execution schedule |
| `@trace` | Any | Enable execution tracing |
| `@managed` | Agent | Mark as managed by governance layer |
| `@retry` | Tool, Agent | Retry policy |
| `@timeout` | Tool, Agent | Timeout policy |
| `@cache` | Tool | Cache TTL for tool results |

Unknown annotations produce a warning (`unknown-annotation`).

---

## 6. Expressions

### 6.1 Tool Invocation

```
act WebSearch(query: sub_query, max_results: 5)?
```

The `act` keyword invokes a tool. The `?` operator propagates errors (short-circuits on `Err`).

### 6.2 Model Completion

```
let decision = model.complete(ClassifyIssue(issue, team_context))
let summary = @synthesize(topic: topic, sources: combined)
```

`model.complete()` calls the agent's LLM with a prompt template. `@fn()` calls are LLM-backed synthesis operations.

### 6.3 Pipeline

```
store.search(embed(query), top_k)
    |> rerank(query, model: @cohere/rerank-3)
    |> filter(chunk => chunk.score > 0.72)
```

The `|>` operator forwards the left-hand value as the first argument to the right-hand function.

### 6.4 Control Flow

```
for issue in issues {
    let decision = model.complete(ClassifyIssue(issue, team_context))
    act AddIssueLabel(repo: repo, issue_number: issue.number, label: decision.priority)?
}
```

### 6.5 Agent Spawning and Async

```
let planner = spawn QueryPlanner()
let plan = await planner.plan(query)?

let worker_pool = pool(size: 3, target: ResearchAgent)
let result = await worker_pool.investigate(sub, query.depth)?
```

- `spawn` creates an agent instance
- `await` waits for an async operation
- `pool` creates a worker pool of agent instances

### 6.6 Reasoning and Observation

```
think "Fetch untriaged issues and classify them"
think f"Starting research on: {query.topic} (depth: {query.depth})"

observe "fact_check" { claim, verdict }
```

- `think` logs a reasoning step (visible in traces)
- `observe` logs a structured observation event

### 6.7 Memory Operations

```
store memory.working["last_triage_run"] = now().iso8601()
store memory.append({ sub_query, web_results, docs })
```

### 6.8 Result Constructors

```
Ok(plan)
Ok(())
Ok(summary)
```

`Ok(value)` constructs a successful `Result`. `()` is the unit value for void results.

---

## 7. Model References

Model references use the `@provider/model` syntax:

| Reference | Provider |
|-----------|----------|
| `@anthropic/claude-4` | Anthropic Claude |
| `@anthropic/claude-haiku` | Anthropic Claude Haiku |
| `@openai/gpt-4o-mini` | OpenAI GPT-4o Mini |
| `@openai/text-embed-3` | OpenAI Embeddings |
| `@cohere/rerank-3` | Cohere Rerank |
| `@google/gemini-pro` | Google Gemini |

Provider SDKs are optional dependencies — the compiler core does not import them.

---

## 8. File-Level Doc Comments

A file may begin with `///` doc comments before the first declaration:

```
/// AXON Research Pipeline — A Multi-Agent Showcase
///
/// This example demonstrates AXON's multi-agent orchestration,
/// RAG integration, typed flows, and autonomous reasoning.
///
/// Run:  axon run examples/research_pipeline.ax --query "What is AXON?"

import { Chunk } from "axon:types"
```

These are treated as file-level documentation and skipped by the parser.

---

## 9. Validation Diagnostics

The AXON validator produces typed diagnostics:

| Code | Severity | Description |
|------|----------|-------------|
| `missing-tool-docstring` | error | Tool has no `///` docstring |
| `empty-tool-docstring-line` | warning | Tool has an empty `///` line |
| `missing-agent-model` | error | Agent has no `model:` field |
| `missing-agent-method` | error | Agent has no `fn` method |
| `unknown-agent-tool` | error | Agent references undefined tool |
| `duplicate-agent-tool` | warning | Agent lists same tool twice |
| `duplicate-agent-method` | error | Agent has duplicate method name |
| `duplicate-flow-stage` | error | Flow has duplicate stage name |
| `unknown-flow-stage` | warning | Flow body references undeclared stage |
| `missing-budget-tokens` | error | `@budget` missing `tokens` argument |
| `invalid-budget-tokens` | error | `@budget` tokens not a positive integer |
| `unknown-prompt-variable` | error | Prompt template references undeclared variable |
| `unknown-annotation` | warning | Annotation is not in the known set |
| `duplicate-import` | warning | Same name imported more than once |
| `duplicate-rag-method` | error | RAG block has duplicate method name |

---

## 10. Project Structure

```
my-project/
├── axon.toml              # Project configuration
├── examples/              # .ax source files
├── src/axon/              # Compiler source (if developing AXON itself)
├── tests/
│   ├── snapshots/
│   │   ├── examples/      # AST snapshots (*.ast.json)
│   │   └── formatted/     # Formatter snapshots (*.formatted.ax)
│   └── test_*.py          # Test suite
└── pyproject.toml         # Python package configuration
```

### 10.1 axon.toml

```
[defaults]
model = "@anthropic/claude-4"
```

The config file provides default model and project-wide settings.

---

## 11. CLI Commands

| Command | Description |
|---------|-------------|
| `axon compile <file> --target python` | Compile .ax to Python server code |
| `axon compile <file> --target typescript` | Compile .ax to TypeScript client |
| `axon syntax <file>` | Check syntax without validation |
| `axon validate <file>` | Run full validation |
| `axon run <file> --query "..."` | Execute an agent with a query |
| `axon format <file>` | Auto-format source code |
| `axon check-project [path]` | Run all quality gates |
| `axon dependency-audit [path]` | Audit import boundaries |
| `axon govern <file>` | Generate governance JSON |
| `axon ci-template --platform github-actions` | Generate CI workflow YAML |
| `axon explain <diagnostic-code>` | Explain a diagnostic in plain English |
| `axon task-template --number N --title "..."` | Generate a contributor task ticket |
| `axon debug <trace-file>` | Analyze an execution trace |
| `axon profile <trace-file> --json` | Profile trace performance |
| `axon serve-api` | Start the AXON API server |
| `axon add <file>` | Add a new .ax file from template |
| `axon remove <file>` | Remove a file and update snapshots |
| `axon eval <file>` | Evaluate agent outputs |
| `axon version` | Print version |
| `axon info` | Print environment info |

---

## 12. Compilation Targets

### 12.1 Python

The primary target. Compiles `.ax` files to Python server modules with:
- FastAPI endpoints for each agent
- Pydantic models for typed records
- Async tool execution
- Trace generation

### 12.2 TypeScript

Secondary target. Generates TypeScript client code with:
- Type interfaces matching AXON types
- API client functions
- Union types for discriminated unions

---

## 13. Standard Modules

| Module | Exports |
|--------|---------|
| `axon:types` | `Chunk`, core type definitions |
| `axon:time` | `now()`, time utilities |
| `axon:tools/web` | `WebSearch`, `WebFetch` |

---

## 14. Grammar Summary (EBNF-style)

```
file          = { file_doc_comment? declaration } ;
declaration   = import | type_alias | tool | prompt | rag | flow | agent ;
import        = "import" "{" names "}" "from" string ;
type_alias    = "type" ident [ type_params ] "=" type_value ;
tool          = "tool" ident "(" params ")" "->" type "{" body "}" ;
prompt        = "prompt" ident "(" prompt_params ")" "->" type "{" template "}" ;
rag           = "rag" ident "{" rag_fields { method } "}" ;
flow          = "flow" ident "(" params ")" "->" type "{" { stage } orchestration "}" ;
agent         = "agent" ident "{" agent_fields { method } "}" ;
method        = "fn" ident "(" params ")" "->" type "{" body "}" ;
stage         = "stage" ident "(" params ")" "->" type ;
annotation    = "@" ident [ "(" args ")" ] ;
type          = ident | "List" "<" type ">" | "Result" "<" type "," type ">" |
                "{" fields "}" | type "|" type | string ;
```

---

*AXON is a prototype language under active development. This specification describes the current implementation as of v1.0. Future phases will add live provider integration, distributed runtime, streaming, and advanced tool adapters.*
