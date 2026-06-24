# AXON Language Specification — v0.1
> **Phase 0 Draft — Syntax Validation**
> Status: Iterating on syntax only. No compiler exists yet.
> Goal: Validate that the syntax feels natural to both humans and LLMs before building the parser.

---

## 1. Design Principles

1. **Readable by both humans and LLMs.** An LLM should be able to write valid AXON from this spec alone. A developer should read any `.ax` file and understand what the agent does without documentation.
2. **Grounded in the five agent primitives.** Every keyword maps to one of: Perceive, Recall, Reason, Act, or Learn. Nothing exists outside this model.
3. **Explicit over implicit.** Tool calls are marked with `act`. LLM operations are marked with `@`. Memory writes use `store`. Nothing is hidden in magic.
4. **Compile-time safety first.** Token budgets, schema correctness, and type mismatches are errors at parse time, not runtime surprises.
5. **Provider-agnostic.** No `.ax` file contains logic coupled to a specific provider. Provider names appear only in configuration fields and `axon.toml`.
6. **Fail loudly.** `Result<T, E>` everywhere. No hidden exceptions. Every error surface is explicit.
7. **AEL traces are first-class.** Every agent run produces a human-readable, machine-replayable AEL trace log.

---

## 2. File Structure

AXON source files use the `.ax` extension. A file contains top-level declarations in any order.

```
file         := declaration+
declaration  := agent_decl
             | tool_decl
             | prompt_decl
             | rag_decl
             | flow_decl
             | type_alias
             | import_stmt
```

### Import syntax

```axon
import WebSearch from "axon:tools/web"
import { WebSearch, WebFetch } from "axon:tools/web"
import { Chunk, Document } from "axon:types"
import SupportAgent from "./agents/support.ax"
```

Built-in packages:
- `axon:tools/web` — WebSearch, WebFetch
- `axon:tools/fs` — ReadFile, WriteFile, ListDir
- `axon:tools/exec` — RunPython, RunShell
- `axon:tools/db` — SQLQuery
- `axon:types` — Chunk, Document, Message, Context, Report
- `axon:errors` — AgentError, ToolError, ProviderError

---

## 3. Core Keywords Reference

| Keyword | Layer | Purpose |
|---------|-------|---------|
| `agent` | ADL | Define an autonomous agent |
| `tool` | ADL | Define a callable tool |
| `prompt` | ADL | Define a typed prompt template |
| `rag` | ADL | Define a retrieval-augmented pipeline |
| `flow` | ADL | Define a multi-stage orchestration pipeline |
| `model` | Field | Bind a language model provider |
| `memory` | Field | Declare agent memory type |
| `tools` | Field | Bind tool list to agent |
| `workers` | Field | Declare worker agent pool |
| `fn` | Both | Define a method or function |
| `act` | AEL | Invoke an external tool |
| `store` | AEL | Write a value to memory |
| `think` | AEL | Log reasoning (trace only) |
| `observe` | AEL | Name and log an observation |
| `go` | Both | Spawn async computation |
| `await` | Both | Wait for async result(s) |
| `chan` | Both | Declare a typed channel |
| `send` | Both | Send a value to a channel |
| `select` | Both | Multiplex across channels |
| `match` | Both | Pattern match on a value |
| `for` | Both | Iterate over a collection |
| `if` | Both | Conditional branch |
| `let` | Both | Bind an immutable value |
| `return` | Both | Return from a function |
| `import` | ADL | Import declarations |

---

## 4. Type System

### 4.1 Primitive Types
| Type | Description |
|------|-------------|
| `Str` | UTF-8 string |
| `Int` | 64-bit signed integer |
| `Float` | 64-bit floating point |
| `Bool` | `true` or `false` |
| `Bytes` | Raw byte array |

### 4.2 Collection Types
| Type | Description |
|------|-------------|
| `List<T>` | Ordered sequence |
| `Map<K, V>` | Key-value map |
| `Set<T>` | Unordered unique elements |
| `Tuple<A, B>` | Fixed-arity pair |

### 4.3 Result and Option Types
| Type | Description |
|------|-------------|
| `Option<T>` | `Some(T)` or `None` |
| `Result<T, E>` | `Ok(T)` or `Err(E)` |
| `Stream<T>` | Async sequence of T values |

