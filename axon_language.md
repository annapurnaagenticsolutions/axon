This is a genuinely exciting design challenge. Let me think through this comprehensively — a language purpose-built for the Agentic AI era.

V

visualize

V

visualize show\_widget  
---

## **AXON — The AI-Native Language**

**AXON** (Agentic eXecution and Orchestration Notation) is the design concept. Here's the full vision:

---

### **The Core Philosophy**

Every other language treats AI/LLM calls as *library calls*. AXON treats **agents, tools, memory, and prompts as first-class language citizens** — the same way Go treats goroutines, or Rust treats ownership.

---

### **First-Class Language Keywords**

#### **`agent` — not a class, a runtime actor**

axon  
agent ResearchAgent {  
    memory: Memory\<Semantic\>         // typed memory  
    model: Model \= @openai/gpt-5    // model binding  
    tools: \[WebSearch, CodeRunner\]  // auto-schema generated

    fn run(goal: Str) \-\> Result\<Report, AgentError\> {  
        let plan \= @think("Break this goal into steps: {goal}")  
        for step in plan.steps {  
            let result \= @act(step)?    // tool dispatch  
            @reflect(result)            // self-correction loop  
        }  
        @synthesize(memory.recall\_all())  
    }  
}

#### **`tool` — auto-generates JSON schema, handles parsing**

axon  
tool WebSearch(query: Str, max\_results: Int \= 5\) \-\> List\<SearchResult\> {  
    /// Searches the web for current information.  
    /// Use when asked about recent events or facts.  
    http.get("https://search.api/v1?q={query}\&n={max\_results}")  
        |\> parse\_json::\<List\<SearchResult\>\>()  
}  
// No manual schema writing. AXON generates the tool definition from the  
// signature \+ docstring automatically.

#### **`prompt` — a first-class type with compile-time validation**

axon  
prompt SummarizeDoc\<T: Document\>(  
    doc: T,  
    style: Str \= "concise",  
    @budget(tokens: 800\)    // compile-time token budget annotation  
) \-\> Str {  
    """  
    Summarize the following {T.kind} in a {style} manner.  
    Focus on key insights. Max 3 paragraphs.

    Document: {doc.content}  
    """  
}

// Usage  
let summary \= model.complete(SummarizeDoc(my\_pdf, style: "technical"))

#### **`memory` — typed, queryable, persistent**

axon  
// Three built-in memory kinds  
let working  \= Memory\<ShortTerm\>(capacity: 8000.tokens)  
let longterm \= Memory\<Semantic\>(store: VectorDB::connect(env.PGVECTOR\_URL))  
let episodic \= Memory\<Episodic\>()   // session replay, ordered by time

// Storing  
longterm.store("User prefers Python examples", tags: \["preference"\])

// Querying (semantic search built in)  
let context \= longterm.recall("what does the user prefer?", top\_k: 5\)

#### **`flow` — orchestration pipeline as syntax**

axon  
flow ResearchPipeline {  
    stage Ingest   \-\> stage Chunk \-\> stage Embed \-\> stage Index  
    stage Query    \-\> stage Retrieve(top\_k: 10\) \-\> stage Rerank  
    stage Generate \-\> stage Validate \-\> stage Respond

    // Parallel branches  
    stage Retrieve branches \[WebSearch, LocalDocs, KnowledgeBase\]  
        then merge with RelevanceReranker  
}  
---

### **The RAG Block — Native, Not a Framework**

axon  
rag KnowledgeBase {  
    source: "./docs/\*\*/\*.pdf"  
    chunker: Chunker::sliding(size: 512, overlap: 64\)  
    embedder: Embedder::@openai/text-embed-3  
    store: VectorDB::postgres(env.DB\_URL)

    // Query time pipeline  
    fn retrieve(query: Str, top\_k: Int \= 8\) \-\> List\<Chunk\> {  
        let q\_embed \= embedder.embed(query)  
        store.similarity\_search(q\_embed, top\_k)  
            |\> rerank(query, model: @cohere/rerank-3)  
            |\> filter(score \> 0.72)  
    }  
}

// Usage — feels like a database query  
let chunks \= KnowledgeBase.retrieve("What is our refund policy?")  
let answer \= model.complete(prompt"""  
    Answer using only this context: {chunks.format()}  
    Question: {query}  
""")  
---

### **Multi-Agent Orchestration**

axon  
// Supervisor pattern — built into the language  
orchestrate MarketAnalysis {  
    supervisor: PlannerAgent  
    workers: \[  
        ResearchAgent \* 3,    // spin up 3 research agents  
        WriterAgent,  
        FactCheckerAgent  
    \]

    // Message passing — Go-style channels  
    chan\<Task\>   task\_queue  
    chan\<Result\> results

    fn run(topic: Str) \-\> Report {  
        supervisor.plan(topic) |\> task\_queue   // fan out  
        results |\> collect(timeout: 60s)       // fan in  
            |\> supervisor.synthesize()  
    }  
}  
---

### **Type System Highlights**

axon  
// AI-domain native types  
type Token    \= UInt32  
type Embedding \= Vec\<Float32, 1536\>   // dimension-checked at compile time  
type Chunk    \= { content: Str, tokens: Int, metadata: Map\<Str, any\> }  
type Context  \= { messages: List\<Message\>, total\_tokens: Int }

// Streaming as a first-class type  
type Stream\<T\> \= AsyncIterator\<T\>

fn stream\_response(prompt: Str) \-\> Stream\<Token\> {  
    model.stream(prompt)   // yields tokens as they arrive  
}

// Compile-time token budget enforcement  
@budget(max\_tokens: 4096\)  
fn summarize\_long\_doc(doc: Document) \-\> Str { ... }  
// Compiler ERROR if prompt \+ doc could exceed 4096 tokens  
---

### **Safety & Observability — Baked In**

axon  
// Every LLM call is automatically traced  
@trace(name: "research\_step", tags: \["agent", "llm"\])  
async fn research(query: Str) \-\> Str {  
    model.complete(prompt"""Find information about: {query}""")  
}  
// Automatically captures: latency, tokens used, cost, model, inputs/outputs  
// Exports to OpenTelemetry, Langfuse, or custom backends

// Built-in eval harness  
eval SummarizationQuality {  
    dataset: "./evals/summarization\_cases.jsonl"  
    metric: \[RougeL, SemanticSimilarity, Faithfulness\]  
    threshold: 0.85  
}  
// Run with: axon eval SummarizationQuality  
---

### **10–15 Year Sustainability Strategy**

Here's what makes AXON future-proof rather than just trendy:

**1\. Model-agnostic by design.** Models will change radically. AXON's `Model` type is a trait — any model (local, cloud, future architectures) implements it. You change one config line, not your codebase.

**2\. The abstractions will outlast the implementations.** "Agent with memory, tools, and a goal" is a pattern that will survive for decades, even if the underlying transformers are replaced. RAG as a pattern — retrieve \+ augment \+ generate — maps to any information retrieval paradigm.

**3\. Observability as a first-class citizen.** As agentic systems get more complex, debugging *why* an agent did something becomes critical. Languages that bake in tracing and eval survive; those that don't get replaced by frameworks that provide it.

**4\. Compile-time safety for AI.** Token budgets, schema validation for tools, type-checked embeddings — these prevent an entire class of runtime failures that currently plague Python-based agent frameworks.

**5\. Gradual adoption path.** Python bindings and a `@managed` escape hatch mean teams can migrate incrementally, not rewrite everything. This is how Go displaced C++ in infrastructure — not by being incompatible, but by being easy to adopt alongside.

---

### **Honest Challenges**

* **The ecosystem problem** is the biggest risk. Python wins because of `numpy`, `transformers`, `langchain`. AXON needs first-class Python FFI from day one, and a strategy to either wrap or replace those libraries.  
* **The spec stabilization problem** — AI APIs change weekly. The language spec must be stable even when model APIs aren't. The solution: model providers are plugins, not language features.  
* **Who builds it** — a language needs a company or foundation with a 10-year commitment. The closest analog is Mozilla \+ Rust, or Google \+ Go. Without institutional backing, it stays a research project.

