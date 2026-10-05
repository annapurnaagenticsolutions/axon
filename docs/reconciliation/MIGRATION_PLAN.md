# AXON Platform Migration Plan

Date: 2026-10-05

## Constraints

- Free/near-zero cash burn.
- Preserve working features.
- Normal CI must not make paid model calls.
- Prefer standards and existing hosted primitives.
- No broad rewrite.
- No new standalone repository until architecture boundaries are proven.

## Phase 0 — Reconcile reality

1. Run Python, Rust, WASM and conformance suites locally.
2. Generate one machine-readable capability manifest from tested code.
3. Correct stale runtime/roadmap/changelog/status documentation.
4. Mark each Mesh capability as migrate, retain-as-fixture, integrate or retire.
5. Add/refresh root `AGENTS.md` for Codex with architecture invariants and no-paid-API CI rule.

Exit:
- documentation matches executable code;
- one verified test baseline;
- no contradictory runtime claims.

## Phase 1 — Stabilize canonical IR

1. Document current IR schema and invariants.
2. Add versioned IR envelope.
3. Define target-adapter ABI.
4. Define normalized trace envelope.
5. Add explicit capability/permission representation where missing.
6. Add offline-mode invariant tests.

Exit:
- existing native/MCP targets implement the adapter contract without behavior regression.

## Phase 2 — Standards adapters

Order:
1. A2A v1.0;
2. OpenAI Agents API;
3. Cloudflare Agents.

Rules:
- use official SDKs/protocols;
- adapter optional dependencies only;
- fixture/recording backend mandatory;
- no live API in default CI.

Exit:
- one representative AXON agent compiles to at least three targets.

## Phase 3 — Portability Lab

Add:
- target capability diff;
- normalized fixture runner;
- normalized trace comparison;
- semantic equivalence assertions;
- cost/latency metadata;
- authority/policy equivalence report.

Primary acceptance test:

> One AXON program -> 3+ runtimes -> normalized traces -> automatic detection of semantic/authority differences.

## Phase 4 — AXON Assurance consolidation

Migrate reusable Mesh semantics:
- policy guardrails;
- approval tests;
- risk/scenario library;
- evidence envelope;
- benchmark cases;
- connector-contract tests.

Do not migrate:
- duplicate provider runtime;
- duplicate trace transport;
- duplicate generic registry where AXON already owns it.

Mesh remains available as historical/reference architecture while assurance semantics move behind AXON contracts.

## Phase 5 — Decision IR

Backends:
1. deterministic rules;
2. deterministic fixture model;
3. optional OpenAI Decisions API;
4. optional Jev/Laya/CLM adapters.

AXON owns the typed decision abstraction, not the model.

## Phase 6 — WebMCP Contract Studio prototype

Only after core portability works.

Build:
- action discovery;
- typed contract proposal;
- confirmation/risk annotations;
- WebMCP code generation;
- contract tests;
- browser-agent assurance.

Avoid building a generic schema linter.

## Cost policy

- Local fixtures/mocks: default.
- GitHub public CI: default.
- Cloudflare free/startup credits: hosted test/demo default.
- External paid model calls: explicit live test only.
- Any new recurring SaaS dependency requires an ADR with OSS/self-hosted alternative.
