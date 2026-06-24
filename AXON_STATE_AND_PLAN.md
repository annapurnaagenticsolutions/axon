# AXON State & Execution Plan
> Snapshot: 2026-06-17
> Based on full codebase audit of D:\vision_agentic\axon

---

## Completed (Phase 1 Foundation)

### Compiler & Tooling
- Full parser for all 7 declaration types: `agent`, `tool`, `prompt`, `rag`, `flow`, `type`, `import`
- Static validator with 10+ semantic checks + type checker
- Source formatter with golden snapshots; AST snapshots; golden error snapshots
- 30+ CLI commands: `syntax`, `validate`, `build`, `serve`, `smoke`, `run`, `trace-*`, `check-project`, `release-*`, `runtime-plan`, etc.
- FastMCP stub generation (`axon build`)
- Release workflow: handoff checklist, bundle manifest, governance evidence, release notes
- CI, pre-commit hooks, dependency/hygiene audits

### Executing Runtime (RFCs #001–#009 implemented)
- Expression parser/evaluator for AEL (`act`, `let`, `think`, `observe`, `store`, `if`, `for`, `match`, `try`, `delegate`, `send`/`receive`)
- Mock provider runtime with `model.complete()` and `@`-operator adapters
- Tool registry with sandboxed execution and HTTP builtins
- Trace emitter, reader, replay with exact event matching
- Checkpoint/restore (`--checkpoint`, `--memory`)
- Multi-agent in-memory message bus
- Persistent semantic memory (`remember`, `recall`, `forget`)
- RAG registry, chunker, embedder, indexer, vector store abstractions
- Flow executor with DAG scheduling
- Provider plugin abstractions (OpenAI, Anthropic, Mock — optional extras)
- Resilience layer: retry, circuit breaker, metrics
- LSP server (basic diagnostics, completion, symbols)

### Quality
- 80+ pytest tests; 14 `.ax` example files with full coverage

---

## Gaps vs Full Vision

| Area | Status | What's Missing |
|------|--------|----------------|
| **Real Provider Calls** | ✅ Partial | Plugin abstractions exist; live wiring is Phase 5. Mock providers by default |
| **Agent Lifecycle** | ✅ Complete | `spawn`, `pause`, `resume`, `terminate`, supervision tree |
| **Distributed Runtime** | ✅ Partial | In-memory bus/registry; cross-process mesh pending |
| **Advanced Concurrency** | ✅ Complete | `go`/`await`, `chan`/`select`, worker pools wired |
| **Pattern Matching** | ✅ Complete | Exhaustive `match` with binding + guards |
| **Worker Pools** | ✅ Complete | `PoolExpr` → `WorkerPool` with dispatch strategies |
| **Model Router** | ✅ Complete | `CHEAPEST`/`FASTEST`/`QUALITY`/`FALLBACK` strategies |
| **Real Tool Modules** | ✅ Partial | `fs`, `http` implemented; `db`, `sandbox`, `slack`, `github` pending |
| **Production Packaging** | ✅ Complete | Docker, `axon deploy`, `axon eval`, health checks, graceful shutdown |
| **IDE Ecosystem** | ✅ Partial | VS Code extension + syntax highlighting; debugger + profiler pending |

---

## Completed Phases

### Phase 2 — Distributed & Production Runtime
- **2A** Live providers (OpenAI, Anthropic) with streaming
- **2B** Agent lifecycle (`spawn`/`pause`/`resume`/`terminate`), supervision tree
- **2C** Concurrency (`go`/`await`, `chan`/`select`, worker pools)
- **2D** Distributed runtime (message bus, service registry, model router, OpenTelemetry)
- **2E** Developer experience (VS Code extension, LSP, package manager)

### Phase 3 — Production Hardening
- `axon eval` benchmark harness with regression detection
- Graceful shutdown with signal handling
- Health check endpoint (`/health`)
- `axon add` / `axon remove` package manager
- `axon deploy` (Docker + Fly.io)

### Phase 4 — Toolchain & Community
- TypeScript codegen target (`axon compile --target ts`)
- VS Code extension with TextMate grammar
- LSP client for autocomplete + diagnostics

---

## Next: Phase 5 — Debugging & Advanced Tooling

1. **AXON Debugger**: step-through AEL traces, inspect memory, breakpoints
2. **Profiler**: execution time profiling per agent/method
3. **Enhanced tool modules**: `db` (SQLite/PostgreSQL), `sandbox` (restricted execution)
4. **Cross-process distributed runtime**: Redis/NATS message bus

---

## Recommended Execution Plan

### Phase 2A — Live Provider Integration (2–3 sprints)
1. **Real provider execution** behind `[providers]` optional extra
   - Wire `OpenAIProvider.complete()` and `AnthropicProvider.complete()` to real APIs
   - Add `axon run --provider openai` / `--provider anthropic` flags
   - Add streaming response support (`Stream<Str>`) with SSE parsing
2. **Streaming runtime RFC** (#010) and implementation
3. **Real tool modules** for `fs` and `http` (not stubs)
4. Integration tests with recorded VCR cassettes (no live calls in CI)

### Phase 2B — Agent Lifecycle & Control (2 sprints)
1. **Agent lifecycle runtime RFC** (#011)
   - `spawn AgentName()`, `pause`, `resume`, `terminate`
   - Process-isolated agent workers via subprocess / sandbox
   - Hot-reload of `.ax` source without restarting runtime
2. **Agent supervision tree**: parent agent monitors child health, restarts on failure

### Phase 2C — Concurrency & Worker Pools (2 sprints)
1. **Concurrency runtime RFC** (#012)
   - Full `go` / `await` futures executor
   - `chan<T>` / `select` runtime with async event loop
   - `workers: Pool<Agent>(size: N)` with round-robin / least-loaded dispatch
2. **Pattern matching hardening**: exhaustive checks, enum binding, guard clauses

### Phase 2D — Distribution & Production (3 sprints)
1. **Distributed multi-agent runtime RFC** (#013)
   - Message bus over Redis / NATS
   - Agent discovery and service registry
   - Distributed tracing (OpenTelemetry exporter)
2. **Model Router**: cost-optimized, latency-optimized, quality-first strategies
3. **Production packaging**
   - Docker image with multi-stage build
   - `axon deploy` command for cloud (initial target: Fly.io / Railway)
   - Prometheus metrics endpoint, structured logging

### Phase 2E — Developer Experience (2 sprints)
1. **VS Code extension** for syntax highlighting, diagnostics, go-to-definition
2. **Enhanced LSP**: autocomplete for tool names, parameter hints, inline errors
3. **AXON debugger**: step-through AEL traces, inspect memory, breakpoints
4. **Package manager**: `axon add user/repo` for importing community agents/tools

---

## Immediate Next Step

**Phase 2A, Sprint 1**: Wire live provider calls behind existing `OpenAIProvider` / `AnthropicProvider` plugins and add a `--live` flag to `axon run`. The mock runtime already works; this is the smallest upstream change that unlocks real execution.
