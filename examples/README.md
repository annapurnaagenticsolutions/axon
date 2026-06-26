# AXON Example Corpus

This directory contains small but realistic AXON examples used as parser,
validator, code-generation, smoke-test, and documentation fixtures.

## Examples

| File | Purpose |
| --- | --- |
| `hello.ax` | Minimal tool + agent example. |
| `hello_run.ax` | Minimal executing runtime example: one agent, one tool, one mock model call. |
| `types.ax` | Type alias parsing, including record and literal union aliases. |
| `prompts.ax` | Prompt declarations with inline `@budget` annotations. |
| `rag.ax` | Minimal RAG declaration and agent reference to `ProductDocs.retrieve`. |
| `flow.ax` | Minimal flow declaration with stage arrows. |
| `trace_preview.ax` | Static AEL trace-preview example with `think`, `act`, `observe`, and `store`. |
| `github_triage.ax` | GitHub issue triage workflow with prompts, tools, memory, and actions. |
| `customer_support.ax` | RAG-backed customer support workflow with escalation. |
| `invoice_extraction.ax` | PDF invoice extraction into a structured finance record. |
| `monitoring_alerts.ax` | Scheduled monitoring agent with anomaly detection and alerting. |
| `meeting_notes.ax` | Meeting transcription, summarization, action-item extraction, and note saving. |
| `data_analysis.ax` | CSV analysis agent with sandboxed Python and chart generation. |
| `debate.ax` | Multi-agent debate-oriented agent plus flow pipeline. |
| `code_review.ax` | **Real-world demo**: reads a file, LLM code review, saves output. Run with `--live --provider groq`. |
| `content_summarizer.ax` | **Real-world demo**: fetches a URL, LLM summary, saves output. Run with `--live --provider groq`. |
| `data_query.ax` | **Database tool demo**: SQLite operations with `db.query`, `db.execute`, `db.transaction`, schema introspection. |
| `run_demos.py` | Demo runner script for both real-world agents. `python examples/run_demos.py --live --provider groq` |

The examples are intentionally conservative: they validate and smoke-test against
Phase 1 compiler behavior without requiring provider calls, vector databases, or
real external tool execution. The `code_review.ax` and `content_summarizer.ax`
demos go further — they work end-to-end in mock mode and with live providers
using `--live --provider groq|openai|anthropic`.