### 4.4 AI-Domain Types
| Type | Fields |
|------|--------|
| `Token` | `UInt32` — a single LLM token |
| `Embedding` | `Vec<Float, N>` — dimensioned vector |
| `Chunk` | `content: Str, tokens: Int, score: Float, metadata: Map<Str, Any>` |
| `Document` | `content: Str, kind: Str, source: Str, metadata: Map<Str, Any>` |
| `Message` | `role: "user"\|"assistant"\|"system", content: Str` |
| `Context` | `messages: List<Message>, total_tokens: Int` |
| `Report` | `summary: Str, findings: List<Any>, sources: List<Str>` |
| `Task` | `id: Str, goal: Str, priority: Int, context: Any` |

### 4.5 Memory Types
| Type | Backing | Use case |
|------|---------|----------|
| `Memory<ShortTerm>` | In-process dict | Ephemeral working state |
| `Memory<Semantic>` | Vector database | Long-term knowledge retrieval |
| `Memory<Episodic>` | Ordered log | Conversation history, event replay |

### 4.6 String Interpolation
```axon
let name = "world"
let message = "Hello, {name}!"              // → "Hello, world!"
let query = "Find information about {topic} in {year}"
```

### 4.7 Literal Union Types
```axon
// Constrained string values checked at compile time
severity: "info" | "warn" | "critical"
tone: "formal" | "casual" | "technical"
```

---

## 5. Agent Definitions (ADL)

### 5.1 Basic Structure
```axon
agent AgentName {
    // Required
    model: @provider/model-name

    // Optional
    tools:   [Tool1, Tool2, RAGIndex.retrieve]
    memory:  Memory<Semantic>
    workers: WorkerAgent * 4

    // Methods (at least one required)
    fn primary_method(input: InputType) -> Result<OutputType, AgentError> {
        // method body
    }

    fn helper(param: Str) -> Str {
        // helper functions are private to the agent
    }
}
```

### 5.2 Model Binding Options
```axon
model: @anthropic/claude-4             // specific model
model: @anthropic/claude-haiku         // cheaper/faster tier
model: @openai/gpt-4o
model: @google/gemini-2-pro
model: @ollama/llama3                  // local, no API key
model: env.DEFAULT_MODEL              // resolved from environment

// Intelligent routing
model: Router {
    default:  @anthropic/claude-4,
    cheap:    @anthropic/claude-haiku,
    local:    @ollama/llama3,
    strategy: CostOptimized            // or: LatencyOptimized, QualityFirst
}
```

### 5.3 Memory Configuration
```axon
memory: Memory<ShortTerm>
memory: Memory<ShortTerm>(capacity: 4000.tokens)
memory: Memory<Semantic>
memory: Memory<Semantic>(store: VectorDB::postgres(env.PG_URL))
memory: Memory<Semantic>(store: VectorDB::sqlite("./local.db"))
memory: Memory<Episodic>(max_events: 10000)
```

### 5.4 Worker Pools
```axon
workers: WorkerAgent * 4
workers: WorkerAgent * env.WORKER_COUNT
```

---

## 6. Tool Definitions (ADL)

Tools connect agents to the external world. AXON auto-generates MCP tool schemas and JSON schemas from the type signatures.

### 6.1 Syntax
```axon
tool ToolName(
    required_param: Type,
    optional_param: Type = default_value
) -> ReturnType {
    /// One-line description of what this tool does.
    /// When the LLM should use it.
    /// What it returns and in what format.
    ///
    /// Extended description and examples if needed.

    implementation_body
}
```

### 6.2 Rules
- `///` docstrings are **required** and become the tool's MCP description
- The LLM reads docstrings to decide when to invoke each tool
- Return types must be fully specified — no `Any` returns
- Tool bodies use built-in modules: `http`, `fs`, `db`, `sandbox`, `slack`, `github`
- Tools must be **pure** — no side effects except through explicit return values

### 6.3 Built-in Modules Available in Tool Bodies
```axon
http.get(url) -> Result<Response, ToolError>
http.post(url, body) -> Result<Response, ToolError>
fs.read(path) -> Result<Str, ToolError>
fs.write(path, content) -> Result<(), ToolError>
db.query(conn, sql) -> Result<List<Row>, ToolError>
sandbox.run_python(code) -> Result<Any, ToolError>
slack.post(channel, message, severity) -> Result<Bool, ToolError>
github.post_review(repo, pr, review) -> Result<Bool, ToolError>
```

---

## 7. Prompt Types (ADL)

Prompts are typed, named templates that the compiler can statically analyse for token budget compliance.

