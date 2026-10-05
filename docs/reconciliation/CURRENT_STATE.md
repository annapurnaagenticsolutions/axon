# AXON Platform Reconciliation — Current State

Date: 2026-10-05  
Scope: AXON + Open Enterprise AgentOps Mesh  
Principle: preserve working code; consolidate ownership before adding features.

## Executive finding

AXON is already substantially beyond a compiler prototype. It contains a compiler/IR, executing runtime, Rust parser/type checker/IR compiler, multi-agent runtime, model routing, tracing/debugging/replay, package management, CI tooling, persistence, memory, OpenTelemetry exporters, sandbox abstractions and deployment tooling.

AgentOps Mesh is strongest as an assurance/policy/evidence reference implementation. Several of its runtime-facing services overlap with AXON and should not evolve independently.

## Canonical AXON capabilities

### Compiler and language
- Parser, AST, validator and type checker.
- AXON IR compiler/schema.
- Python/TypeScript/MCP/Go/Rust code generation surfaces.
- Rust-native parser, validator, type checker and IR compiler.
- LSP, formatter, diagnostics and VS Code tooling.

### Runtime
- Executing runtime and async runtime.
- Agent lifecycle and supervision.
- Checkpoint/restore and persistence.
- In-memory and Redis/NATS messaging.
- Service registry/discovery and remote dispatch.
- Provider registry/plugins and model router.
- Tool registry, permissions, secret management and sandbox abstractions.
- Semantic memory/RAG abstractions.
- Metrics and OpenTelemetry/OTLP exporters.

### Developer assurance already present
- Eval harness and evaluators.
- Debugger, profiler and trace replay.
- Regression comparison.
- Chaos/load testing.
- CI template generation and project quality gates.

## Canonical Mesh capabilities

Mesh should remain the canonical source for higher-level assurance semantics until migrated behind AXON contracts:
- deterministic policy guardrails;
- approval workflow;
- risk classification;
- evidence vault;
- audit event bus;
- certification/readiness logic;
- identity/secrets boundary modelling;
- RBAC/tenant-readiness checks;
- connector contract/readiness evaluation;
- benchmark/scenario assets.

## Confirmed documentation drift

1. `docs/RUNTIME_BOUNDARY.md` describes a much older mock-only runtime boundary while `AXON_STATE_AND_PLAN.md` and current source expose live providers, distributed runtime, lifecycle, checkpoints and more.
2. `ENHANCEMENT_ROADMAP.md` lists WASM and Go/Rust codegen as pending, while current CI builds WASM and `src/axon/codegen/` already contains `go.py` and `rust.py`.
3. Mesh documentation references older AXON capability/test counts.
4. `CHANGELOG.md` does not represent the current implementation breadth.
5. Repository status language varies between prototype/alpha/beta/pre-production.

## Immediate rule

Do not add another runtime, gateway, memory service, trace platform or generic evaluator until ownership is reconciled and the existing implementation is tested.

## Recommended canonical boundary

- **AXON owns:** language, IR, compiler, target adapters, runtime-neutral contracts, portability/conformance, normalized traces.
- **AXON Assurance owns:** policy/authority tests, recovery/side-effect tests, protocol conformance and cross-runtime equivalence.
- **External standards/platforms own:** MCP transport, A2A transport, hosted agent execution, generic sandboxing, generic observability storage.
- **Mesh becomes:** assurance/reference assets feeding AXON Assurance rather than an independently expanding runtime platform.