---

### **The Closest Real Analogy**

**Mojo** showed that Python-syntax \+ systems performance is viable. AXON's bet is one level above: not "Python but fast" — but **"what if the language itself understood what an agent is"** the way SQL understood what a table is. SQL survived 50 years because it matched the domain perfectly. AXON's shot at longevity is the same — match the domain of intelligence orchestration so precisely that nothing else feels right.

## **You said: Query: how much overlap is with mojo design; is we prototype this?**

Query: how much overlap is with mojo design; is we prototype this? Challenge response: let's build strategy to wrap, I think it's best, will be a plug and play; spec: model providers are plugins; building: let's research and prototype, it'll be fun and later may be backed. What's your view ?

May 27

## **Claude responded: Great instincts — let me think through all three threads honestly and then map a real prototype strategy.**

Architected wrapper strategy, plugin ecosystem, and phased prototype roadmap  
Architected wrapper strategy, plugin ecosystem, and phased prototype roadmap

Great instincts — let me think through all three threads honestly and then map a real prototype strategy.

Here's the Mojo overlap picture first, because it actually clarifies everything else:

V

visualize

V

visualize show\_widget

The honest answer is the overlap is small and non-threatening — Mojo operates one level *below* AXON. Mojo is making the model call itself fast. AXON is about what happens *around* model calls. They could literally be used together.

Now the wrapper architecture — this is the smart move:

V

visualize

V

visualize show\_widget  
---

### **My honest view — and it's genuinely enthusiastic**

**The wrapper strategy is not a compromise. It's the historically proven path.** TypeScript didn't replace JavaScript by being a different runtime — it transpiled down and won by being the best developer experience layer. Kotlin didn't replace the JVM — it compiled to JVM bytecode and immediately got access to every Java library ever written. AXON can do exactly the same thing, and it's *faster to validate* because you get the ecosystem on day one.

---

### **The Provider Plugin Spec — get this right early**

This is the most critical design decision. Lock it in and the rest builds around it:

python  
\# axon-runtime/providers/base.py  
from typing import Protocol, Iterator, runtime\_checkable

@runtime\_checkable  
class ModelProvider(Protocol):  
    name: str                          \# "anthropic", "openai", etc.  
    models: list\[str\]                  \# \["claude-4", "claude-3-5-sonnet"\]

    def complete(  
        self,  
        messages: list\[Message\],  
        model: str,  
        max\_tokens: int \= 1000,  
        temperature: float \= 0.7,  
        \*\*kwargs  
    ) \-\> Response: ...

    def stream(  
        self,  
        messages: list\[Message\],  
        model: str,  
        \*\*kwargs  
    ) \-\> Iterator\[Token\]: ...

    def embed(  
        self,  
        text: str | list\[str\],  
        model: str  
    ) \-\> Embedding | list\[Embedding\]: ...

    def rerank(  
        self,  
        query: str,  
        documents: list\[str\],  
        model: str,  
        top\_n: int \= 5  
    ) \-\> list\[RankedResult\]: ...

Provider registration works like database drivers or Terraform providers:

python  
\# In any AXON project's axon.toml  
\[providers\]  
default \= "@anthropic/claude-4"  
fallback \= "@openai/gpt-4o"      \# automatic failover  
embed   \= "@openai/text-embed-3"  
rerank  \= "@cohere/rerank-3"

\# One line swap — zero code change

The key insight is that providers are **configuration, not code**. Your agent logic never imports `anthropic` or `openai` directly — it calls `model.complete()` and the runtime resolves the provider. This is exactly how JDBC works and it's why Java survived every database war.

---

### **Prototype Roadmap — concrete and fun**

#### **Phase 0 — "does the syntax feel right?" (2 weeks)**

Don't build a parser yet. Build it as a Python decorator-based DSL. This is the fastest way to discover what the syntax should actually *be*:

python  
from axon import agent, tool, prompt, memory, rag

@tool  
def web\_search(query: str, max\_results: int \= 5) \-\> list\[SearchResult\]:  
    """Searches the web. Use when you need current information."""  
    ...

@agent(model="@anthropic/claude-4", tools=\[web\_search\])  
class ResearchAgent:  
    knowledge: memory(kind="semantic")

    def run(self, goal: str) \-\> str:  
        ...

This is valid Python, immediately runnable, and lets you iterate on the abstraction feel before committing to grammar.

#### **Phase 1 — real transpiler (month 1–2)**

* Grammar in tree-sitter (ANTLR4 is an alternative but tree-sitter has better error recovery and GitHub uses it)  
* Emit Python from AXON syntax  
* CLI: `axon run`, `axon build`, `axon new`  
* `axon-runtime` PyPI package

#### **Phase 2 — provider system \+ memory (month 2–3)**

* `ModelProvider` protocol locked in  
* First party plugins: `axon-provider-anthropic`, `axon-provider-openai`, `axon-provider-ollama`  
* Memory types: `ShortTerm` (in-process), `Semantic` (wraps ChromaDB/pgvector), `Episodic` (SQLite)  
* `axon add provider anthropic` installs \+ registers

#### **Phase 3 — RAG \+ observability (month 3–4)**

* `rag {}` block compiles to retrieval pipeline  
* Auto-chunking, embedding, similarity search  
* Every LLM call automatically traced to OpenTelemetry  
* `axon trace` CLI shows last run's call graph with token costs

#### **Phase 4 — toolchain \+ community (month 4–6)**

* VS Code extension with syntax highlighting \+ autocomplete  
* `axon eval` command with built-in harness  
* Public package registry: `axon add agent github.com/you/research-agent`  
* TypeScript target begins

---

### **The honest hard parts**

Three things that will actually hurt during prototype:

**Streaming semantics across providers** — every provider streams differently. OpenAI sends delta chunks, Anthropic sends content blocks, Ollama does its own thing. The runtime has to normalize these into a single `Stream<Token>` abstraction without losing metadata (stop reasons, usage stats). Solvable, but fiddly.

**The `agent` loop semantics** — what does it mean for an agent to "run"? The runtime needs a default ReAct-style loop (think → act → observe → repeat) that's also overridable. Getting this abstraction right is the deepest design problem in the whole project.

**Vector store portability** — every vector DB has different query APIs, different indexing strategies, different metadata filters. The `Memory<Semantic>` type needs an abstraction layer here, similar to how SQLAlchemy abstracts SQL dialects.

---

### **The backing path**

The trajectory if it gains traction: open source it on day one → build a Discord → get 100 stars → write one killer blog post ("I built an agent framework that's 5x less code than LangChain") → that's enough for a seed round conversation or an Anthropic/Google labs partnership. Mojo's creator landed Modular after the community signal was clear. Same playbook available here.

**Bottom line:** yes, let's prototype it. The wrapper-first approach means you could have a working proof of concept in 2 weeks — literally a `pip install axon-runtime` moment — and discover what the syntax *actually* needs to feel like from real use, not speculation. That's the right order of operations. Want to start sketching the actual Phase 0 decorator DSL?

## **You said: one more thought, what if we build it as a MCP or MetaMCP language framework for both humans and AI/LLM.**

one more thought, what if we build it as a MCP or MetaMCP language framework for both humans and AI/LLM. I want to brainstorm multiple ideas, so we may have options and then think about effective and stable long term design like SQL, TypeScript, Kotlin. Your view?

May 27

## **Claude responded: This is where the thinking gets genuinely deep.**

Synthesized six design directions, evaluated stability principles, recommended unified architecture  
Synthesized six design directions, evaluated stability principles, recommended unified architecture

This is where the thinking gets genuinely deep. The MCP angle changes everything — it shifts AXON from "a language" to potentially "a protocol standard." Let me brainstorm the full option space first, then map which designs survive 15 years.