### 7.1 Syntax
```axon
prompt PromptName(
    param1: Type,
    param2: Type = default,
    @budget(tokens: N)              // compile-time budget check
) -> ReturnType {
    """
    Template body.
    Variables interpolated as {param1} and {param2}.
    Multi-line supported.
    Return type tells the compiler what to expect.
    """
}
```

### 7.2 Usage
```axon
// Synchronous completion
let result: Str = model.complete(PromptName(value1, value2))

// Streaming completion
let stream: Stream<Str> = model.stream(PromptName(value1))

// Inline (anonymous) prompts
let answer = @think("What is the best approach for {goal}?")
```

### 7.3 Budget Enforcement
The `@budget` annotation causes the compiler to:
1. Estimate the maximum token size of all inputs at the call site
2. Add the prompt template's fixed token count
3. Raise a compile error if the sum may exceed the budget

---

## 8. Memory Operations

```axon
// ── WRITE ─────────────────────────────────────────────
store memory.key = value
store memory.working["topic"] = data
memory.append(event)                  // episodic: ordered append

// ── READ ──────────────────────────────────────────────
let val   = memory.get("key")                    // Option<T>
let val   = memory.get("key").unwrap_or(default) // with fallback
let chunks = memory.recall(query, top_k: 5)      // semantic search
let recent = memory.recent(n: 12)                // last N (episodic)
let all    = memory.recall_all()

// ── DELETE ────────────────────────────────────────────
memory.delete("key")
memory.clear()
```

---

## 9. RAG Blocks (ADL)

```axon
rag IndexName {
    // Source — file glob, URL, or query
    source: "./docs/**/*.pdf"
    // source: ["./specs/*.md", "./wiki/*.txt"]
    // source: db.query("SELECT content, id FROM docs")

    // Chunking strategy
    chunker: Chunker::sliding(size: 512, overlap: 64)
    // chunker: Chunker::sentence(max_tokens: 256)
    // chunker: Chunker::paragraph()

    // Embedding model
    embedder: @openai/text-embed-3
    // embedder: @ollama/nomic-embed-text   // local, free

    // Vector store
    store: VectorDB::sqlite("./index.db")
    // store: VectorDB::postgres(env.PG_URL)
    // store: VectorDB::chroma(env.CHROMA_URL)

    // Retrieval method (required)
    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(chunk => chunk.score > 0.72)
    }
}
```

**CLI commands:**
```bash
axon index IndexName          # build or update the index
axon index IndexName --watch  # watch for file changes
axon index --all              # rebuild all indexes in project
```

---

## 10. Flow Pipelines (ADL)

```axon
flow FlowName(input: InputType) -> OutputType {
    // Stage declarations
    stage Ingest(data: List<Document>) -> List<Chunk>
    stage Embed(chunks: List<Chunk>)   -> List<Chunk>
    stage Retrieve(query: Str)          -> List<Chunk>
    stage Generate(chunks: List<Chunk>, query: Str) -> OutputType

    // Sequential pipeline
    Ingest -> Embed -> Retrieve -> Generate

    // Parallel execution — both run concurrently, C waits for both
    [StageA, StageB] -> MergeStage

    // Conditional routing
    Retrieve -> match score {
        high => DirectAnswer,
        _    => EscalateToHuman
    }
}
```

---

## 11. AEL — Agent Execution Language

AEL is the imperative dialect that agents generate (and log) during execution. It can be written directly for deterministic replay and testing.

### 11.1 AEL Keywords
```axon
// Reasoning — logged in trace, not an external call
think "I should search for recent data on {topic}"

// Tool invocation — external call, logged with full args
act WebSearch(query: "climate 2025", max_results: 5)

// Observation — name an intermediate result
observe results: [{ title: "NASA Report", url: "https://..." }]

// Memory write
store memory.working["climate"] = results[0].snippet
```

### 11.2 AEL in Agent Methods
Inside `fn` bodies, you write normal imperative code. The compiler generates AEL traces automatically.

```axon
fn research(topic: Str) -> Result<Report, AgentError> {
    // These lines generate AEL trace entries automatically
    let results = act WebSearch(query: topic, max_results: 5)?
    store memory.working["results"] = results

    let summary = @summarize(results, style: "bullet_points")
    Ok(Report { summary, sources: results.map(r => r.url) })
}
```

