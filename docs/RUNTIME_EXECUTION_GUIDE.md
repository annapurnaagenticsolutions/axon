# AXON Runtime Execution Guide

This guide covers how to execute AXON agents using the Phase 2 runtime system.

## Overview

The AXON runtime provides:
- **Provider abstraction** — Call OpenAI, Anthropic, or mock providers
- **Tool dispatch** — Execute tools via `act` expressions
- **Memory** — Persistent key-value and semantic memory
- **RAG** — Document indexing and retrieval
- **Flow execution** — DAG-based multi-stage pipelines
- **Trace replay** — Deterministic replay from captured traces

## Quick Start

### Execute an Agent

```bash
axon run my_agent.ax
```

### With Provider Selection

```bash
axon run my_agent.ax --provider openai --model gpt-4
axon run my_agent.ax --provider anthropic --model claude-3-5-sonnet
```

### With Trace Capture

```bash
axon run my_agent.ax --trace-output trace.jsonl
```

### Replay from Trace

```bash
axon run my_agent.ax --replay trace.jsonl
```

## Provider Configuration

Providers are configured via environment variables:

| Provider | Environment Variable | Required |
|----------|---------------------|----------|
| OpenAI | `OPENAI_API_KEY` | Yes |
| Anthropic | `ANTHROPIC_API_KEY` | Yes |
| Mock | None | No |

## Runtime Architecture

```
AXON Source File
      |
      v
  Parser (AST)
      |
      v
RuntimeExecutor
  |-- ProviderRegistry (OpenAI, Anthropic, Mock)
  |-- ToolRegistry (Built-in, Mock, User-defined)
  |-- MemoryStore (Key-value, Semantic)
  |-- RagRegistry (Document collections)
  |-- TraceEmitter (AEL events)
      |
      v
  Output + Trace Log
```

## Tool Implementation

Tools are dispatched via `act` expressions:

```axon
fn search(query: Str) -> Result<List<Str>, Error> {
    act Search(query: query)
}
```

### Built-in Tools

- `Search` — Keyword search over indexed documents
- `Fetch` — Retrieve content by ID

### Custom Tools

Register custom tools in Python:

```python
from axon.tool_registry import MockToolRegistry

registry = MockToolRegistry()
registry.register("MyTool", my_tool_impl)
```

## Memory Usage

### Working Memory

```axon
fn process(data: Str) -> Str {
    let cached = recall(key: "last_result")?
    // ... use cached ...
}
```

### Semantic Memory

```python
from axon.memory_store import MemoryStore

store = MemoryStore()
store.remember("concept", vector=embedding)
results = store.recall_similar("concept", top_k=5)
```

## Flow Execution

Flows execute as DAGs:

```axon
flow Pipeline(input: Str) -> Str {
    stage Process(input: Str) -> Str
    stage Analyze(data: Str) -> Str
    stage Format(result: Str) -> Str

    Process -> Analyze
    Analyze -> Format
}
```

Run with:

```bash
axon run my_flow.ax --flow Pipeline
```

## Error Handling

The runtime uses `Result<T, E>` for all operations:

- `Ok(value)` — Success
- `Err(error)` — Failure with message

Use the `?` operator to propagate errors:

```axon
fn fetch_and_process(url: Str) -> Result<Str, Error> {
    let data = fetch(url: url)?  // Returns early on error
    process(data: data)
}
```

## Resilience

The runtime includes retry and circuit breaker patterns:

- **Retry** — Exponential backoff for transient failures
- **Circuit Breaker** — Opens after consecutive failures, recovers after timeout

Configure via `RetryConfig` and `CircuitBreakerConfig`.

## Testing

Use mock providers for deterministic tests:

```python
from axon.providers import MockProviderPlugin
from axon.runtime import RuntimeConfig, execute_runtime

config = RuntimeConfig(source_path=Path("test.ax"))
result = execute_runtime(config)
```

## Security

- No secrets in trace logs
- API keys from environment variables only
- No arbitrary code execution
- All runtime behavior behind explicit CLI commands

## References

- `docs/RUNTIME_BOUNDARY.md` — Security boundaries
- `docs/runtime-rfcs/` — RFC specifications
- `src/axon/runtime.py` — Implementation
