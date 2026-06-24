# AXON Runtime RFC #012 — Agent Supervision Tree

**Status:** Draft  
**Created:** 2026-06-17  
**Owner:** AXON Maintainers  

> This RFC proposes an Erlang/OTP-inspired supervision tree for AXON agents. A `Supervisor` manages a group of child agents, monitors their health, and applies configurable restart strategies when they fail.

---

## SUMMARY

Propose an `AgentSupervisor` that:

1. Manages a group of child agent definitions (source file + name + args).
2. Uses `AgentLifecycleManager` to spawn children.
3. Monitors child health via background polling thread.
4. Applies restart strategies on failure:
   - `one_for_one`: restart only the failed child
   - `one_for_all`: restart all children when one fails
   - `rest_for_one`: restart the failed child and all children started after it
5. Enforces restart intensity limits (max_restarts in max_seconds) and terminates all children if exceeded.
6. Emits AEL trace events for child start, child terminate, and supervisor shutdown.

---

## PROBLEM / MOTIVATION

In production, agents are not single-shot scripts — they are long-running services that may crash due to provider errors, tool bugs, or unexpected inputs. Without supervision:

- A crashed agent stays dead until manually restarted.
- One agent failure can cascade to others if they depend on shared resources.
- There's no central place to define "if this agent fails, restart it up to N times".

AXON needs a lightweight supervision primitive that keeps agent groups alive.

---

## CURRENT BOUNDARY CHECK

- [ ] **This RFC enables automatic restart of failed agent instances** — The primary change
- [x] Do not call real model providers unless `--no-mock` is passed — Existing guard preserved
- [x] Do not dispatch `act` calls to real tools without permission — Existing sandbox preserved
- [x] Do not resolve, print, or snapshot API keys — Existing secret handling preserved
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary — No new dependencies
- [x] Define deterministic test doubles before adding live provider behavior — Mock provider already defined

---

## PROPOSED RUNTIME SCOPE

### Supervisor Concepts

A `Supervisor` is a background monitor thread that:

1. Holds a list of `ChildSpec` entries: `{source_path, name, args, mock, provider_name}`.
2. Spawns each child via `AgentLifecycleManager.spawn()` at startup.
3. Polls all children every N seconds.
4. If a child reaches `ERROR` status:
   - Apply the configured `RestartStrategy`.
   - Track restart counts and timestamps.
   - If intensity limit is exceeded, terminate all children and enter `shutdown` state.
5. Can be stopped cleanly via `stop()`.

### Restart Strategies

| Strategy | Behavior on child failure |
|---|---|
| `one_for_one` | Restart only the failed child. |
| `one_for_all` | Terminate all children, then restart all children. |
| `rest_for_one` | Terminate the failed child and all children started after it, then restart them in order. |

### Restart Intensity

```
max_restarts: 5
max_seconds: 60
```

If more than 5 restarts happen across all children within any 60-second window, the supervisor terminates all children and shuts down.

---

## NON-GOALS

- Do not implement distributed supervision (cross-process or cross-node) in this RFC.
- Do not implement transient/temporary child specs (all children are permanent).
- Do not add supervisor declarations to AXON source syntax (deferred to Phase 2D).
- Do not implement supervisor hierarchies (supervisors supervising supervisors).

---

## AXON SYNTAX EXECUTED

No new AEL syntax. Supervision is external (CLI / programmatic API).

---

## PROVIDER PLUGIN IMPACT

None.

---

## TOOL DISPATCH IMPACT

None.

---

## MEMORY / RAG / FLOW IMPACT

None.

---

## TRACE AND OBSERVABILITY GUARANTEES

1. `supervisor_start(name, strategy, child_count)` emitted on supervisor start.
2. `supervisor_child_start(name, child_name)` emitted when a child is started.
3. `supervisor_child_restart(name, child_name, reason)` emitted when a child is restarted.
4. `supervisor_shutdown(name, reason)` emitted when the supervisor terminates due to max intensity.

---

## SECURITY AND SECRET HANDLING

No changes.

---

## TESTING STRATEGY

- Unit test: Supervisor starts all children successfully.
- Unit test: One-for-one strategy restarts only the failed child.
- Unit test: One-for-all strategy restarts all children.
- Unit test: Rest-for-one strategy restarts failed + later children.
- Unit test: Max intensity exceeded triggers supervisor shutdown.
- Unit test: Trace events emitted for child start, restart, and shutdown.
- No live network calls in CI.

---

## ROLLBACK PLAN

If supervision causes instability:

1. Users can avoid it by not using `axon supervisor`.
2. `axon run` and `axon agent` remain unchanged.

---

## ACCEPTANCE CRITERIA

- [ ] `AgentSupervisor` class with `start()` / `stop()` / `add_child()` / `remove_child()`
- [ ] All three restart strategies implemented and tested
- [ ] Restart intensity enforcement (max_restarts / max_seconds)
- [ ] CLI `axon supervisor start <config.json>` starts a supervisor group
- [ ] CLI `axon supervisor stop <name>` stops a supervisor group
- [ ] Trace events emitted for supervision actions
- [ ] All existing tests pass without modification

---

## OPEN QUESTIONS

1. Should supervisors be declared in `.ax` source syntax (e.g., `supervisor MySup { children: [...], strategy: one_for_one }`)?
2. Should the supervisor expose metrics (restart counts, child uptime) via an API?
3. Should we support child-level `max_restarts` in addition to supervisor-level intensity?