### 11.3 Trace Log Format (JSONL)
```json
{"t":"think",   "content":"I need to search for...", "agent":"ResearchAgent", "ts":1234567890, "tokens":12}
{"t":"act",     "tool":"WebSearch", "args":{"query":"climate 2025"}, "ts":1234567891}
{"t":"observe", "name":"results", "count":5, "ts":1234567892}
{"t":"store",   "key":"working.results", "ts":1234567893}
{"t":"think",   "content":"Summarising findings...", "ts":1234567894, "tokens":8}
```

Traces are written to:
- Stdout (development)
- `./traces/{agent}_{timestamp}.jsonl` (file mode)
- OpenTelemetry endpoint (production)
- Any configured trace backend

---

## 12. Annotations

| Annotation | Target | Effect |
|-----------|--------|--------|
| `@budget(tokens: N)` | `prompt`, `fn` | Compile error if estimated tokens may exceed N |
| `@schedule(every: N.unit)` | `fn` | Register as a periodic job |
| `@trace` | `agent`, `fn` | Force full AEL trace logging |
| `@managed` | `agent`, block | Use GC memory (safe for long-running state) |
| `@retry(max: N, backoff: Ms)` | `fn`, `act` | Auto-retry on `ToolError` |
| `@timeout(Ms)` | `fn` | Raise `AgentError::Timeout` after Ms |
| `@cache(ttl: Seconds)` | `tool` | Cache result by input hash |

### Examples
```axon
@budget(tokens: 2000)
fn summarize(doc: Document) -> Str { ... }

@schedule(every: 5.minutes)
@trace
fn watch_metrics(endpoint: Str) -> Result<(), AgentError> { ... }

@retry(max: 3, backoff: 1000)
@timeout(30000)
act FetchData(url: env.DATA_URL)
```

**Schedule units:** `.seconds`, `.minutes`, `.hours`, `.days`

---

## 13. Concurrency Model

```axon
// Spawn async — non-blocking, returns Future<T>
let future  = go agent.run(task)
let futures = tasks |> map(t => go worker.execute(t))

// Await
let result  = await future
let results = await futures                    // List<Future<T>> → List<Result<T,E>>
let results = await futures timeout 120s       // with deadline

// Channels
chan<Task>   task_queue
chan<Report> result_stream

send task_queue task
let report = receive result_stream             // blocks until available

// Select — multiplex channels
select {
    msg from task_queue     => handle(msg),
    msg from priority_queue => handle_priority(msg),
    after 30s               => handle_timeout()
}
```

---

## 14. Error Handling

```axon
// Function returns Result
fn fetch(url: Str) -> Result<Response, ToolError> { ... }

// ? propagates Err immediately
let response = fetch(url)?

// Pattern match on Result
match fetch(url) {
    Ok(response)              => process(response),
    Err(ToolError::NotFound)  => handle_404(),
    Err(ToolError::Timeout)   => retry(),
    Err(e)                    => log_error(e)
}

// Option handling
let val = memory.get("key")           // Option<T>
let val = memory.get("key")?          // propagates None as Err
let val = memory.get("key").unwrap_or(default_value)
```

### Built-in Error Types
```axon
AgentError::BudgetExceeded(limit: Int, actual: Int)
AgentError::ProviderError(inner: ProviderError)
AgentError::ToolError(tool: Str, inner: ToolError)
AgentError::Timeout(after_ms: Int)
AgentError::MaxRetries(tool: Str, attempts: Int)
AgentError::ChannelClosed(channel: Str)

ToolError::NotFound
ToolError::Unauthorized
ToolError::Timeout
ToolError::ParseError(msg: Str)
ToolError::RateLimit(retry_after_ms: Int)
```

---

## 15. Provider Configuration

### 15.1 Provider Strings
```
@anthropic/claude-4
@anthropic/claude-3-5-sonnet
@anthropic/claude-haiku
@openai/gpt-4o
@openai/gpt-4o-mini
@openai/text-embed-3-large
@google/gemini-2-pro
@google/gemini-2-flash
@cohere/command-r-plus
@cohere/rerank-3
@ollama/llama3
@ollama/nomic-embed-text
```

### 15.2 axon.toml
```toml
[providers.anthropic]
api_key  = "${ANTHROPIC_API_KEY}"

[providers.openai]
api_key  = "${OPENAI_API_KEY}"

[providers.google]
api_key  = "${GOOGLE_API_KEY}"

[providers.cohere]
api_key  = "${COHERE_API_KEY}"

[providers.ollama]
base_url = "http://localhost:11434"    # no key required

[defaults]
model   = "@anthropic/claude-4"
embed   = "@openai/text-embed-3-large"
rerank  = "@cohere/rerank-3"
```