V

visualize

V

visualize show\_widget

The key synthesis insight: the strongest long-term design isn't any single option — it's C as the core, A as the deployment target, and E as the governance model. Here's what that unified architecture looks like in practice:

V

visualize

V

visualize show\_widget

## **You said: let's continue**

let's continue

May 27

## **Claude responded: Picking up right where the architecture landed — the diagram shows the what, but the most important question is why this design survives 15 years when every ot…**

Architected foundational model and prototype roadmap for AXON  
Architected foundational model and prototype roadmap for AXON

Picking up right where the architecture landed — the diagram shows the what, but the most important question is *why* this design survives 15 years when every other framework gets replaced. That answer lives in the foundational model underneath AXON.

V

visualize

V

visualize show\_widget  
---

### **Why this is actually SQL-level stable**

SQL didn't survive 50 years because it was a clever syntax. It survived because it maps to **relational algebra** — a mathematical model so fundamental to how data works that every database system, from Oracle to DuckDB to BigQuery, implements it regardless of SQL. The language outlasted mainframes, client-server, the web, and cloud because the underlying model didn't change. Tables, rows, queries — stable for half a century.

AXON's equivalent bet is those 5 primitives. Every agent system ever built — BDI agents from 1987, ReAct from 2023, whatever comes in 2030 — is a composition of Perceive, Recall, Reason, Act, and Learn. ReAct is literally `Reason → Act → Perceive → loop`. BDI is `Perceive → Recall (Beliefs) → Reason (Desires → Intentions) → Act`. Tree-of-Thought is `Reason × N → evaluate → Act`. The paradigms come and go; the primitives stay. If AXON maps to the primitives, paradigm shifts don't break it — they just generate new compositions of the same keywords.

The **TypeScript parallel** is about where the value actually lives. TypeScript didn't win because its compiler is brilliant. It won because the VS Code integration — real-time type errors, autocomplete across a 200,000-line codebase — made the alternative (raw JavaScript) feel dangerous. The value is in the tooling, not the language. AXON's TypeScript move is building the LSP server that gives you token budget warnings at edit time, type errors when your `prompt {}` references a variable that doesn't exist in scope, and inline cost estimates per tool call. The language is the vehicle. The tooling is the reason people adopt it.

The **Kotlin parallel** is interoperability. Kotlin won Android because it was 100% Java-interoperable — you could mix Kotlin and Java files in the same project, call any Java library, migrate a class at a time. AXON's equivalent: every existing MCP server is callable from AXON, every AXON agent is a valid MCP server. Zero migration cost for anyone already in the MCP ecosystem. Plus Kotlin solved Java's single biggest pain point — null pointer exceptions — through the type system. AXON's equivalent pain point is **tool schema hell**: manually writing JSON schemas for every LLM tool, in every framework, in every language, all slightly differently. AXON `tool` blocks auto-generate schemas from the type signature. One declaration, every format.

---

### **The AEL insight — the most original contribution**

This is the part nobody in the ecosystem has solved and it's worth saying directly: there is currently no standard format for what an LLM agent *does* when it executes.

OpenAI calls it `function_call` JSON. Anthropic calls it `tool_use` with a different schema. LangChain wraps both in `AgentAction` objects. LlamaIndex wraps those in `AgentChatResponse`. Every framework has opaque internal logs that you can't replay, audit, or train on. When something goes wrong in a multi-step agent run, you're reading Python stack traces and `print()` statements.

AEL can be the lingua franca. When an LLM runs inside AXON, its actions are structured execution traces:

axon  
think "User wants climate data. I should search for recent figures."  
act WebSearch(query: "global temperature 2025", max\_results: 5\)  
observe results: \[{ title: "...", url: "...", snippet: "..." }, ...\]  
think "Result 1 looks authoritative. Fetch the full article."  
act WebFetch(url: "https://climate.nasa.gov/...")  
store memory.working\["climate\_summary"\] \= "Global temps rose 1.2°C since..."  
act Respond(content: synthesize(memory.working))

That trace is simultaneously four things: human-readable (a developer can follow exactly what happened and why), machine-executable (the runtime can replay it deterministically for debugging), auditable (a compliance team can verify the agent only accessed approved sources), and trainable (future model fine-tuning on high-quality AEL traces). The last one is the long game. If AXON agents produce millions of AEL traces, those traces become among the most valuable training data in existence — structured, typed, semantically rich records of intelligent task completion. That's the 10-year flywheel.

---

### **Prototype plan — concrete phases**

**Phase 0 — two weeks, no code.** Write ten real-world agent use cases in `.ax` files by hand. Customer support agent, research synthesizer, code reviewer, RAG over internal docs, multi-agent debate. Iterate until ADL reads as naturally as SQL `CREATE TABLE`. The key question to answer: can a non-programmer read an `.ax` file and understand what the agent does? If yes, you've found the right syntax. If not, iterate.

**Phase 1 — month 1–2: `axon serve` first.** Build the MCP server generator before anything else. Parse a `.ax` file, emit a FastMCP server, launch it with `axon serve myagent.ax`. Claude Desktop connects to it immediately. This is the one demo that makes someone say *"I need this right now"* — because they don't need to understand the language to see the value. A tool that takes any `.ax` file and makes it a working MCP server is immediately useful even to someone who's never heard of AXON.

**Phase 2 — month 2–3: AEL runtime.** The agent actually runs. `act`, `think`, `observe`, `store` execute against the MCP wire. Provider plugins land: `axon-provider-anthropic`, `axon-provider-openai`. Memory types: `ShortTerm` (in-process dictionary), `Semantic` (ChromaDB). AEL traces log to JSONL files — simple, readable, replay-capable.

**Phase 3 — month 3–4: RAG and flows.** `rag { }` block compiles to a retrieval pipeline. `flow { }` runs multi-stage pipelines with fan-out and fan-in. Multi-agent: `go agent.run(task)` spawns concurrent agents, channels pass messages between them.

**Phase 4 — month 4–6: tooling and community.** VS Code extension with LSP. Token budget warnings at edit time. `axon eval` command with built-in harness. Public package registry. But critically — the GitHub repo, the spec document, and the Discord should open at **Phase 0**, not Phase 4\. Open standard governance starts before you write a single line of parser code. The moment you open the spec, you're not competing with frameworks — you're offering them a standard to implement.

---

### **My genuine view**

The MCP angle is the move that changes the category. Without it, AXON is a thoughtful language competing with LangChain, CrewAI, and LlamaIndex — and that's a crowded, fast-moving fight. With it, AXON is the authoring language for a protocol that's already winning adoption. The precedent is clear: HTTP defined the wire, HTML defined what humans write. Nobody says "I'm writing HTTP" — they say "I'm writing HTML." If AXON becomes the standard way to author MCP agents, MCP's adoption curve becomes AXON's adoption curve without AXON having to fight for it.

The dual-mode design — the same language for human authoring (ADL) and LLM execution (AEL) — is the most theoretically original piece. It's the Lisp insight applied to the agent era: if the agent's thought format is also the language the human uses, you collapse the gap between what you build and what runs. Every debugging session is just reading AEL. Every fine-tuning dataset is just collected AEL traces. That's a compound advantage that builds over years.

If I had to name the one decision that determines whether this survives 15 years or 3: it's open standard governance from day one. One company's language becomes legacy when that company pivots, gets acquired, or loses interest. A community-governed spec becomes infrastructure. ECMA governs JavaScript. W3C governs HTML. Neither is going away because no single company can kill them. AXON needs that structure from the start, not as an afterthought. It's uncomfortable to give up control early — but it's the only governance model that produces SQL-level longevity.

The prototype strategy is right: start with `axon serve`, prove the MCP server generation, then build outward. Want to start on Phase 0 — drafting the first ten `.ax` use cases together right now?

## **You said: so you feel MCP or MetaMCP approach will be better than language design that we planned before?**

