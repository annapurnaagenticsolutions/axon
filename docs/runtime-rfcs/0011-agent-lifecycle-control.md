# AXON Runtime RFC #011 — Agent Lifecycle & Control

**Status:** Draft  
**Created:** 2026-06-17  
**Owner:** AXON Maintainers  

> This RFC proposes external lifecycle control for AXON agents: spawning, pausing, resuming, and terminating agent instances via CLI commands and a runtime-managed agent process registry.

---

## SUMMARY

Propose an `AgentLifecycleManager` that:

1. Tracks running agent instances with a unique ID, name, status (`running`, `paused`, `terminated`), and runtime context.
2. Provides CLI commands:
   - `axon agent spawn <source> --name <name> --arg key=value` — start a new agent instance
   - `axon agent pause <name>` — pause a running agent (suspend message processing)
   - `axon agent resume <name>` — resume a paused agent
   - `axon agent terminate <name>` — force-terminate an agent
   - `axon agent status <name>` — show agent state and metrics
3. Uses in-process agent workers for the Phase 2B prototype (subprocess isolation deferred to Phase 2D).
4. Emits AEL trace events for lifecycle transitions (`agent_spawn`, `agent_pause`, `agent_resume`, `agent_terminate`).

---

## PROBLEM / MOTIVATION

Currently `axon run` executes a single agent to completion and exits. There is no way to:

- Start an agent and keep it alive for interactive or event-driven use
- Pause an agent to inspect its memory state
- Resume an agent after modification
- Terminate a long-running agent gracefully
- Query what agents are currently running

These capabilities are essential for production deployments where agents run as persistent services.

---

## CURRENT BOUNDARY CHECK

- [ ] **This RFC enables external lifecycle control of AXON agent instances** — The primary change
- [x] Do not call real model providers unless `--no-mock` is passed — Existing guard preserved
- [x] Do not dispatch `act` calls to real tools without permission — Existing sandbox preserved
- [x] Do not resolve, print, or snapshot API keys — Existing secret handling preserved
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary — No new dependencies
- [x] Define deterministic test doubles before adding live provider behavior — Mock provider already defined
- [x] Document exactly which AXON syntax subset the runtime will execute — No new AEL syntax in this RFC
- [x] State trace emission guarantees before runtime actions are implemented — Listed below

---

## PROPOSED RUNTIME SCOPE

### In-Process Agent Workers (Phase 2B)

For the Phase 2B prototype, agent instances run in the same Python process as the CLI. Each spawned agent gets its own:

- `RuntimeExecutor` with independent `RuntimeConfig`
- `TraceEmitter` (optional, can write to separate trace files)
- `MemoryStore` (independent, can be checkpointed)
- `SandboxedToolRegistry` (shared builtins, but independent tool registries are also possible)

Running agents execute in a background thread that polls a work queue. The queue can be:
- A `run()` method invocation (one-shot execution)
- A message from the message bus (for multi-agent coordination)

### Agent Status States

| State | Meaning | Transitions |
|---|---|---|
| `idle` | Agent loaded but not executing | `spawn` → `running` |
| `running` | Actively executing | `pause` → `paused`, `terminate` → `terminated` |
| `paused` | Execution suspended, state preserved | `resume` → `running`, `terminate` → `terminated` |
| `terminated` | Execution stopped, resources released | None (final) |
| `error` | Execution failed with an error | `terminate` → `terminated` |

### CLI Commands

```bash
# Spawn a new agent instance (returns instance ID)
axon agent spawn examples/bot.ax --name bot-1 --arg q=world

# Pause
axon agent pause bot-1

# Resume
axon agent resume bot-1

# Terminate
axon agent terminate bot-1

# Check status
axon agent status bot-1

# List all running agents
axon agent list
```

---

## NON-GOALS

- Do not add `spawn` / `pause` / `resume` / `terminate` AEL syntax in this RFC.
- Do not implement subprocess-isolated agent workers (deferred to Phase 2D).
- Do not implement hot-reload of `.ax` source in this RFC.
- Do not implement agent supervision trees (Phase 2B Sprint 2).

---

## AXON SYNTAX EXECUTED

No new AEL syntax. All lifecycle control is external (CLI commands).

---

## PROVIDER PLUGIN IMPACT

None. Lifecycle management is orthogonal to provider calls.

---

## TOOL DISPATCH IMPACT

None. Tool dispatch remains unchanged.

---

## MEMORY / RAG / FLOW IMPACT

- Each spawned agent gets its own `MemoryStore`.
- `--memory` flag on `spawn` loads memory from a file.
- `--checkpoint` flag on `spawn` persists memory after each run.

---

## TRACE AND OBSERVABILITY GUARANTEES

When tracing is enabled:

1. `agent_spawn(instance_id, agent_name, source_file)` emitted on spawn.
2. `agent_pause(instance_id, agent_name)` emitted on pause.
3. `agent_resume(instance_id, agent_name)` emitted on resume.
4. `agent_terminate(instance_id, agent_name, reason)` emitted on terminate.
5. Agent execution traces continue to be emitted as normal AEL events.

---

## SECURITY AND SECRET HANDLING

No changes. API keys and secrets continue to be handled via `ProviderConfig`.

---

## TESTING STRATEGY

- Unit test: `AgentLifecycleManager` spawn/pause/resume/terminate/status
- Unit test: State transitions and invalid transitions (e.g., pause a terminated agent)
- Unit test: Trace events emitted for lifecycle transitions
- Unit test: Multiple agents can coexist with independent memory
- Integration test: `axon agent spawn` → `status` → `terminate` via CLI
- No live network calls in CI (mock provider only)

---

## ROLLBACK PLAN

If lifecycle management causes instability:

1. The `axon agent` subcommands can be deprecated or hidden.
2. `axon run` continues to work unchanged (single-shot execution).

---

## ACCEPTANCE CRITERIA

- [ ] `axon agent spawn <source>` starts a new agent and prints instance ID
- [ ] `axon agent pause <name>` changes status to `paused`
- [ ] `axon agent resume <name>` changes status back to `running`
- [ ] `axon agent terminate <name>` stops the agent
- [ ] `axon agent status <name>` shows state, source file, and last output
- [ ] `axon agent list` shows all non-terminated agents
- [ ] Trace events `agent_spawn`, `agent_pause`, `agent_resume`, `agent_terminate` emitted
- [ ] All existing tests pass without modification

---

## OPEN QUESTIONS

1. Should spawned agents support a `--watch` mode that re-runs on file changes (lightweight hot-reload)?
2. Should the lifecycle manager expose a REST API for remote control (Phase 2D concern)?
3. Should `spawn` support `--background` vs `--foreground` execution modes?
