# AXON — Launch Posts (Drafts)

**Do not publish until Tuesday/Wednesday. These are final drafts for review.**

---

## 1. Hacker News Post

**Timing:** Tuesday or Wednesday, 13:00 UTC (5:30pm IST, 9am ET)
**URL:** Point to GitHub repo: https://github.com/annapurnaagenticsolutions/axon

### Title (factual, no hype):
```
AXON: A typed DSL for autonomous agents that compiles to Python and TypeScript
```

### Body:
```
I built a programming language where agents, tools, memory, RAG, and orchestration are first-class language constructs — not framework boilerplate.

Write .ax files → type-check → compile to Python MCP servers or TypeScript modules → deploy to Docker or Fly.io.

Key differentiators:
- Type-safe agent definitions (compiler catches errors before runtime)
- Multi-target compilation (one source → Python + TypeScript)
- 1100+ tests, 16 examples, Docker/K8s/LSP/debugger/profiler
- RAG, flows, supervision trees, checkpoint/restore built in

Comparison: a multi-agent research pipeline in 189 lines of AXON vs 500+ lines of LangChain with no type safety.

Blog post with side-by-side comparison: [link]
GitHub: [link]
Try it: git clone, pip install -e ".[dev]", axon run examples/hello.ax --mock (no API key needed)

Happy to answer questions about language design decisions, the compiler architecture, or why I think agents need a DSL instead of another framework.
```

### First comment (post within 15 minutes):
```
Some context on why I built this:

I've been building agent systems for a while, and the pattern I kept seeing was: 500+ lines of Python wiring together 15+ LangChain classes, no type checking on tool signatures, runtime errors that should have been caught at compile time, and no way to target both Python and TypeScript from the same codebase.

AXON takes the SQL approach: when a domain gets complex enough, it gets its own language. SQL solved declarative data query. AXON solves declarative agent orchestration.

The compiler is written in Python, the parser uses a Pratt parser + hand-written lexer, and the codegen targets Python (via FastMCP) and TypeScript (via module generation). The type system is structural with generics, Result types, and agent-specific types (Memory, RAG, Flow).

1100+ tests, 16 examples covering realistic patterns (research pipeline, GitHub triage, invoice extraction, monitoring alerts). The --mock flag lets you run any agent without an API key.

Loom demo (90s): [link]
```

---

## 2. X/Twitter Thread

**Timing:** 60 minutes after HN post (14:00 UTC)
**Format:** 8 tweets, GIF-led

### Tweet 1:
```
AXON: a typed DSL for autonomous agents. Compiles to Python + TypeScript.

Not another framework. A language where agents, tools, RAG, and flows are first-class constructs.

1100+ tests. 16 examples. Docker, K8s, VS Code extension, debugger, profiler.

[Attach: 20s hero GIF]
```

### Tweet 2:
```
Here's a multi-agent research pipeline in 189 lines of AXON:

- 4 agents (QueryPlanner, ResearchAgent, Summarizer, FactChecker)
- RAG knowledge base
- Typed tools with Result<> returns
- Flow orchestration with stage pipeline
- Episodic memory

[Attach: screenshot of research_pipeline.ax]
```

### Tweet 3:
```
The same pipeline in LangChain: 500+ lines of Python.

- 15+ imports
- No type checking on tool signatures
- No compile-time flow validation
- No multi-target compilation
- Manual memory/checkpoint wiring

[Attach: screenshot of LangChain code]
```

### Tweet 4:
```
AXON compiles to Python MCP servers AND TypeScript modules.

One source. Multiple targets.

axon compile --target ts → production-ready TypeScript.

[Attach: GIF of axon compile --target ts showing TS output]
```

### Tweet 5:
```
Type safety is the killer feature.

Tool signature mismatch? Compile error.
Agent receives wrong type? Compile error.
Flow stage missing? Compile error.

No more discovering type bugs at 3am in production.

[Attach: screenshot of axon validate showing a type error]
```

### Tweet 6:
```
Try it right now, no API key needed:

git clone https://github.com/annapurnaagenticsolutions/axon
cd axon
pip install -e ".[dev]"
axon run examples/hello.ax --mock

The --mock flag runs any agent without calling an LLM.
```

### Tweet 7:
```
What's in the repo:

- 1100+ tests
- 16 examples (research, triage, invoices, monitoring, data analysis)
- CLI: run, compile, build, deploy, debug, profile, serve-api
- Docker + Kubernetes configs
- VS Code extension with LSP + autocomplete
- Debugger with trace inspection
- Profiler with token/cost/latency per agent
```

### Tweet 8:
```
GitHub: https://github.com/annapurnaagenticsolutions/axon

MIT licensed. No CLA, no dual license, no "commercial use requires paid plan."

Built by @annapurnaagntic

If you've been frustrated by agent framework boilerplate, this is for you.
```

---

## 3. Reddit Post (r/programming or r/LocalLLaMA)

**Timing:** Thursday (Day 2 after HN)
**Format:** Screenshot-lead, link in comments

### Title:
```
[Show] AXON: A typed DSL for autonomous agents that compiles to Python + TypeScript
```

### Body:
```
I built a programming language for AI agents where agents, tools, memory, RAG, and flows are first-class language constructs.

The motivation: every agent framework today is a library on top of a language never designed for agents. The result is 500+ lines of boilerplate, no type safety, and runtime errors that should be compile errors.

AXON takes the SQL approach: when a domain gets complex enough, it gets its own language.

Key features:
- Type-safe agent/tool/flow definitions (compile-time checking)
- Multi-target compilation (Python MCP servers + TypeScript modules)
- RAG, memory, flows as language primitives
- 1100+ tests, 16 examples
- Docker, K8s, VS Code extension, debugger, profiler
- --mock mode to run without API keys

Side-by-side comparison with LangChain in the repo README.
GitHub: https://github.com/annapurnaagenticsolutions/axon

Try it:
git clone [repo]
cd axon
pip install -e ".[dev]"
axon run examples/hello.ax --mock
```

---

## 4. Dev.to Cross-Post

**Timing:** Friday (Day 3)
**Format:** Full blog post cross-posted from GitHub README

Use the same content as `why-we-built-axon.md` (now with corrected URLs and counts) but formatted for Dev.to:
- Add `#agents #ai #programming #opensource` tags
- Use Dev.to's liquid tags for code blocks
- Add a "Discussion" prompt at the end