**Golden rule: API keys never appear in `.ax` files. Only `${ENV_VAR}` references in `axon.toml`.**

---

## 16. Reference Implementations

### 16.1 Research Synthesizer
```axon
import { WebSearch, WebFetch, Calculator } from "axon:tools/web"

agent ResearchAgent {
    model:  @anthropic/claude-4
    tools:  [WebSearch, WebFetch, Calculator]
    memory: Memory<Semantic>

    @budget(tokens: 4000)
    fn run(topic: Str, depth: Int = 3) -> Result<Report, AgentError> {
        let queries = @plan("Generate {depth} diverse search queries for: {topic}")

        for query in queries {
            let results = act WebSearch(query: query, max_results: 5)?
            store memory.working[query] = results
        }

        let context = memory.recall(topic, top_k: 10)
        Ok(@synthesize(context, format: Report))
    }
}
```

### 16.2 RAG Customer Support
```axon
rag ProductDocs {
    source:   "./knowledge_base/**/*.md"
    chunker:  Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store:    VectorDB::postgres(env.PGVECTOR_URL)

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(chunk => chunk.score > 0.72)
    }
}

tool CreateTicket(title: Str, priority: "low" | "medium" | "high") -> Result<Str, ToolError> {
    /// Creates a support ticket in the ticketing system.
    /// Use when no documentation answers the user's question.
    http.post(env.TICKET_API, { title, priority })
        |> parse_json::<{ id: Str }>()
        |> map(r => r.id)
}

agent SupportAgent {
    model: @anthropic/claude-sonnet
    tools: [ProductDocs.retrieve, CreateTicket]

    fn handle(question: Str) -> Result<Response, AgentError> {
        let context = act ProductDocs.retrieve(query: question)?

        if context.empty? {
            let ticket_id = act CreateTicket(title: question, priority: "medium")?
            return Ok(Response.escalate("Created ticket #{ticket_id}. We will follow up shortly."))
        }

        Ok(@answer(question, using: context, tone: "helpful and concise"))
    }
}
```

### 16.3 Multi-Agent Orchestrator
```axon
agent WorkerAgent {
    model: @anthropic/claude-haiku
    tools: [WebSearch, Calculator]

    fn execute(task: Task) -> Result<TaskResult, AgentError> {
        @complete(task)
    }
}

agent OrchestratorAgent {
    model:   @anthropic/claude-4
    workers: Pool<WorkerAgent>(size: 4)
    memory:  Memory<Semantic>

    fn run(goal: Str) -> Result<Report, AgentError> {
        let plan = @plan(goal, max_steps: 10)

        let futures = plan.tasks
            |> map(task => go workers.next().execute(task))

        let results = await futures timeout 120s?

        Ok(@synthesize(results, goal: goal))
    }
}
```

### 16.4 Code Review Agent
```axon
import { ReadFile } from "axon:tools/fs"

tool PostGitHubReview(
    repo:      Str,
    pr_number: Int,
    body:      Str,
    event:     "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
) -> Result<Bool, ToolError> {
    /// Posts a code review to a GitHub pull request.
    /// Use after analyzing all changed files in the PR.
    github.post_review(repo, pr_number, body, event)
}

agent CodeReviewer {
    model: @anthropic/claude-4
    tools: [ReadFile, PostGitHubReview]

    @budget(tokens: 8000)
    fn review(pr: PullRequest) -> Result<CodeReview, AgentError> {
        let files = pr.changed_files
            |> map(path => act ReadFile(path: path)?)

        let review = CodeReview {
            summary:     @summarize(files, style: "one paragraph"),
            issues:      @find_issues(files, categories: ["bug", "security", "performance"]),
            suggestions: @suggest_improvements(files, style: "actionable"),
            verdict:     @classify(files, categories: ["approve", "request_changes", "comment"])
        }

        act PostGitHubReview(
            repo:      pr.repo,
            pr_number: pr.number,
            body:      review.format_markdown(),
            event:     review.verdict.to_github_event()
        )?

        Ok(review)
    }
}
```