so you feel MCP or MetaMCP approach will be better than language design that we planned before? Can you reevaluate and suggest, so that we will be 100% sure we are approaching effective design? What do you think?

May 27

## **Claude responded: Good — you're right to push on this.**

Reconsidered language-first design as stronger foundational approach  
Reconsidered language-first design as stronger foundational approach

Good — you're right to push on this. Let me do an honest reevaluation rather than just continue building on the direction we drifted. Stepping back to first principles:

V

visualize

V

visualize show\_widget  
---

### **The honest reevaluation**

I'll be direct: in the last few messages I got pulled toward the MCP angle because it was exciting and immediate. That was a drift in the wrong direction for a 15-year design. Here's why.

**The critical risk with MCP-first.** MCP was announced in late 2024\. It is one year old. Google already shipped a competing protocol — Agent-to-Agent (A2A). OpenAI has its own tool-calling format. The protocol war for agentic systems is not settled. If AXON is MCP-native, and MCP loses — or Anthropic changes the spec significantly, which they can because they own it — AXON is stranded. SQL didn't survive by being "the language for IBM DB2." It survived by being the language for *relational algebra*, an abstraction that predates any specific database engine. That's the right model to follow.

MCP's scope is also genuinely narrow. It defines tools, resources, and prompts. But the richest parts of what we designed — `flow { }` DAG pipelines, `rag { }` retrieval chains, `memory<Semantic>` typed stores, multi-agent channel passing — none of these map cleanly to MCP primitives. You'd be forcing a rich language's semantics through a narrow protocol aperture.

**What the MCP exploration gave us that's genuinely worth keeping.** Not everything from that direction was wrong. Three things are valuable and belong in the design regardless of MCP:

The ADL \+ AEL dual-mode insight is independent of any protocol. Humans writing declarative agent definitions and LLMs generating imperative execution traces in the same language is a real design principle — the "SQL DDL vs DML" distinction for agents. It belongs in the language spec.

The 5 primitives (Perceive, Recall, Reason, Act, Learn) are independent of MCP. They're grounded in 40 years of agent theory. This is the stable mathematical foundation AXON needs.

The open standard governance argument is independent of MCP. Whatever AXON becomes, it should be community-governed from day one. That principle holds.

**The right relationship between AXON and MCP.** Think of it exactly like TypeScript and JavaScript runtimes. TypeScript doesn't care whether you target Node.js, Deno, Bun, or the browser — you pick a target at compile time. Similarly, AXON doesn't care whether you target MCP, A2A, a Python runtime, or TypeScript. You write AXON once; the compiler emits for the target.

Concretely: `axon serve myagent.ax --target mcp` emits a FastMCP server. `axon build myagent.ax --target python` emits a Python package. `axon build myagent.ax --target typescript` emits a TypeScript module. MCP is a first-class target — it gets the `axon serve` command and the killer demo. But it is not the design foundation.

---

### **The definitive recommendation**

Here it is, stated cleanly:

**AXON is a programming language.** Not an MCP DSL, not a MetaMCP framework. A language — with its own syntax, type system, compiler, and runtime — that happens to emit to multiple targets including MCP.

Its foundation is the 5 primitives of agent cognition, giving it the same kind of mathematical grounding SQL gets from relational algebra. Its type system enforces token budgets, schema correctness, and memory safety at compile time. Its wrapper-first strategy (transpile to Python first) gives immediate ecosystem access. Its provider plugin model makes it model-agnostic. Its open standard governance makes it community-owned and independent of any company. And its MCP compilation target gives it immediate interoperability with a fast-growing ecosystem — without betting the language's existence on that ecosystem surviving.

The original language design was right. The MCP angle is a powerful feature of that design, not its replacement.

**My honest view:** I should have caught the drift earlier. The language-first design is clearly stronger on the dimensions that matter for 15-year survival — protocol independence, expressiveness, compile-time safety, community ownership. MCP-first only wins on speed-to-demo and build simplicity, which are real concerns for a prototype but not the right constraints for a foundational design decision. The synthesis gets you both: a language-grounded design with `axon serve` as the fastest path to a working demo. That's the right call, and it's where the original thinking was already pointing before we got pulled sideways.

Ready to start Phase 0 — drafting the first real `.ax` files to test whether the syntax actually feels right in practice?

## **You said: before you move ahead with Phase 0, one more important question is how are we going to test and implement it.**

before you move ahead with Phase 0, one more important question is how are we going to test and implement it. How we'll use it with IDEs/models/ API Key based models and so on,. How other Models/LLMs can help us develop this language to make it a collaborative effort. Think from these prospect also.

May 27

## **Claude responded: Great question — and a genuinely important one to answer before Phase 0\.**

Architected comprehensive testing, IDE integration, and LLM-collaborative development strategy  
Architected comprehensive testing, IDE integration, and LLM-collaborative development strategy

Great question — and a genuinely important one to answer before Phase 0\. Testing, IDE integration, API key design, and multi-LLM collaboration are all interconnected. Here's the full picture:

V

visualize

V

visualize show\_widget

## **You said: please resume**

please resume

May 27

## **Claude responded: Continuing from the ecosystem diagram — let me cover all four areas the diagram represents.**

Identified incomplete explanation and pinpointed missing sections to continue  
Identified incomplete explanation and pinpointed missing sections to continue

Continuing from the ecosystem diagram — let me cover all four areas the diagram represents.

---

### **1\. Testing strategy — three levels, one key insight**

**Level 1 — Unit tests (instant, deterministic, free).** These test the language itself, not the agents running in it. Parser correctness — does this `.ax` file produce the right AST? Type checker accuracy — does the compiler catch a budget overflow or a mismatched return type? Transpiler output — does `agent ResearchBot { }` emit valid Python? These run in milliseconds with standard pytest and need no API keys, no models, nothing external. Every commit triggers them.

**Level 2 — Integration tests (fast, cheap, no API cost).** This is the key insight: use **Ollama** for all integration testing. Ollama runs Llama 3, Mistral, Phi, and others locally — no API key, no cost, no rate limits, no latency waiting for a cloud endpoint. An AXON agent that compiles and runs correctly against Ollama is 90% proven. The test suite covers: does the agent loop execute? Do tool calls dispatch correctly? Does memory read and write? Does the MCP server respond to tool calls? All of this works against a local model running on your laptop.

**Level 3 — Eval suite (scheduled, uses real models, measures quality).** `axon eval` runs against real cloud providers on a schedule — nightly or pre-release. It measures things Ollama can't tell you: does the agent produce *good* outputs, not just *any* outputs? Metrics include faithfulness (did it stay grounded in the retrieved context?), task completion rate, token efficiency, and provider consistency (does the same agent produce equivalent results across Anthropic, OpenAI, and Google?). This level costs money, so you run it deliberately rather than on every commit.

**The CI pipeline:**

git push  
  → pytest unit tests (parser, types, transpiler)   — always, \~5s  
  → integration tests via Ollama                    — on PRs, \~60s  
  → axon eval nightly                               — scheduled, \~$2-5  
  → provider compatibility matrix                  — weekly  
---

### **2\. IDE integration — one LSP server, all editors for free**

The strategic decision here is to build **one** LSP (Language Server Protocol) server and get every editor for free. Microsoft designed LSP specifically so language features are written once and consumed by any editor that speaks the protocol — VS Code, JetBrains (via LSP4IJ), Neovim, Emacs, Zed, Helix. You write the server in Python using `pygls`, which handles the JSON-RPC transport and lets you focus on language semantics.

The LSP features, in priority order for the prototype:

**Token budget warnings at edit time** — this is AXON's TypeScript moment. Before the compiler even runs, the editor underlines a prompt block in amber if the token count estimate exceeds your `@budget` annotation. This single feature makes developers say "I couldn't live without this." It's the equivalent of TS flagging a null reference — catches a class of runtime failures at the earliest possible moment.

