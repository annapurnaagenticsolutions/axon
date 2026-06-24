# AXON Runtime RFC #008 — Multi-Agent Message-Passing Runtime

**Status:** Draft
**Created:** 2026-06-09
**Owner:** axon-dev

> Runtime work must be proposed before implementation. This template is intentionally strict because runtime behavior can call providers, dispatch tools, mutate memory, index RAG data, execute flows, or replay traces.

---

## SUMMARY

Propose a minimal multi-agent message-passing runtime for AXON. This enables multiple `agent` declarations in a single source file to communicate via a lightweight message bus, and allows the user to run any agent by name (not just the first one). The runtime provides:

1. **`--agent <Name>` CLI flag** — run a specific agent's `run()` method by name
2. **Agent message bus** — `send(recipient, message)` and `receive()` for async inter-agent communication
3. **Agent pipeline composition** — sequential execution of multiple agents with output forwarding

The intended output is a working multi-agent AXON file where agents cooperate:
```axon
agent Producer {
    model: @mock/gpt
    fn run() -> Str { "data" }
}

agent Consumer {
    model: @mock/gpt
    fn run(input: Str) -> Str { input }
}
```

And the CLI can run either agent, or a pipeline: `axon run multi.ax --agent Producer` or `axon run multi.ax --agent Consumer --arg input=hello`.

## PROBLEM / MOTIVATION

AXON already supports `delegate AgentName(args)` for agent-to-agent calls, but this is synchronous and tightly coupled — the caller must know the callee's name and signature. Real multi-agent systems need:

1. **Named agent execution** — A source file may define multiple agents (e.g., `Router`, `WorkerA`, `WorkerB`). Currently only the first agent's `run()` is executed. Users need `axon run file.ax --agent WorkerA`.

2. **Decoupled communication** — Agents should communicate via messages, not just direct delegation. This enables patterns like:
   - Producer-Consumer (one agent produces data, another consumes it)
   - Router-Workers (a router agent distributes tasks to worker agents)
   - Fan-out/Fan-in (one agent sends to many, results are collected)

3. **Composition** — Pipelines of agents should be easy to declare and run without writing imperative delegation code.

This RFC keeps the scope narrow: in-memory message bus, no persistence, no distributed execution.

## CURRENT BOUNDARY CHECK

Confirm the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md` and state exactly what this RFC proposes to change.

Required confirmations:

- [x] This RFC explicitly permits multi-agent body execution and message passing.
- [x] This RFC uses existing mock provider and tool dispatch from RFC #004.
- [x] Do not dispatch real tools without mocking.
- [x] Do not resolve, print, or snapshot API keys.
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.
- [x] Deterministic test doubles (in-memory message bus) defined.
- [x] Document exactly which AXON syntax subset the runtime will execute — listed below.
- [x] Trace emission guarantees defined below.

## PROPOSED RUNTIME SCOPE

Add a minimal multi-agent message-passing runtime:

1. **Named agent execution** (`--agent` CLI flag)
   - `axon run file.ax --agent WorkerA` executes `WorkerA.run()` instead of the first agent
   - Error if the named agent does not exist or has no `run()` method

2. **Agent message bus** (`src/axon/message_bus.py`)
   - `send(recipient: str, message: Any)` — sends a message to a named agent's mailbox
   - `receive(timeout_ms: Int = 0) -> Any | None` — receives a message from own mailbox (non-blocking)
   - `receive_blocking(timeout_ms: Int = 5000) -> Any` — blocks until message arrives or timeout
   - In-memory store: `dict[str, deque[Any]]` mapping agent name to message queue
   - Messages are any JSON-serializable value

3. **Agent pipeline composition**
   - `axon run file.ax --pipeline "Producer -> Consumer"` executes agents in sequence
   - Output of stage N becomes input (via message bus or direct args) to stage N+1
   - Simple string syntax: comma-separated agent names, arrow `->` for forwarding

4. **Runtime integration**
   - `RuntimeConfig` gains `agent_name: Optional[str]` and `pipeline: Optional[str]` fields
   - Message bus instance is shared across all agent executions in a single `run`
   - Each agent gets `send` and `receive` functions injected into its evaluation scope

## NON-GOALS

- Do not implement unrelated runtime subsystems.
- Do not broaden provider/tool/memory behavior beyond this RFC.

## AXON SYNTAX EXECUTED

This RFC executes the following constructs inside agent bodies:

```axon
// Named agent execution (CLI flag)
// axon run multi.ax --agent Producer
agent Producer {
    model: @mock/gpt
    fn run() -> Str {
        "produced data"
    }
}

