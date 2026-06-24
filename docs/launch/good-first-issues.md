# Good First Issues — Create These on GitHub After Repo Creation

Create 10 issues with the `good first issue` label. Copy-paste each section below as a GitHub issue.

---

## Issue 1: Add sentiment analysis example
**Label:** good first issue, documentation

Create a new `.ax` file `examples/sentiment_analysis.ax` that demonstrates:
- A `SentimentAnalyzer` agent with a `classify_sentiment` tool
- Input type with `text: Str` and `language: Str = "en"`
- Output type with `sentiment: "positive" | "negative" | "neutral"` and `confidence: Float`
- Use `@mock/gpt` model so it runs without API keys

Validate with: `axon syntax examples/sentiment_analysis.ax && axon validate examples/sentiment_analysis.ax`

---

## Issue 2: Add email summarizer example
**Label:** good first issue, documentation

Create `examples/email_summarizer.ax` with:
- A `EmailSummarizer` agent
- A RAG knowledge base for email context
- Tool to extract key points from email text
- Flow: receive → extract → summarize → output

---

## Issue 3: Improve TypeScript codegen for tool definitions
**Label:** good first issue, enhancement

The TypeScript code generator currently outputs tool definitions as plain functions. Improve it to generate proper TypeScript interfaces for tool inputs and outputs.

Look at `src/axon/codegen/ts.py` (or equivalent) for the current implementation.

---

## Issue 4: Add syntax highlighting for VS Code extension
**Label:** good first issue, enhancement

The VS Code extension in `vscode-axon/` needs improved syntax highlighting:
- Add highlighting for `agent`, `tool`, `rag`, `flow`, `stage` keywords
- Add highlighting for types: `Str`, `Int`, `Float`, `Bool`, `List`, `Result`, `Map`
- Add highlighting for `@model` references (e.g., `@openai/gpt-4o`)
- Add highlighting for comments (`//` and `///`)

---

## Issue 5: Write a test for flow stage ordering validation
**Label:** good first issue, testing

Write a test that verifies the compiler rejects invalid flow stage ordering:
- Flow with disconnected stages (A → B, C → D where B and C are not connected)
- Flow with circular dependencies (A → B → A)
- Flow with missing stage implementation

Add to `tests/` following existing test patterns.

---

## Issue 6: Add data validation example
**Label:** good first issue, documentation

Create `examples/data_validator.ax` with:
- A `DataValidator` agent
- A tool that validates a JSON-like structure against a schema type
- Input type for the data and schema
- Output type with `valid: Bool` and `errors: List<Str>`

---

## Issue 7: Add meeting scheduler multi-agent example
**Label:** good first issue, documentation

Create `examples/meeting_scheduler.ax` with:
- 3 agents: `CalendarAgent`, `PreferenceAgent`, `SchedulerAgent`
- A flow that coordinates between them to find a meeting time
- Demonstrate agent-to-agent communication

---

## Issue 8: Improve error messages for type mismatches
**Label:** good first issue, enhancement

When the type checker finds a mismatch (e.g., passing `Str` where `Int` was expected), the error message should include:
- The file and line number
- The expected type and actual type
- A suggestion if the types are close (e.g., `List<Str>` vs `List<Str?>`)

Look at `src/axon/typechecker/` for the current error reporting.

---

## Issue 9: Add translation pipeline example
**Label:** good first issue, documentation

Create `examples/translation_pipeline.ax` with:
- A multi-agent flow: `SourceAgent` → `TranslatorAgent` → `ReviewerAgent` → `OutputAgent`
- Each agent handles a different language
- Demonstrate flow stage chaining and intermediate types

---

## Issue 10: Write a "Getting Started" tutorial
**Label:** good first issue, documentation

Write `docs/getting-started.md` with:
- Step-by-step installation guide
- First agent: hello.ax walkthrough
- Second agent: adding a tool
- Third agent: adding RAG
- Fourth: compiling to TypeScript
- How to run with --mock mode
- How to deploy with Docker

Target audience: developer who has never used AXON before. 15-minute read.