**Tool schema validation** — if your `tool` block has a type mismatch between the function signature and what the docstring claims, the editor squiggles it. If you reference a tool name in an `agent` block that doesn't exist in scope, it's an error before `axon run` ever fires.

**Autocomplete for provider strings** — typing `model: @` triggers a completion list of installed providers and their available models, with inline cost-per-token shown in the hover documentation.

**Go-to-definition across .ax files** — clicking on an agent reference in a `flow { }` block jumps to that agent's definition, even across files in the same AXON workspace.

The VS Code extension is a thin TypeScript wrapper that launches the Python LSP server as a child process and forwards all editor events to it. JetBrains uses LSP4IJ (their official LSP bridge plugin) to connect the same server. You build the intelligence once.

---

### **3\. API key management — the golden rule**

The golden rule is absolute: **API keys never appear in `.ax` files.** Not hardcoded, not as default values, never. The `.ax` file is source code — it goes in git, it gets shared, it's readable. Keys belong in environment variables or a secrets manager.

The `axon.toml` project config file is where providers are wired up, and it references env vars by name:

toml  
\[providers\]  
default  \= "@anthropic/claude-4"  
embed    \= "@openai/text-embed-3"  
local    \= "@ollama/llama3"

\[providers.anthropic\]  
api\_key  \= "${ANTHROPIC\_API\_KEY}"

\[providers.openai\]  
api\_key  \= "${OPENAI\_API\_KEY}"

\[providers.ollama\]  
base\_url \= "http://localhost:11434"  
\# no key needed

The `.ax` agent code itself is provider-agnostic:

axon  
agent ResearchBot {  
    model: Model  // resolved from axon.toml at runtime  
    tools: \[WebSearch\]  
}

Switching from Anthropic to OpenAI is a one-line change in `axon.toml` — the agent `.ax` file doesn't change at all. This is the provider plugin promise kept concretely.

For teams: `axon.toml` is committed to git (with `${ENV_VAR}` placeholders, never real values). A `.env` file holds the real keys and goes in `.gitignore`. CI/CD injects secrets via environment at runtime. For local Ollama development — no key file needed at all, which makes onboarding frictionless for contributors.

---

### **4\. Multi-LLM collaborative development — the most exciting part**

This is where AXON's development process itself becomes novel. You're building a language *for* AI systems — it would be strange not to use AI systems to build it. Here's how different models contribute different things:

**Phase 0: LLMs as syntax testers.** Before writing a single line of parser code, feed the draft spec to Claude, GPT-4o, Gemini, and a local Llama model, and ask each: *"Without any examples, write an AXON agent that does X."* If Claude writes valid AXON naturally — the syntax is intuitive. If GPT-4o struggles to express a pattern — the syntax has a gap. This is user testing with LLMs as proxy users, and it's free, instant, and brutally honest. Any pattern that three different models get wrong is a syntax problem, not a model problem.

**A council of models for spec review.** Different models have different reasoning strengths. Rather than treating this as a weakness to work around, use it as a feature:

* **Claude** reviews for logical consistency and type system soundness — it excels at finding internal contradictions in formal specifications  
* **GPT-4o** generates adversarial cases — ask it explicitly to "try to break this spec" and it will find ambiguities and edge cases the design team missed  
* **Gemini** reviews for documentation clarity — feed it a spec section and ask whether a new developer could understand it without prior context  
* **Llama (local, via Ollama)** provides the open-source community perspective — if the spec is too complex for a smaller model to reason about, it's probably too complex for new contributors

Each model reviews independently, you diff the findings, and the disagreements are the most interesting design problems.

**LLMs as the CI system.** Every GitHub PR to the AXON compiler or spec gets a Claude Code review that checks three things automatically: does this change break any existing `.ax` example files? Does it introduce any ambiguity into the grammar? Are there test cases for this new feature? This is not replacing human review — it's handling the mechanical checklist so human reviewers can focus on design judgment.

**Automated test generation from the spec.** Take any section of the AXON spec and feed it to Claude with the instruction: *"Generate a complete pytest test suite for this spec section, covering the happy path, all edge cases, and expected error conditions."* The output needs review and occasionally correction, but it bootstraps the test suite at 10x the speed of writing it manually. This is how you build 500 tests for a language spec in week two of development.

**The meta-bootstrap — the most exciting phase.** Once Phase 1 exists (basic parser \+ Python transpiler), the development process becomes recursive. You write AXON agents that help build AXON:

axon  
agent SpecReviewer {  
    model: @anthropic/claude-4  
    tools: \[ReadFile, GitDiff, WriteComment\]

    fn review(diff: Str) \-\> Review {  
        let issues  \= @think("What ambiguities does this diff introduce?")  
        let missing \= @think("What test cases are missing for this change?")  
        let suggest \= @think("How could the syntax be clearer?")  
        Review { issues, missing, suggest }  
    }  
}

agent TestGenerator {  
    model: @anthropic/claude-4  
    tools: \[ReadSpec, WriteTestFile\]

    fn generate(section: Str) \-\> List\<Test\> {  
        @think("Edge cases for this spec section")  
            |\> @generate("Write pytest tests for each")  
    }  
}

You run `axon run spec_reviewer.ax` and it reviews the PR. You run `axon run test_generator.ax --spec grammar.md` and it writes new tests. AXON participates in its own development. This is the Lisp bootstrap pattern for the AI era — the language helps build the language.

**The long game — a fine-tuned AXON model.** As AXON gains real usage, you collect `.ax` files from the community (with permission). Fine-tune a small 7B model — something that runs locally — specifically on AXON syntax and idioms. This becomes the local autocomplete model embedded in the LSP server. No API key, no latency, no cost per keystroke. The more AXON is used, the smarter the local model gets. This is GitHub Copilot's playbook applied to a domain-specific language — and because AXON's domain is narrow and well-defined, a small fine-tuned model can be remarkably capable within it.

---

### **The development stack, committed**

The prototype technology choices flow directly from all of this: **tree-sitter** for the parser (GitHub uses it, excellent Python bindings, graceful error recovery), **pygls** for the LSP server (Python-native, active maintainers), **FastMCP** for the MCP compilation target (gives you `axon serve` immediately), **Ollama** as the primary test runtime (free, local, no friction), **pytest** for unit and integration tests, and **Claude Code** as the CI reviewer from day one.

The development is genuinely collaborative — between us, the open spec, the council of models reviewing it, and eventually the AXON agents that help maintain it. That's a development process worth building.

Ready for Phase 0?

## **You said: great plan.**

great plan. Proceed

May 27

## **Claude responded: Phase 0 is about one thing: writing real .**

Architected comprehensive language specification with ten real-world agent implementations  
Architected comprehensive language specification with ten real-world agent implementations

Phase 0 is about one thing: writing real `.ax` files by hand until the syntax either feels right or breaks. No compiler, no parser — just syntax. Here are the ten reference implementations that define what AXON v0.1 actually looks like, followed by the spec document.

---

### **The 5 most instructive use cases inline**

These five files surface the key syntax decisions. Commentary follows each.

**1 — Research synthesizer (core agent pattern)**

axon  
import { WebSearch, WebFetch } from "axon:tools/web"

agent ResearchAgent {  
    model: @anthropic/claude-4  
    tools: \[WebSearch, WebFetch, Calculator\]  
    memory: Memory\<Semantic\>

    @budget(tokens: 4000\)  
    fn run(topic: Str, depth: Int \= 3\) \-\> Result\<Report, AgentError\> {  
        let queries \= @plan("Generate {depth} search queries for: {topic}")

        for query in queries {  
            let results \= act WebSearch(query: query, max\_results: 5)?  
            store memory.working\[query\] \= results  
        }

        let context \= memory.recall(topic, top\_k: 10\)  
        Ok(@synthesize(context, format: Report))  
    }  
}

*Key decisions revealed: `@plan()` for LLM reasoning, `act` for tool calls, `store` for memory, `?` for propagation, `@budget` annotation on the method.*