### 16.5 Data Analysis Agent
```axon
tool ReadCSV(path: Str) -> Result<DataFrame, ToolError> {
    /// Reads a CSV file into a structured DataFrame.
    /// Use to load tabular data for analysis.
    fs.read(path) |> csv.parse::<DataFrame>()
}

tool RunPython(
    code:    Str,
    context: Map<Str, Any> = {}
) -> Result<Any, ToolError> {
    /// Executes Python code in a sandboxed environment.
    /// Use for statistical analysis, aggregations, and data transforms.
    /// Context variables are injected into the Python scope.
    sandbox.run_python(code, context)
}

tool PlotChart(
    data:       DataFrame,
    chart_type: "bar" | "line" | "scatter" | "heatmap" | "auto",
    title:      Str
) -> Result<Image, ToolError> {
    /// Generates a data visualization from a DataFrame.
    /// Use after analysis to present findings visually.
    viz.plot(data, chart_type, title)
}

agent DataAnalyst {
    model: @anthropic/claude-4
    tools: [ReadCSV, RunPython, PlotChart]

    fn analyze(csv_path: Str, question: Str) -> Result<AnalysisReport, AgentError> {
        let df   = act ReadCSV(path: csv_path)?
        let code = @generate("Python pandas code to answer: {question}", schema: df.schema)
        let stats = act RunPython(code: code, context: { df })?
        let chart = act PlotChart(data: df, chart_type: "auto", title: question)?

        Ok(AnalysisReport {
            question,
            findings:      @interpret(stats, question),
            visualization: chart,
            methodology:   @explain("How I computed the above findings")
        })
    }
}
```

### 16.6 Meeting Notes Agent
```axon
prompt SummarizeTranscript(
    transcript: Str,
    audience:   Str = "general",
    @budget(tokens: 600)
) -> Str {
    """
    Summarize the following meeting transcript for a {audience} audience.
    Be concise. Maximum 3 paragraphs.

    Transcript:
    {transcript}
    """
}

prompt ExtractActionItems(
    transcript: Str,
    @budget(tokens: 400)
) -> List<ActionItem> {
    """
    Extract all action items from this meeting transcript.
    For each, identify: the owner (person responsible), the task, and the deadline if mentioned.
    Return structured data only.

    Transcript:
    {transcript}
    """
}

tool Transcribe(audio_path: Str) -> Result<Transcript, ToolError> {
    /// Transcribes an audio file to text using speech recognition.
    /// Supports .mp3, .mp4, .wav, .m4a formats.
    whisper.transcribe(audio_path)
}

tool SaveToNotion(title: Str, content: Str, page_id: Str) -> Result<Str, ToolError> {
    /// Creates or updates a Notion page with the given content.
    /// Returns the URL of the created page.
    notion.create_page(title, content, page_id)
}

agent MeetingNotesAgent {
    model: @anthropic/claude-4
    tools: [Transcribe, SaveToNotion]

    fn process(audio_path: Str, notion_page_id: Str) -> Result<MeetingNotes, AgentError> {
        let transcript = act Transcribe(audio_path: audio_path)?

        let notes = MeetingNotes {
            summary:      model.complete(SummarizeTranscript(transcript.text)),
            action_items: model.complete(ExtractActionItems(transcript.text)),
            decisions:    @extract(transcript.text, kind: "decisions_made"),
            attendees:    @extract(transcript.text, kind: "speaker_names"),
            date:         transcript.metadata.get("date").unwrap_or("unknown")
        }

        let url = act SaveToNotion(
            title:   "Meeting Notes — {notes.date}",
            content: notes.to_markdown(),
            page_id: notion_page_id
        )?

        Ok(notes)
    }
}
```

### 16.7 Monitoring Agent
```axon
tool FetchMetrics(endpoint: Str) -> Result<Metrics, ToolError> {
    /// Fetches system metrics (CPU, memory, latency, error rate) from an endpoint.
    /// Use on a schedule to monitor system health.
    http.get(endpoint) |> parse_json::<Metrics>()
}

tool SendAlert(
    channel:  Str,
    message:  Str,
    severity: "info" | "warn" | "critical"
) -> Result<Bool, ToolError> {
    /// Sends an alert to a Slack channel.
    /// Only call when anomalies exceed configured thresholds.
    slack.post(channel, message, severity)
}

agent MonitorAgent {
    model:  @anthropic/claude-haiku
    tools:  [FetchMetrics, SendAlert]
    memory: Memory<ShortTerm>(capacity: 500)

    @schedule(every: 5.minutes)
    @trace
    fn watch(endpoint: Str, thresholds: Thresholds) -> Result<(), AgentError> {
        let metrics = act FetchMetrics(endpoint: endpoint)?
        let history = memory.recent(n: 12)

        let anomalies = @classify(
            input:      metrics,
            baseline:   history,
            thresholds: thresholds
        )

        match anomalies.severity {
            "critical" => {
                act SendAlert(
                    channel:  "#ops-critical",
                    message:  @format_alert(anomalies, include: ["metric", "delta", "threshold"]),
                    severity: "critical"
                )?
            },
            "warn" => {
                act SendAlert(channel: "#ops", message: @format_alert(anomalies), severity: "warn")?
            },
            _ => {}
        }

        store memory.append(metrics)
        Ok(())
    }
}
```

