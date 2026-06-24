# AXON Runtime RFCs

Runtime RFCs are design proposals for any behavior that could cross the current AXON runtime boundary: executing agent method bodies, calling providers, dispatching tools, mutating memory, indexing RAG data, executing flows, or replaying traces.

Current RFCs:

| RFC | Title | Status | Purpose |
|---|---|---|---|
| [0001](0001-minimal-non-executing-runtime.md) | Minimal Non-Executing Runtime Plan | Draft | Defines the first runtime architecture boundary without enabling live execution. |
| [0002](002-expression-type-checking.md) | Expression Type Checking | Accepted | Static type checking using the expression AST. Non-executing. |
| [0003](003-provider-abstraction-runtime.md) | Provider Abstraction Runtime | Draft | Provider plugin protocol for real model calls. |
| [0004](0004-minimal-executing-agent-runtime.md) | Minimal Executing Agent Runtime | Accepted | First end-to-end executing runtime: mock tools, expression evaluator, AEL traces, memory persistence. |
| [0005](0005-flow-execution-engine.md) | Flow Execution Engine | Accepted | Orchestrates multi-stage AXON flows with typed data passing. |
| [0006](0006-rag-indexing-retrieval-runtime.md) | RAG Indexing and Retrieval Runtime | Accepted | Vector indexing, chunking, and similarity search for RAG pipelines. |
| [0007](0007-trace-replay-runtime.md) | Trace Replay Runtime | Accepted | Exact and fuzzy trace replay with event matching and deterministic reproduction. |
| [0008](0008-multi-agent-message-passing-runtime.md) | Multi-Agent Message-Passing Runtime | Accepted | Named agent execution, `delegate` expression, and in-memory message bus. |
| [0009](0009-persistent-agent-memory.md) | Persistent Agent Memory | Accepted | Semantic memory with `remember`, `recall`, `forget`, embeddings, and persistence. |
| [0010](0010-streaming-runtime.md) | Streaming Runtime | Draft | Sync-runtime streaming of model provider responses with per-chunk trace events. |
| [0011](0011-agent-lifecycle-control.md) | Agent Lifecycle & Control | Draft | External CLI control for spawning, pausing, resuming, and terminating agent instances. |
| [0012](0012-agent-supervision-tree.md) | Agent Supervision Tree | Draft | Erlang/OTP-inspired supervision with restart strategies for agent groups. |
| [0013](0013-hot-reload-source-watching.md) | Hot-Reload & Source Watching | Draft | Poll-based file watching with automatic agent re-spawn on source change. |
| [0014](0014-persistence-checkpoint-restore.md) | Persistence: Checkpoint & Restore | Draft | Durable agent state snapshots and restore for fault tolerance. |
| [0015](0015-metrics-observability.md) | Metrics & Observability | Draft | Runtime metrics collection, export, and CLI observability. |
| [0016](0016-streaming-runtime-hardening.md) | Streaming Runtime Hardening | Draft | Real-time streaming output collector, lifecycle integration, and comprehensive tests. |
| [0017](0017-rest-api-server.md) | REST API Server | Draft | FastAPI server exposing agent lifecycle, supervision, metrics, and WebSocket streaming. |
| [0018](0018-persistence-postgresql.md) | PostgreSQL-backed Persistence | Draft | SQLite/PostgreSQL persistence store for memory, traces, and checkpoints. |
| [0019](0019-opentelemetry-tracing.md) | OpenTelemetry Tracing & Correlation IDs | Draft | Trace/span IDs and context propagation for end-to-end observability. |
| [0020](0020-docker-production-deployment.md) | Docker Hardening & Production Deployment | Draft | Hardened Docker images, docker-compose, and Kubernetes manifests. |
| [0021](0021-load-testing-chaos-engineering.md) | Load Testing & Chaos Engineering | Draft | Concurrent agent spawn/execution tests and failure injection suite. |
| [0022](0022-secret-management.md) | Secret Management & Secure Configuration | Draft | Pluggable secret backends (env, file, keyring, Vault) with audit logging. |
| [0023](0023-polyglot-architecture-ir.md) | Polyglot Architecture & IR | Draft | Language-agnostic IR, modular backends, capability-based security, polyglot runtimes. |

Use `axon runtime-rfc-template` to draft future proposals.


Runtime-plan documentation lives in `docs/RUNTIME_PLAN.md`. Use it with Runtime RFC #001 to understand the current non-executing runtime-planning workflow and the required corpus checks.