---

**2 — RAG customer support (retrieval pipeline)**

axon  
rag ProductDocs {  
    source: "./knowledge\_base/\*\*/\*.md"  
    chunker: Chunker::sliding(size: 512, overlap: 64\)  
    embedder: @openai/text-embed-3  
    store: VectorDB::postgres(env.PGVECTOR\_URL)

    fn retrieve(query: Str, top\_k: Int \= 5\) \-\> List\<Chunk\> {  
        store.search(embed(query), top\_k)  
            |\> rerank(query, model: @cohere/rerank-3)  
            |\> filter(chunk \=\> chunk.score \> 0.72)  
    }  
}

agent SupportAgent {  
    model: @anthropic/claude-sonnet  
    tools: \[ProductDocs.retrieve, CreateTicket\]

    fn handle(question: Str) \-\> Result\<Response, AgentError\> {  
        let context \= act ProductDocs.retrieve(query: question)?

        if context.empty? {  
            act CreateTicket(title: question, priority: "medium")?  
            return Ok(Response.escalate("Creating a support ticket for you."))  
        }

        Ok(@answer(question, using: context, tone: "helpful"))  
    }  
}

*Key decisions revealed: `rag {}` block with own `fn retrieve()` method, pipe operator `|>` for retrieval chain, RAG tools are called with `act` just like any other tool.*

---

**3 — Multi-agent orchestration (concurrency)**

axon  
agent WorkerAgent {  
    model: @anthropic/claude-haiku  
    tools: \[WebSearch, Calculator\]

    fn execute(task: Task) \-\> Result\<TaskResult, AgentError\> {  
        @complete(task)  
    }  
}

agent OrchestratorAgent {  
    model: @anthropic/claude-4  
    workers: WorkerAgent \* 4  
    memory: Memory\<Semantic\>

    fn run(goal: Str) \-\> Result\<Report, AgentError\> {  
        let plan \= @plan(goal, max\_steps: 10\)

        let futures \= plan.tasks  
            |\> map(task \=\> go workers.next().execute(task))

        let results \= await futures timeout 120s  
            |\> collect()?

        Ok(@synthesize(results, goal: goal))  
    }  
}

*Key decisions revealed: `WorkerAgent * 4` worker pool syntax, `go` for async spawn, `await futures timeout 120s` for time-bounded collection, `workers.next()` for round-robin dispatch.*

---

**4 — Prompt types and compile-time budget safety**

axon  
// Prompt as a first-class typed template  
prompt SummarizeDocument(  
    doc: Document,  
    style: Str \= "concise",  
    audience: Str \= "general",  
    @budget(tokens: 600\)  
) \-\> Str {  
    """  
    Summarize the following {doc.kind} for a {audience} audience.  
    Style: {style}. Maximum 3 paragraphs. Focus on key insights.

    Content:  
    {doc.content}  
    """  
}

prompt ExtractActionItems(  
    transcript: Str,  
    @budget(tokens: 300\)  
) \-\> List\<ActionItem\> {  
    """  
    Extract all action items from this transcript.  
    Return as a structured list with: owner, task, deadline.

    Transcript:  
    {transcript}  
    """  
}

agent MeetingAgent {  
    model: @anthropic/claude-4  
    tools: \[Transcribe, SaveToNotion\]

    fn process(audio\_path: Str, page\_id: Str) \-\> Result\<MeetingNotes, AgentError\> {  
        let transcript \= act Transcribe(path: audio\_path)?

        let notes \= MeetingNotes {  
            summary:      model.complete(SummarizeDocument(transcript.as\_doc())),  
            action\_items: model.complete(ExtractActionItems(transcript.text)),  
            attendees:    @extract(transcript.text, kind: "speaker\_names")  
        }

        act SaveToNotion(title: "Notes — {notes.date}", content: notes.to\_md(), page\_id: page\_id)?  
        Ok(notes)  
    }  
}

*Key decisions revealed: `@budget` on prompts is a compile-time annotation — the compiler statically estimates if the template \+ expected inputs could exceed the budget and raises an error before runtime. `model.complete(PromptTemplate(...))` is the explicit call pattern.*

---

**5 — Monitoring agent (annotations \+ short-term memory)**

axon  
tool FetchMetrics(endpoint: Str) \-\> Result\<Metrics, ToolError\> {  
    /// Fetches system metrics from a monitoring endpoint.  
    /// Use to check CPU, memory, error rate, and latency.  
    http.get(endpoint)  
        |\> parse\_json::\<Metrics\>()  
}

tool SendAlert(channel: Str, message: Str, severity: "info"|"warn"|"critical") \-\> Result\<Bool, ToolError\> {  
    /// Sends an alert to a Slack channel.  
    /// Only call when anomalies exceed configured thresholds.  
    slack.post(channel, message, severity)  
}

agent MonitorAgent {  
    model: @anthropic/claude-haiku  
    tools: \[FetchMetrics, SendAlert\]  
    memory: Memory\<ShortTerm\>(capacity: 500\)

    @schedule(every: 5.minutes)  
    @trace  
    fn watch(endpoint: Str, thresholds: Thresholds) \-\> Result\<(), AgentError\> {  
        let metrics  \= act FetchMetrics(endpoint: endpoint)?  
        let history  \= memory.recent(n: 12\)

        let anomalies \= @classify(  
            input:      metrics,  
            baseline:   history,  
            thresholds: thresholds  
        )

        match anomalies.severity {  
            "critical" \=\> {  
                act SendAlert(  
                    channel:  "\#ops-critical",  
                    message:  @format\_alert(anomalies),  
                    severity: "critical"  
                )?  
            },  
            "warn" \=\> {  
                act SendAlert(channel: "\#ops", message: @format\_alert(anomalies), severity: "warn")?  
            },  
            \_ \=\> {}  
        }

        store memory.append(metrics)  
        Ok(())  
    }  
}

*Key decisions revealed: `@schedule(every: 5.minutes)` makes a method periodic. `@trace` enables full AEL logging for this method. Literal union types `"info"|"warn"|"critical"` for constrained strings. `()` as the unit return type (like Rust).*

---

### **Syntax decisions crystallised by writing these files**

**Locked in:**

* `@prefix` for all LLM-powered operations — unambiguously marks "this calls the model"  
* `act` keyword for tool invocations — explicit, readable, traceable  
* `store memory.key = value` — explicit memory writes, never implicit  
* `go` \+ `await` for concurrency — familiar to Go developers  
* `///` triple-slash docstrings on tools — these become MCP tool descriptions verbatim  
* `|>` pipe operator — indispensable for retrieval chains and data transforms  
* `?` error propagation — consistent with the `Result<T, E>` model  
* `@budget(tokens: N)` as a compile-time annotation — the single most valuable safety feature  
* Provider syntax `@provider/model-name` — clean, unambiguous  
* Types: `Str`, `Int`, `Bool`, `List<T>`, `Result<T, E>`, `Option<T>` — consistent set

**Still open:**

* `WorkerAgent * 4` pool syntax — useful shorthand or too cute? Alternative: `pool: WorkerAgent(size: 4)`  
* Should `flow {}` stages be declared separately or inlined?  
* How to handle streaming in return types — `Stream<Str>` vs `async fn`?  
* Module system for large projects — folder convention or explicit `module`?  
* `@classify()` vs `@detect()` — naming consistency for built-in LLM ops

---

Now creating the full spec document — the Phase 0 deliverable:

Ran a command, created a file, read a file  
Ran a command, created a file, read a file  
---

### **What Phase 0 produced and what comes next**

The spec has 19 sections covering the full syntax surface, 10 reference implementations, a decisions log distinguishing what's locked from what's still open, and acceptance criteria for when Phase 0 is actually complete.

**The most important next step before Phase 1 starts** is the LLM readability test from section 18\. Take this spec to Claude, GPT-4o, and Gemini with this exact prompt:

*"Read this language spec and write a valid AXON agent that does the following: \[new use case not in the spec\]. Do not look at the reference implementations — write from the spec alone."*

If all three produce syntactically consistent `.ax` files without contradicting each other, the syntax is intuitive enough to proceed to the parser. If they diverge on the same construct — that construct needs rethinking before the grammar is frozen.

**The two open questions that will cost the most if decided wrong in Phase 1** are the `flow {}` vs orchestrator agent split (it affects the entire pipeline execution model) and the full list of built-in `@` operations (it determines what the runtime must implement before anything useful runs). Worth resolving those explicitly before writing a single grammar rule.

Phase 1 deliverable: `axon run hello_agent.ax` executes — one agent, one tool, one model call. Everything else builds from there.

Axon spec v0.1  
Document · MD   
Download

## **You said: one query: I'm bit confused.**

one query: I'm bit confused. What should I do to finalize phase 0, before we can move towards phase 1

May 27

## **Claude responded: Really simple answer — Phase 0 has two parts.**

Distilled Phase 0 into four concrete actionable tasks  
Distilled Phase 0 into four concrete actionable tasks

Really simple answer — Phase 0 has two parts. The writing part is **done** (spec \+ 10 reference files). What remains is **validation**. Here's exactly what to do:

V

visualize

V

visualize show\_widget

## **You said: So query for you: I take the Axon spec v0.**

So query for you: I take the Axon spec v0.1 MD file, in IDE, select the model, and provide this prompt "Read this language spec and write a valid AXON agent that does the following: \[new use case not in the spec\]. Do not look at the reference implementations — write from the spec alone." with respect to this MD file, correct ?

May 28

## **Claude responded: Yes, exactly right.**

Validated approach and synthesized clarification guidance  
Validated approach and synthesized clarification guidance

Yes, exactly right. That's precisely the test. A few things to make it work well:

**The spec as context:** Don't just reference the file — paste the full content of `axon_spec_v0.1.md` into the conversation as context. Most IDE AI assistants and chat interfaces accept it as an attached file or pasted text. The model needs to read the actual spec, not just know a file exists.

**Run it across three different models.** The point is comparing outputs, not just getting one answer. Suggested combo: Claude, GPT-4o, and Gemini. Each independently, with the same spec \+ the same use case.

**Good "new use cases" to test with** — these are genuinely not in the spec's 10 examples:

* *"An agent that monitors a GitHub repo for new issues, labels them by priority using AI, and assigns them to team members"*  
* *"An agent that watches a folder for new PDF invoices and extracts line items into a database"*  
* *"An agent that takes Slack messages from the past week and generates a team standup summary"*

Pick one and use the same use case across all three models so you can compare outputs directly.

**What to look for when reading the outputs:**

Does the model naturally write `act ToolName(...)` for tool calls — or did it invent something else? Does it use `@think()` / `@plan()` for LLM operations, or did it write plain function calls? Did it add `///` docstrings to tools without being told? Did it use `Result<T, AgentError>` return types? Did it use `store memory.key = value`?

If all three models write `.ax` files that look consistent with each other and with the spec — the syntax is intuitive. If one model writes something completely different for a specific construct, that construct is ambiguous in the spec and needs fixing before Phase 1\.

Bring the outputs back here and we'll compare them together.

## **You said: I'd attached 3 models output in this file, please review**

### **models\_output.md**

md

I'd attached 3 models output in this file, please review

May 28

## **Claude responded: Excellent outputs.**

Systematically analyzed three model outputs for specification compliance  
Systematically analyzed three model outputs for specification compliance

Excellent outputs. Let me do a systematic comparison across all three.

V

visualize

V

visualize show\_widget  
---

### **Overall verdict: Phase 0 passes**

The critical finding — **10 out of 13 constructs converged perfectly across all three models without prompting**. That's a strong signal the core syntax is intuitive and well-specified. The models independently agreed on `act`, `store`, `memory.get().unwrap_or()`, `?`, `///` docstrings, `@budget`, `@schedule`, `@trace`, literal unions, and string interpolation. These are locked.

Three gaps surfaced. Here's exactly what each means and how to fix it:

---

#### **Gap 1 — `think` vs `@think` — spec inconsistency**

Both Gemini and Claude wrote `think "text"` as a bare keyword (no `@`, no parens). The spec shows `@think("...")` in agent method examples but `think "..."` in the AEL section. The models defaulted to bare keyword — which is actually cleaner.

**Fix:** Unify to `think "..."` everywhere (bare keyword, like `store` and `act`). Reserve `@prefix` strictly for operations that call the LLM with a structured response (like `@plan`, `@summarize`, `@classify`). `think` is just a trace annotation — it doesn't return anything — so the bare keyword form is correct.

---

#### **Gap 2 — Time/date built-in missing from spec**

Claude used `now().iso8601()`. GPT used `@now()`. Neither is defined in the spec. Claude even flagged it explicitly in its notes — *"now().iso8601() is used but the spec doesn't define a standard library for date/time."*

**Fix:** Add one line to the spec under built-in functions:

axon  
import { now, sleep, format\_date } from "axon:time"  
// now() \-\> Str  — returns ISO 8601 timestamp  
// now().iso8601() \-\> Str  
// now().unix() \-\> Int  
---

#### **Gap 3 — Custom type alias syntax underdefined**

GPT correctly inferred a struct-like type syntax that the spec mentions in the grammar but never demonstrates with an example:

axon  
type Issue \= {  
    id:         Int,  
    number:     Int,  
    title:      Str,  
    body:       Str,  
    labels:     List\<Str\>,  
    created\_at: Str  
}

Gemini fell back to `Any` and `Map<Str, Any>` because there was no example to follow. Claude assumed types were pre-defined elsewhere.

**Fix:** Add a `type` alias example to the spec — one example is enough for all three models to use it consistently.

---

#### **Bonus observation — Claude picked the right model tier**

Claude Sonnet used `@anthropic/claude-haiku` for the classification tasks (narrow prompts, small budgets). Gemini and GPT both defaulted to `@anthropic/claude-4`. This shows the spec's guidance on cost-appropriate model selection was clear enough — one model read and applied it correctly.

---

### **What to do right now**

These three gaps are small. Let me update the spec with all three fixes, then Phase 0 is officially done:

Edited 7 files, ran 2 commands, read a file  
Edited 7 files, ran 2 commands, read a file  
---

### **Phase 0 is officially done**

Here's the summary of what the three model outputs proved:

**The syntax works.** Three independent models — without seeing each other's output — all wrote `act`, `store`, `memory.get().unwrap_or()`, `?`, `///`, `@budget`, `@schedule`, `@trace`, literal unions, and string interpolation correctly and consistently. That's the proof the core language is intuitive.

**Three genuine gaps were surfaced and fixed:**

* `think` is now unambiguously a bare keyword (not `@think`)  
* `axon:time` is now a defined built-in package with `now()` and `iso8601()`  
* Type alias syntax now has a concrete example in the spec

**One smart observation from Claude's output** worth noting: it chose `@anthropic/claude-haiku` for narrow classification tasks rather than defaulting to `claude-4`. That means the model-tier guidance in the spec was clear enough to influence real architectural decisions. Good sign.

The updated spec is the Phase 0 deliverable — marked complete, with 3 non-blocking open questions carried forward. Phase 1 starts now: tree-sitter grammar, Python transpiler, and the first `axon serve` MCP demo. Ready when you are.

Axon spec v0.1  
Document · MD   
Download

## **You said: great\!**

great\! Let continue the momentum

May 28

## **Claude responded: Phase 1 starts now.**

Architected Phase 1 implementation strategy for AXON parser and code generator  
Architected Phase 1 implementation strategy for AXON parser and code generator

Phase 1 starts now. First target: `axon serve` — parse a `.ax` file, generate a working FastMCP server, connect Claude Desktop. Let's build it.

Create project directory structure  
Create project directory structure