### 16.8 Email Drafting Agent
```axon
tool SearchContacts(name: Str) -> Result<Contact, ToolError> {
    /// Searches the company contact directory for a person by name.
    /// Returns their email, role, and communication history summary.
    crm.find_contact(name)
}

tool ReadRecentEmails(from_email: Str, last_n: Int = 5) -> Result<List<Email>, ToolError> {
    /// Reads recent emails from a specific sender.
    /// Use to understand communication tone and context.
    gmail.fetch(from: from_email, limit: last_n)
}

prompt DraftEmail(
    recipient:    Str,
    purpose:      Str,
    context:      Str,
    tone:         "formal" | "friendly" | "direct" = "professional",
    @budget(tokens: 800)
) -> Str {
    """
    Draft an email to {recipient}.

    Purpose: {purpose}
    Tone: {tone}

    Context about this person and your relationship:
    {context}

    Write only the email body. No subject line. No greeting header.
    """
}

agent EmailAgent {
    model: @anthropic/claude-4
    tools: [SearchContacts, ReadRecentEmails]

    fn draft(purpose: Str, recipient_name: Str) -> Result<Email, AgentError> {
        let contact  = act SearchContacts(name: recipient_name)?
        let history  = act ReadRecentEmails(from_email: contact.email)?
        let context  = @summarize(history, focus: "communication style and key topics")
        let tone     = @infer_tone(history)

        Ok(Email {
            to:      contact.email,
            subject: @generate("Subject line for: {purpose}"),
            body:    model.complete(DraftEmail(
                recipient: recipient_name,
                purpose:   purpose,
                context:   context,
                tone:      tone
            ))
        })
    }
}
```

### 16.9 Software Architect Agent
```axon
import { ReadFile, WriteFile } from "axon:tools/fs"

tool SearchInternalDocs(query: Str) -> Result<List<Chunk>, ToolError> {
    /// Searches internal architecture documentation and past decisions.
    /// Use before proposing new system designs.
    internal_rag.retrieve(query, top_k: 8)
}

agent ArchitectAgent {
    model:  @anthropic/claude-4
    tools:  [ReadFile, WriteFile, SearchInternalDocs]
    memory: Memory<Semantic>

    @budget(tokens: 6000)
    fn design(requirements: Str) -> Result<SystemDesign, AgentError> {
        let existing   = act SearchInternalDocs(query: requirements)?
        store memory.working["requirements"] = requirements
        store memory.working["existing"]     = existing

        let components = @think("What components does this system need? Consider: {existing}")
        let interfaces = @think("How should these components communicate?")
        let tradeoffs  = @think("What are the key architectural decisions and their tradeoffs?")
        let risks      = @think("What are the top 3 risks in this design?")

        let design = SystemDesign {
            components,
            interfaces,
            tradeoffs,
            risks,
            diagram: @generate_mermaid(components, interfaces)
        }

        act WriteFile(path: "./docs/architecture/{requirements.slug}.md", content: design.to_md())?

        Ok(design)
    }
}
```

