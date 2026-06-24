# AXON Example Cookbook

**Version:** 1.0  
**License:** MIT

A practical guide to writing AXON programs, organized by pattern. Each recipe is self-contained and can be copied directly into a `.ax` file.

---

## Table of Contents

1. [Hello World](#1-hello-world)
2. [Typed Records and Unions](#2-typed-records-and-unions)
3. [Prompt Templates](#3-prompt-templates)
4. [RAG Knowledge Base](#4-rag-knowledge-base)
5. [Agent with Memory](#5-agent-with-memory)
6. [Multi-Stage Flows](#6-multi-stage-flows)
7. [GitHub Issue Triage](#7-github-issue-triage)
8. [Customer Support with RAG + Escalation](#8-customer-support-with-rag--escalation)
9. [Invoice Extraction Pipeline](#9-invoice-extraction-pipeline)
10. [Meeting Notes Agent](#10-meeting-notes-agent)
11. [Monitoring and Alerting](#11-monitoring-and-alerting)
12. [Data Analysis Agent](#12-data-analysis-agent)
13. [Multi-Agent Debate](#13-multi-agent-debate)
14. [Multi-Agent Memory Sharing](#14-multi-agent-memory-sharing)
15. [Research Pipeline (Full Showcase)](#15-research-pipeline-full-showcase)
16. [Trace Preview and Debugging](#16-trace-preview-and-debugging)

---

## 1. Hello World

The minimal AXON program: one tool, one agent.

```axon
tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]

    fn run(q: Str) -> Str { q }
}
```

**Key points:**
- Every tool needs at least one `///` docstring line
- Agents require `model:` and at least one `fn` method
- String interpolation with `{name}` works in tool bodies

**Run it:**
```bash
axon run examples/hello.ax --query "world"
```

---

## 2. Typed Records and Unions

AXON's type system catches mismatches at compile time.

```axon
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

**Patterns:**
- Simple alias: `type X = Str`
- Union: `type X = "a" | "b" | "c"`
- Record: `type X = { field: Type, ... }`
- Generic: `type X<T> = { items: List<T>, ... }`

---

## 3. Prompt Templates

Prompts are typed LLM templates with budget controls.

```axon
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
```

**Key points:**
- Template body is triple-quoted
- `{variable}` interpolation references parameters
- `@budget(tokens: N)` controls max token spend
- Default values: `tone: "friendly" | "formal" = "friendly"`
- The validator checks that template variables match parameter names

---

## 4. RAG Knowledge Base

Define retrieval-augmented generation pipelines declaratively.

```axon
import { Chunk } from "axon:types"

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

**Required fields:** `source`, `chunker`, `embedder`, `store`  
**At least one `fn` method is required.**

**Using RAG in an agent:**
```axon
agent SupportAgent {
    model: @anthropic/claude-4
    tools: [ProductDocs.retrieve, CreateTicket]

    fn handle(question: Str) -> Result<Str, AgentError> {
        let context = act ProductDocs.retrieve(query: question)?
        Ok(@answer(question, using: context))
    }
}
```

RAG methods are referenced as `RagName.methodName` in the tools list.

---

## 5. Agent with Memory

Three memory kinds for different use cases:

```axon
// Short-term working memory (limited capacity)
agent TriageAgent {
    model: @anthropic/claude-haiku
    tools: [FetchIssues]
    memory: Memory<ShortTerm>(capacity: 1000)

    fn triage(repo: Str) -> Result<(), AgentError> {
        store memory.working["last_run"] = "2024-01-01"
        Ok(())
    }
}

// Semantic memory (persistent knowledge)
agent KnowledgeAgent {
    model: @anthropic/claude-4
    tools: []
    memory: Memory<Semantic>

    fn learn(key: Str, value: Str) -> Str {
        store memory[key] = value
        "stored"
    }
}

// Episodic memory (event log)
agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch]
    memory: Memory<Episodic>(max_events: 500)

    fn investigate(query: Str) -> Result<Str, AgentError> {
        let results = act WebSearch(query: query)?
        store memory.append({ query, results })
        Ok(results)
    }
}
```

---

## 6. Multi-Stage Flows

Flows connect stages into pipelines with `->` arrows.

```axon
import { Chunk } from "axon:types"

flow AnswerFlow(question: Str) -> Str {
    stage Retrieve(query: Str) -> List<Chunk>
    stage Answer(chunks: List<Chunk>, question: Str) -> Str

    Retrieve -> Answer
}
```

**Linear chain:**
```axon
Plan -> Investigate -> Summarize -> Verify -> Compile
```

**Fan-in (multiple stages feed one):**
```axon
[Pro, Con] -> Synthesize
```

**Key points:**
- Each stage has typed parameters and return type
- The orchestration body uses `->` to connect stages
- The validator checks for duplicate stage names and undeclared references

---

## 7. GitHub Issue Triage

A practical agent that fetches issues, classifies them with an LLM, and applies labels.

```axon
import { now } from "axon:time"

type Issue = {
    number: Int,
    title: Str,
    body: Str,
    labels: List<Str>,
    author: Str
}

type IssueDecision = {
    priority: "low" | "medium" | "high" | "critical",
    assignee: Str,
    rationale: Str
}

prompt ClassifyIssue(issue: Issue, team_context: Str, @budget(tokens: 700)) -> IssueDecision {
    """
    Classify this GitHub issue and choose an assignee.

    Issue title: {issue.title}
    Issue body: {issue.body}
    Team context: {team_context}

    Return priority, assignee, and rationale.
    """
}

tool FetchOpenIssues(repo: Str, max_results: Int = 25) -> Result<List<Issue>, ToolError> {
    /// Fetches open GitHub issues from a repository.
    github.list_issues(repo, state: "open", limit: max_results)
}

tool AddIssueLabel(repo: Str, issue_number: Int, label: Str) -> Result<Bool, ToolError> {
    /// Adds one label to a GitHub issue.
    github.add_label(repo, issue_number, label)
}

tool AssignIssue(repo: Str, issue_number: Int, assignee: Str) -> Result<Bool, ToolError> {
    /// Assigns a GitHub issue to a team member.
    github.assign_issue(repo, issue_number, assignee)
}

agent GitHubTriageAgent {
    model: @anthropic/claude-haiku
    tools: [FetchOpenIssues, AddIssueLabel, AssignIssue]
    memory: Memory<ShortTerm>(capacity: 1000)

    fn triage(repo: Str, team_context: Str) -> Result<(), AgentError> {
        think "Fetch untriaged issues and classify them"
        let issues = act FetchOpenIssues(repo: repo, max_results: 25)?
        store memory.working["last_triage_run"] = now().iso8601()

        for issue in issues {
            let decision = model.complete(ClassifyIssue(issue, team_context))
            act AddIssueLabel(repo: repo, issue_number: issue.number, label: decision.priority)?
            act AssignIssue(repo: repo, issue_number: issue.number, assignee: decision.assignee)?
        }

        Ok(())
    }
}
```

**Patterns used:** imports, type aliases, prompt with budget, three tools, agent with short-term memory, `think` reasoning, `for` loop, `act` with `?` error propagation, `store memory` writes.

---

## 8. Customer Support with RAG + Escalation

RAG-powered support agent that escalates to human tickets when confidence is low.

```axon
import { Chunk } from "axon:types"

type SupportResponse = {
    answer: Str,
    confidence: Float,
    escalated: Bool
}

rag ProductDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./data/product_docs.db")

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(chunk => chunk.score > 0.72)
    }
}

prompt AnswerFromDocs(question: Str, context: List<Chunk>, @budget(tokens: 900)) -> SupportResponse {
    """
    Answer the customer question using only the retrieved documentation.

    Question: {question}
    Context: {context}

    Return answer, confidence, and whether escalation is required.
    """
}

tool CreateSupportTicket(title: Str, description: Str, priority: "low" | "medium" | "high" = "medium") -> Result<Str, ToolError> {
    /// Creates a support ticket in the service desk.
    http.post(env.SUPPORT_TICKET_API, { title, description, priority })
}

agent CustomerSupportAgent {
    model: @anthropic/claude-4
    tools: [ProductDocs.retrieve, CreateSupportTicket]
    memory: Memory<Semantic>

    fn handle(question: Str) -> Result<SupportResponse, AgentError> {
        let context = act ProductDocs.retrieve(query: question, top_k: 5)?
        store memory.working["last_question"] = question
        let response = model.complete(AnswerFromDocs(question, context))

        if response.escalated {
            act CreateSupportTicket(title: question, description: response.answer, priority: "medium")?
        }

        Ok(response)
    }
}
```

**Patterns used:** RAG with SQLite store, prompt returning a structured type, conditional escalation, semantic memory, `if` branching.

---

## 9. Invoice Extraction Pipeline

Document processing agent that reads PDFs, extracts structured data, and archives files.

```axon
type InvoiceLine = {
    description: Str,
    quantity: Float,
    unit_price: Float,
    amount: Float
}

type InvoiceRecord = {
    vendor: Str,
    invoice_number: Str,
    invoice_date: Str,
    total: Float,
    lines: List<InvoiceLine>
}

prompt ExtractInvoice(pdf_text: Str, @budget(tokens: 1200)) -> InvoiceRecord {
    """
    Extract a structured invoice record from this text.

    PDF text:
    {pdf_text}

    Return vendor, invoice number, invoice date, total, and line items.
    """
}

tool ReadPDF(path: Str) -> Result<Str, ToolError> {
    /// Reads a PDF invoice and returns extracted text.
    fs.read_pdf(path)
}

tool InsertInvoice(record: InvoiceRecord) -> Result<Bool, ToolError> {
    /// Inserts a structured invoice record into the finance database.
    db.insert(env.FINANCE_DB, "invoices", record)
}

tool MoveFile(path: Str, destination: Str) -> Result<Bool, ToolError> {
    /// Moves a processed file to an archive or review folder.
    fs.move(path, destination)
}

agent InvoiceExtractionAgent {
    model: @anthropic/claude-4
    tools: [ReadPDF, InsertInvoice, MoveFile]
    memory: Memory<Episodic>(max_events: 10000)

    fn process(path: Str) -> Result<InvoiceRecord, AgentError> {
        let pdf_text = act ReadPDF(path: path)?
        let record = model.complete(ExtractInvoice(pdf_text))
        act InsertInvoice(record: record)?
        act MoveFile(path: path, destination: "./archive")?
        store memory.append(record)
        Ok(record)
    }
}
```

**Patterns used:** nested record types, prompt with high token budget, file I/O tools, database insertion, episodic memory for audit trail.

---

## 10. Meeting Notes Agent

Audio transcription → summary → action items → save to workspace.

```axon
type ActionItem = {
    owner: Str,
    task: Str,
    deadline: Str
}

type MeetingNotes = {
    summary: Str,
    decisions: List<Str>,
    action_items: List<ActionItem>
}

prompt SummarizeTranscript(transcript: Str, audience: Str = "general", @budget(tokens: 700)) -> Str {
    """
    Summarize the meeting transcript for a {audience} audience.

    Transcript:
    {transcript}
    """
}

prompt ExtractActionItems(transcript: Str, @budget(tokens: 500)) -> List<ActionItem> {
    """
    Extract action items from this meeting transcript.

    Transcript:
    {transcript}
    """
}

tool TranscribeAudio(audio_path: Str) -> Result<Str, ToolError> {
    /// Transcribes an audio file into text.
    audio.transcribe(audio_path)
}

tool SaveNotes(title: Str, notes: MeetingNotes) -> Result<Str, ToolError> {
    /// Saves meeting notes to a workspace page.
    notion.save(title, notes)
}

agent MeetingNotesAgent {
    model: @anthropic/claude-4
    tools: [TranscribeAudio, SaveNotes]
    memory: Memory<Episodic>(max_events: 5000)

    fn process(audio_path: Str, title: Str) -> Result<MeetingNotes, AgentError> {
        let transcript = act TranscribeAudio(audio_path: audio_path)?
        let summary = model.complete(SummarizeTranscript(transcript, audience: "engineering"))
        let action_items = model.complete(ExtractActionItems(transcript))
        let notes = MeetingNotes { summary, decisions: [], action_items }
        let url = act SaveNotes(title: title, notes: notes)?
        store memory.append(url)
        Ok(notes)
    }
}
```

**Patterns used:** two prompts for different LLM tasks, record construction with `MeetingNotes { ... }`, default parameter values, episodic memory.

---

## 11. Monitoring and Alerting

Scheduled agent that monitors service metrics and alerts on anomalies.

```axon
type Metrics = {
    service: Str,
    latency_ms: Float,
    error_rate: Float,
    cpu_percent: Float
}

type AnomalyReport = {
    severity: "info" | "warn" | "critical",
    summary: Str,
    metric: Str
}

prompt DetectAnomaly(metrics: Metrics, baseline: Str, @budget(tokens: 500)) -> AnomalyReport {
    """
    Detect whether the latest service metrics are anomalous.

    Metrics: {metrics}
    Baseline: {baseline}

    Return severity, summary, and metric.
    """
}

tool FetchMetrics(endpoint: Str) -> Result<Metrics, ToolError> {
    /// Fetches service metrics from a monitoring endpoint.
    http.get(endpoint) |> parse_json::<Metrics>()
}

tool SendAlert(channel: Str, message: Str, severity: "info" | "warn" | "critical") -> Result<Bool, ToolError> {
    /// Sends an operational alert to a channel.
    slack.post(channel, message, severity)
}

agent MonitoringAgent {
    model: @anthropic/claude-haiku
    tools: [FetchMetrics, SendAlert]
    memory: Memory<ShortTerm>(capacity: 500)

    @schedule(every: 5.minutes)
    @trace
    fn watch(endpoint: Str, channel: Str) -> Result<(), AgentError> {
        let metrics = act FetchMetrics(endpoint: endpoint)?
        let baseline = memory.get("baseline").unwrap_or("no baseline yet")
        let anomaly = model.complete(DetectAnomaly(metrics, baseline))

        if anomaly.severity == "critical" {
            act SendAlert(channel: channel, message: anomaly.summary, severity: "critical")?
        }

        store memory.working["last_metrics"] = metrics
        Ok(())
    }
}
```

**Patterns used:** `@schedule` and `@trace` annotations, `unwrap_or` for safe memory access, conditional alerting, `parse_json::<T>()` type conversion, lightweight model (`claude-haiku`) for cost efficiency.

---

## 12. Data Analysis Agent

Agent that reads CSVs, runs Python code in a sandbox, and generates charts.

```axon
type AnalysisReport = {
    question: Str,
    findings: List<Str>,
    chart_path: Str
}

tool ReadCSV(path: Str) -> Result<DataFrame, ToolError> {
    /// Reads a CSV file into a structured dataframe.
    fs.read(path) |> csv.parse::<DataFrame>()
}

tool RunPython(code: Str, context: Map<Str, Any> = {}) -> Result<Any, ToolError> {
    /// Executes Python code inside a sandboxed environment.
    sandbox.run_python(code, context)
}

tool PlotChart(data: DataFrame, title: Str, chart_type: "bar" | "line" | "scatter" | "auto" = "auto") -> Result<Str, ToolError> {
    /// Generates a chart and returns the chart file path.
    viz.plot(data, chart_type, title)
}

agent DataAnalysisAgent {
    model: @anthropic/claude-4
    tools: [ReadCSV, RunPython, PlotChart]
    memory: Memory<ShortTerm>(capacity: 2000)

    fn analyze(csv_path: Str, question: Str) -> Result<AnalysisReport, AgentError> {
        let df = act ReadCSV(path: csv_path)?
        let code = @generate("Python pandas code to answer: {question}")
        let stats = act RunPython(code: code, context: { df })?
        let chart = act PlotChart(data: df, title: question, chart_type: "auto")?
        store memory.working["last_stats"] = stats
        Ok(AnalysisReport { question, findings: [], chart_path: chart })
    }
}
```

**Patterns used:** `Map<Str, Any>` for flexible context, `@generate()` for LLM code generation, `csv.parse::<T>()` type conversion, record construction, default parameter values.

---

## 13. Multi-Agent Debate

Two-stage debate with a synthesis step.

```axon
type Argument = {
    position: Str,
    content: Str,
    confidence: Float
}

type DebateTranscript = {
    topic: Str,
    rounds: List<Argument>,
    conclusion: Str
}

agent DebaterAgent {
    model: @anthropic/claude-4
    tools: []
    memory: Memory<Episodic>(max_events: 2000)

    fn argue(position: Str, opponent_arg: Option<Str> = None, round: Int = 1) -> Result<Argument, AgentError> {
        let history = memory.recall_all()
        let argument = @argue(my_position: position, prior_rounds: history, counter: opponent_arg, round: round)
        store memory.append(argument)
        Ok(argument)
    }
}

flow DebatePipeline(topic: Str, rounds: Int = 3) -> DebateTranscript {
    stage Pro(round: Int) -> Argument
    stage Con(round: Int) -> Argument
    stage Synthesize(args: List<Argument>) -> DebateTranscript

    [Pro, Con] -> Synthesize
}
```

**Patterns used:** `Option<Str>` for optional parameters, `memory.recall_all()` for episodic recall, fan-in flow `[Pro, Con] -> Synthesize`, flow with default parameter.

---

## 14. Multi-Agent Memory Sharing

Agents that communicate via shared memory and message passing.

```axon
tool RememberFact(key: Str, value: Str) -> Str {
    /// Stores a fact in semantic memory.
    remember(key, value)
    "stored"
}

tool RecallFact(query: Str) -> Str {
    /// Recalls a fact from semantic memory.
    recall(query, 1)
}

tool SendMessage(to: Str, content: Str) -> Str {
    /// Sends a message to another agent.
    send(to, content)
    "sent"
}

tool ReceiveMessage() -> Str {
    /// Receives a message from another agent.
    receive()
}

agent Researcher {
    model: @mock/gpt
    tools: [RememberFact, RecallFact, SendMessage, ReceiveMessage]
    memory: Memory<Semantic>

    fn research(topic: Str) -> Str {
        let fact1 = "Neural networks are inspired by biological brains"
        let fact2 = "Backpropagation was invented in 1986"
        act RememberFact(key: "nn_bio", value: fact1)
        act RememberFact(key: "backprop", value: fact2)
        act SendMessage(to: "Writer", content: "Research complete on " + topic)
        "done"
    }
}

agent Writer {
    model: @mock/gpt
    tools: [RememberFact, RecallFact, SendMessage, ReceiveMessage]
    memory: Memory<Semantic>

    fn write(topic: Str) -> Str {
        let msg = act ReceiveMessage()
        let fact = act RecallFact(query: "neural")
        fact
    }
}

agent Coordinator {
    model: @mock/gpt
    tools: [RememberFact, RecallFact, SendMessage, ReceiveMessage]
    memory: Memory<Semantic>

    fn run(topic: Str) -> Str {
        delegate Researcher.research(topic: topic)
        delegate Writer.write(topic: topic)
    }
}

flow ResearchPipeline(topic: Str) -> Str {
    stage Research(topic: Str) -> Str
    stage Write(topic: Str) -> Str

    Research -> Write
}
```

**Patterns used:** `@mock/gpt` for testing without real API calls, `delegate` for agent-to-agent delegation, message passing tools, shared semantic memory, flow connecting two agents.

---

## 15. Research Pipeline (Full Showcase)

The comprehensive example demonstrating all AXON features together.

```axon
/// AXON Research Pipeline — A Multi-Agent Showcase
///
/// This example demonstrates AXON's multi-agent orchestration,
/// RAG integration, typed flows, and autonomous reasoning.

import { Chunk } from "axon:types"

type ResearchQuery = {
    topic: Str,
    depth: "quick" | "deep" = "quick"
}

type SearchResult = {
    source: Str,
    snippet: Str,
    relevance: Float
}

type FactCheckResult = {
    claim: Str,
    verdict: "confirmed" | "plausible" | "disputed" | "unverified",
    confidence: Float
}

type ResearchReport = {
    topic: Str,
    summary: Str,
    sources: List<SearchResult>,
    facts: List<FactCheckResult>,
    confidence: Float
}

tool WebSearch(query: Str, max_results: Int = 5) -> Result<List<SearchResult>, ToolError> {
    /// Search the web for relevant sources.
    http.get("https://api.search.example/v1", { q: query, limit: max_results })
        |> map(result => {
            source: result.url,
            snippet: result.snippet,
            relevance: result.score
        })
}

tool ExtractFacts(text: Str) -> Result<List<Str>, ToolError> {
    /// Extract factual claims from a text passage.
    @extract_claims(text)
}

rag ResearchDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 1024, overlap: 128)
    embedder: @openai/text-embed-3
    store: VectorDB::in_memory()

    fn retrieve(query: Str, top_k: Int = 3) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> filter(chunk => chunk.score > 0.65)
    }
}

agent QueryPlanner {
    model: @openai/gpt-4o-mini
    tools: [ResearchDocs.retrieve]

    fn plan(query: ResearchQuery) -> Result<List<Str>, AgentError> {
        /// Break a research topic into sub-queries.
        let context = act ResearchDocs.retrieve(query: query.topic)?
        let plan = @decompose(topic: query.topic, context: context, depth: query.depth)
        Ok(plan)
    }
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

agent SummarizerAgent {
    model: @anthropic/claude-haiku
    tools: []

    fn summarize(results: List<SearchResult>, topic: Str) -> Result<Str, AgentError> {
        /// Summarize research findings into a coherent narrative.
        let combined = results
            |> map(r => r.snippet)
            |> join("\n\n")

        let summary = @synthesize(topic: topic, sources: combined)
        Ok(summary)
    }
}

agent FactCheckerAgent {
    model: @openai/gpt-4o-mini
    tools: [WebSearch]

    fn verify(claim: Str) -> Result<FactCheckResult, AgentError> {
        /// Fact-check a single claim against the web.
        let evidence = act WebSearch(query: claim, max_results: 3)?
        let verdict = @verify_claim(claim: claim, evidence: evidence)

        observe "fact_check" { claim, verdict }
        Ok(verdict)
    }
}

flow ResearchPipeline(input: ResearchQuery) -> ResearchReport {
    stage Plan(q: ResearchQuery) -> List<Str>
    stage Investigate(queries: List<Str>) -> List<SearchResult>
    stage Summarize(results: List<SearchResult>) -> Str
    stage Verify(summary: Str) -> List<FactCheckResult>
    stage Compile(facts: List<FactCheckResult>, summary: Str, sources: List<SearchResult>) -> ResearchReport

    Plan -> Investigate -> Summarize -> Verify -> Compile
}

agent ResearchCoordinator {
    model: @anthropic/claude-4
    tools: []

    fn run(query: ResearchQuery) -> Result<ResearchReport, AgentError> {
        /// Coordinate the full research pipeline.
        think f"Starting research on: {query.topic} (depth: {query.depth})"

        let planner = spawn QueryPlanner()
        let plan = await planner.plan(query)?

        let worker_pool = pool(size: 3, target: ResearchAgent)
        let results = []
        for sub in plan {
            let result = await worker_pool.investigate(sub, query.depth)?
            results = results + result
        }

        let summarizer = spawn SummarizerAgent()
        let summary = await summarizer.summarize(results, query.topic)?

        let claims = act ExtractFacts(text: summary)?
        let checker = spawn FactCheckerAgent()
        let facts = []
        for claim in claims {
            let verdict = await checker.verify(claim)?
            facts = facts + [verdict]
        }

        Ok(ResearchReport { topic: query.topic, summary, sources: results, facts, confidence: 0.85 })
    }
}
```

**Patterns used (all of them):**
- File-level `///` doc comments
- Imports, type aliases, unions, generic types
- Tools with pipeline expressions and `map`
- RAG with in-memory store
- Four agents with different models and memory kinds
- `think`, `observe`, `store memory` keywords
- `spawn`, `await`, `pool` for async agent orchestration
- `for` loops, `act` with `?` error propagation
- Five-stage flow with linear pipeline
- `f"..."` interpolation strings
- `Ok()` result constructors
- Record construction with `ResearchReport { ... }`

---

## 16. Trace Preview and Debugging

Agent with trace instrumentation for debugging.

```axon
tool WebSearch(query: Str, max_results: Int = 5) -> Result<List<Any>, ToolError> {
    /// Searches the web for current information.
    http.get("https://api.search.example?q={query}&n={max_results}")
}

agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch]
    memory: Memory<ShortTerm>(capacity: 500)

    fn run(topic: Str) -> Result<(), AgentError> {
        think "Need to gather current information"
        let results = act WebSearch(query: topic, max_results: 5)?
        observe results: [{ title: "placeholder" }]
        store memory.working["results"] = results
        Ok(())
    }
}
```

**Debug commands:**
```bash
# Run and generate a trace
axon run examples/trace_preview.ax --query "AI agents" --trace trace.axontrace

# Analyze the trace
axon debug trace.axontrace

# Profile performance
axon profile trace.axontrace --json
```

**Key points:**
- `think` logs appear in the trace timeline
- `observe` logs structured data for inspection
- The debugger shows tool calls, token usage, and timing
- The profiler outputs JSON for CI integration

---

## Appendix: Common Patterns Quick Reference

| Pattern | Syntax |
|---------|--------|
| Error propagation | `act ToolName(...)?` |
| Pipeline | `data \|> function(args)` |
| Variable binding | `let x = expr` |
| Conditional | `if condition { ... }` |
| Loop | `for item in list { ... }` |
| Agent spawn | `let a = spawn AgentName()` |
| Async wait | `let r = await a.method()?` |
| Worker pool | `pool(size: N, target: AgentName)` |
| Memory write | `store memory.working["key"] = value` |
| Memory append | `store memory.append(event)` |
| Reasoning trace | `think "message"` |
| Observation | `observe "event" { data }` |
| Result success | `Ok(value)` |
| Model call | `model.complete(PromptName(args))` |
| LLM synthesis | `@function_name(args)` |
| Record construction | `TypeName { field: value, ... }` |

---

*The cookbook covers every example in the AXON repository. For the full language specification, see [LANGUAGE_SPEC.md](LANGUAGE_SPEC.md). For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).*