## **You said: resume.**

resume...one more thing I'm thinking is: instead of you doing all the development, you focus on planning and designing, and the development tasks we can give to gemini, gpt and others. what do you think?

May 28

## **Claude responded: Genuinely great instinct — and it's exactly the "council of LLMs" workflow we designed for building AXON.**

Validated multi-model division of labor, architected practical workflow  
Validated multi-model division of labor, architected practical workflow

Genuinely great instinct — and it's exactly the "council of LLMs" workflow we designed for building AXON. Let me think through it properly.

V

visualize

V

visualize show\_widget  
---

### **My honest view — this is the right call**

This is exactly the workflow we planned when we talked about using multiple LLMs to build AXON. Here's why it makes sense:

**I'm most valuable as architect and reviewer, not as typist.** The reasoning work — design decisions, spec consistency, catching subtle issues — is where I add the most value. Generating 300 lines of parser code is something Gemini and GPT do just as well, possibly faster.

**It validates AXON as we build it.** If Gemini implements the parser from a task ticket and it works, that's proof the spec is clear enough. If it gets something wrong, that's a spec gap to fix. Every implementation becomes a test of the design.

**Parallel velocity.** You can give task tickets to multiple models simultaneously. While Gemini implements the parser, GPT implements the CLI. I review both when they come back. This is 3-4x faster than me doing it sequentially.

---

### **The division of labour, precisely**

**What stays with me:**

* Writing and updating the spec  
* Designing new language features  
* Writing task tickets (self-contained implementation specs)  
* Reviewing code from other models  
* Catching inconsistencies across modules  
* Making architectural decisions

**What goes to Gemini / GPT / others:**

* Implementing specific functions given clear specs  
* Writing test suites given test cases  
* Generating boilerplate given templates  
* CLI command implementations  
* Utility functions

---

### **The task ticket format**

Each ticket must be fully self-contained — other models have zero context from our conversation. The ticket IS the context.

AXON Task \#N — \[Module Name\]  
═══════════════════════════════════════════

BACKGROUND  
What AXON is and why this module exists (2-3 sentences).

WHAT TO BUILD  
Exact description of the function/module.

INTERFACE (copy-paste ready)  
Exact function signatures, class definitions, return types.

AXON SYNTAX REFERENCE  
The specific .ax syntax patterns this module must handle.

INPUT → OUTPUT EXAMPLES  
Concrete before/after pairs to test against.

RULES & CONSTRAINTS  
Non-negotiable requirements.

DEPENDENCIES  
What packages to use. What NOT to use.

TEST CASES  
At minimum 3 test cases to pass before submitting.  
---

### **The first three tickets, ready to use right now**

Here they are — self-contained, ready to paste into Gemini or GPT:

Created 3 files, read a file  
Created 3 files, read a file  
---

Three tickets ready to go. Here's how the workflow runs from here:

**Give Task \#01 to Gemini or GPT right now.** It's fully self-contained — the model needs zero context from our conversation. It has the interface, examples, constraints, and 9 test cases. When you get code back, paste it here and I'll review it.

**Task \#02 goes to a different model in parallel** — or the same one after \#01 passes. It depends on \#01's dataclasses but the ticket includes everything needed.

**Task \#03** can run as soon as \#01 and \#02 are done. It's the most exciting one — the output is a real FastMCP server.

**My role from here:** every time you bring back code from another model, I review it against the spec, catch issues, and either approve it or write precise feedback for iteration. I also write the next set of tickets (\#04 CLI, \#05 type alias parser, \#06 RAG block parser) as the earlier tasks complete.

This is faster, cheaper, and more robust than me doing all the coding. And every successful implementation is live validation that the AXON spec is clear.

Axon task 01 parser tools  
Document · MD   
Download  
Axon task 02 parser agents  
Document · MD   
Download  
Axon task 03 codegen mcp  
Document · MD   
Download  
Download all

## **You said: task\#01: given to gemini:**

### **ast\_nodes.py**

29 lines

py

### **parser.py**

262 lines

py

task\#01: given to gemini: I have successfully completed AXON Task \#01. Following the instructions in the axon\_task\_01\_parser\_tools.md file, I have implemented the ToolDecl parser and the AST nodes without any external parsing dependencies. Here is a summary of the deliverables I've created: src/axon/ast\_nodes.py: Contains the dataclasses for Param, Annotation, ToolDecl, and ImportDecl as per the specification. src/axon/parser.py: Implemented a lexer-less parser to read AXON .ax source strings containing tool definitions, imports, and @ annotations. It correctly tracks line numbers, parses out /// docstrings into arrays, isolates the raw code body dynamically via brace depth counting, and parses generic and union types in parameters properly. tests/test\_parser.py: Added the provided suite of 9 tests cases using pytest. I ran pytest on the test suite, and all 9 tests passed successfully: ......... \[100%\] 9 passed in 0.71s The parser correctly ignores // comments, supports literal type parsing like "info" | "warn" | "error" \= "info", accurately matches generic return types like Result\<List\<Any\>, ToolError\>, and extracts imports flawlessly.

Show more  
May 28

## **Claude responded: Good — let me actually run the code rather than just read it.**

Scrutinized parser implementation and identified minor edge case vulnerabilities  
Scrutinized parser implementation and identified minor edge case vulnerabilities

Good — let me actually run the code rather than just read it. Code review without execution catches maybe 70% of issues.

Ran 4 commands, created 2 files  
Ran 4 commands, created 2 files

All 9 pass. Now let me run my own edge case tests — things the spec tests don't cover but Task \#02 will depend on:

Ran 3 commands  
Ran 3 commands

## **You said: resume**

resume

May 28

## **Claude responded: Here's the full review verdict:**

Synthesized test results and formulated approval verdict  
Synthesized test results and formulated approval verdict

Here's the full review verdict:

---

### **Task \#01 — APPROVED ✓**

**9/9 spec tests pass. 6/6 edge cases pass.** Including the tricky ones — nested braces in bodies, stacked annotations, dot-values in annotation args (`every: 5.minutes`), unit return type `()`, and mixed declaration ordering.

**Code quality is solid.** Proper brace-counting for both params and body, correct docstring extraction, no external dependencies, clean line number tracking. Gemini followed the spec precisely.

---

### **Three things worth noting**

**1 — Minor bug: `source[pos-1]` on escaped strings**

In `parse_tool` and `parse_params`, the escape check reads:

python  
if c \== '"' and source\[pos-1\] \!= '\\\\':

When `pos=0`, Python returns `source[-1]` (the last character) instead of raising an error — a silent logical bug. In practice AXON source never starts with a quote character so it won't trigger, but it's worth fixing. The correct check is:

python  
if c \== '"' and (pos \== 0 or source\[pos-1\] \!= '\\\\'):

**2 — `agent` raises a clean SyntaxError**

Confirmed: encountering `agent MyAgent {` gives `SyntaxError: Unexpected token at line 3: agent MyAgent {`. Clear message, correct behavior for now.

**3 — One thing to tell the Task \#02 implementer explicitly**

The `annotations` accumulator in `parse()` gets reset after a `tool` is parsed:

python  
tool\_decl.annotations \= annotations  
annotations \= \[\]  \# ← reset here

Task \#02 must do the same reset after parsing an `agent`. Otherwise annotations bleed from a tool into the next agent declaration. Make sure to include this in the Task \#02 handoff.

---

### **Send Task \#02 now**

The foundation is clean — Task \#02 can build directly on this. Before you hand it off, add one line to the ticket:

**Note for implementer:** The `parse()` function accumulates `@annotations` in a list and resets it after each declaration. When you add `parse_agent()`, reset `annotations = []` after appending the `AgentDecl`, exactly as `parse_tool()` does.

Everything else in the ticket is self-contained and ready to go. Once Task \#02 comes back, Task \#03 (the FastMCP generator) can run immediately — and that's when we get the first real `axon serve` demo.