### 16.10 Multi-Agent Debate
```axon
agent DebaterAgent {
    model:  @anthropic/claude-4
    memory: Memory<Episodic>

    fn argue(
        position:     Str,
        opponent_arg: Option<Str> = None,
        round:        Int
    ) -> Result<Argument, AgentError> {
        let history = memory.recall_all()

        Ok(@argue(
            my_position:   position,
            prior_rounds:  history,
            counter:       opponent_arg,
            style:         "logical and evidence-based",
            round:         round
        ))
    }
}

flow DebatePipeline(topic: Str, rounds: Int = 3) -> DebateTranscript {
    let pro_agent = DebaterAgent(label: "Pro: {topic}")
    let con_agent = DebaterAgent(label: "Con: {topic}")
    let transcript = DebateTranscript::new(topic)

    for round in 1..=rounds {
        let last_pro = transcript.last_pro_arg()
        let last_con = transcript.last_con_arg()

        let pro_future = go pro_agent.argue(
            position:     "For: {topic}",
            opponent_arg: last_con,
            round:        round
        )
        let con_future = go con_agent.argue(
            position:     "Against: {topic}",
            opponent_arg: last_pro,
            round:        round
        )

        let [pro_arg, con_arg] = await [pro_future, con_future]?
        transcript.add_round(round, pro_arg, con_arg)
    }

    transcript
}
```

---

## 17. Syntax Decisions Log

### LOCKED IN ✓

| Decision | Rationale |
|----------|-----------|
| Braces `{}` for blocks | Explicit, better for tooling, familiar from Rust/Go |
| No semicolons | Newlines end statements (like Go) |
| `@prefix` for LLM operations | Unambiguously marks "calls the model" |
| `act` keyword for tool calls | Explicit, readable, shows up in traces |
| `store` keyword for memory writes | Explicit, never implicit side effects |
| `go` for async spawn | Familiar to Go developers, one syllable |
| `await` for async resolution | Familiar (JS/Python/Rust) |
| `///` for tool docstrings | Distinct from `//` comments, signals "LLM reads this" |
| `\|>` pipe operator | Indispensable for retrieval chains |
| `?` for error propagation | Consistent with Result<T,E>, from Rust |
| `@budget(tokens: N)` annotation | Compile-time, most valuable safety feature |
| `@provider/model-name` syntax | Clean, obvious, grep-able |
| Types: `Str`, `Int`, `Bool` | Capitalized, consistent with Swift/Kotlin |
| `fn` keyword | Rust/Swift/Kotlin — universal in modern systems languages |
| `Result<T, E>` and `Option<T>` | No null, explicit error handling everywhere |
| `Pool<T>(size: N)` | Explicit pool syntax instead of `* N` |
| `flow {}` blocks | Purely declarative with `->` arrows, no imperative loops |
| `Stream<T>` | Core primitive type for token streaming |
| Folder convention | Determines module namespace (like Python/Next.js), no `module` keyword |
| `@op` naming rules | Standardized to imperative verbs (`@think`, `@plan`, `@extract`, etc.) |

### STILL OPEN ⚠

| Question | Options | Notes |
|----------|---------|-------|
| Trace verbosity | How much to log by default vs with `@trace` | Affects performance |
| Multi-modal types | Where do `Image`, `Audio`, `Video` fit in the type system? | Needed for many real agents |

---

## 18. Open Questions for Phase 1 Iteration

1. **LLM readability test:** Can Claude, GPT-4o, and Gemini read this spec and write valid `.ax` files without any examples? This is the primary Phase 0 validation criterion.

2. **AEL clarity:** Does the `@think()` / `act` / `store` distinction feel natural when reading a trace log? Or does it feel like three different languages mixed together?

3. **RAG magic vs transparency:** Is `rag {}` with its implicit chunking/embedding/indexing too magical? Should users configure a RAG pipeline more explicitly using individual tool calls?

4. **Flow vs agent methods:** Are `flow {}` blocks pulling their weight, or should complex pipelines just be methods on an orchestrator agent?

5. **Error verbosity:** Is `Result<T, AgentError>` on every `fn` declaration too noisy? Would Kotlin-style checked exceptions be cleaner?

6. **The `@` built-ins:** What is the full exhaustive list of built-in `@` operations? Are they fixed in the spec or extensible by the runtime?

7. **Deployment model:** How does an AXON project deploy? As a Python package? As a Docker container? As an MCP server? The answer affects the CLI design.

---

## 19. Phase 1 Acceptance Criteria

Before building the parser, Phase 0 is complete when:

- [ ] Three different LLMs can write syntactically valid `.ax` files from this spec alone
- [ ] A developer unfamiliar with AXON can read any of the 10 reference files and explain what the agent does
- [ ] All 10 reference files are internally consistent (no syntax contradictions)
- [ ] The open questions list has been reduced to at most 3 items
- [ ] The type system covers all types needed by the 10 reference implementations

---

*AXON Language Specification v0.1 · Phase 0 Draft*
*Next: Phase 1 — tree-sitter grammar + Python transpiler*