// Message passing between agents
agent Router {
    model: @mock/gpt
    fn run() -> Str {
        send("WorkerA", {task: "process", data: "hello"})
        let result = receive_blocking()
        result
    }
}

agent WorkerA {
    model: @mock/gpt
    fn run() -> Str {
        let msg = receive_blocking()
        msg.data
    }
}

// Delegation (existing RFC #004 behavior)
let answer = delegate Expert(question: "what is AI?")

// Pipeline composition (CLI flag)
// axon run multi.ax --pipeline "Router -> WorkerA"
```

Specifically:
- `send(recipient, message)` — sends message to another agent's mailbox
- `receive()` / `receive_blocking()` — reads from own mailbox
- `delegate AgentName(args)` — existing synchronous delegation
- `--agent <Name>` — CLI flag to select which agent to run
- `--pipeline "A -> B -> C"` — CLI flag for sequential agent composition

## PROVIDER PLUGIN IMPACT

No changes to the provider plugin protocol. Each agent still uses its own `model:` reference, resolved through existing provider resolution. Mock mode (`--mock`) still applies globally. No new provider calls introduced by message passing.

## TOOL DISPATCH IMPACT

No changes to tool dispatch. Each agent uses its own `tools:` list. Message passing does not dispatch tools. Existing tool dispatch boundaries and permissions remain unchanged.

## MEMORY / RAG / FLOW IMPACT

- **Message bus: NEW** — In-memory message queues between agents. Not persisted.
- **Memory:** Memory store is shared across agents in a single run (same instance passed to all agents). Existing RFC #004 behavior unchanged.
- **RAG:** No changes to RAG indexing or retrieval. Existing RFC #006 behavior unchanged.
- **Flow:** No changes to flow execution. Existing RFC #005 behavior unchanged.

## TRACE AND OBSERVABILITY GUARANTEES

The following AEL trace events are emitted during multi-agent execution:

1. `agent_start` — `agent_name`, `source_file` (emitted for each agent executed)
2. `agent_end` — `agent_name`, `result_type`, `result_summary`
3. `message_sent` — `from_agent`, `to_agent`, `message_summary`
4. `message_received` — `agent_name`, `message_summary`
5. `delegate_call` / `delegate_return` — (existing events, unchanged)

Intentionally not recorded: full message content (only summary), mailbox state, message queue sizes.

## SECURITY AND SECRET HANDLING

No new secret handling introduced. Multi-agent runtime:
- Uses existing provider resolution (no new API keys)
- Message bus is in-memory only (no network access for messaging)
- Message summaries in traces are truncated to 50 characters
- No message persistence to disk

## TESTING STRATEGY

- [x] unit tests for message bus (send, receive, blocking, timeout, multiple agents)
- [x] unit tests for named agent execution (`--agent` flag)
- [x] unit tests for pipeline composition (`--pipeline` flag)
- [x] end-to-end test: two agents send/receive messages
- [x] end-to-end test: pipeline of three agents
- [x] trace emission tests (message_sent, message_received)
- [x] existing tests remain passing (no regression)
- [x] no accidental network calls in compiler-core tests

## ROLLBACK PLAN

Multi-agent runtime is additive:
1. Delete `src/axon/message_bus.py` to remove message passing
2. Remove `--agent` and `--pipeline` CLI flags from `src/axon/cli.py`
3. Remove `agent_name` and `pipeline` from `RuntimeConfig`
4. Remove `send`/`receive` scope injection from `_evaluate_body`
5. Parser, validator, formatter, codegen, and docs workflows unaffected — they already parse `agent` declarations statically
6. Default behavior (first agent's `run()`) continues unchanged when no `--agent` flag is given

## ACCEPTANCE CRITERIA

- [x] RFC #008 document accepted.
- [x] `axon run` supports `--agent <Name>` flag.
- [x] `axon run` supports `--pipeline "A -> B"` flag.
- [x] Message bus supports send/receive between agents.
- [x] Named agent execution works when multiple agents are defined.
- [x] Pipeline composition forwards outputs between agents.
- [x] Trace events emitted for message passing.
- [x] All existing tests pass (no regression).
- [x] CLI reference updated with `--agent` and `--pipeline` options.

## OPEN QUESTIONS

- **Deferred:** Distributed multi-agent execution (networked agents), persistent message queues, agent scheduling/cron, agent supervisor patterns, agent lifecycle management (spawn/halt).
- **Future RFC #009:** Persistent agent memory — long-term memory across runs with vector storage and recall.
