# AXON Target Architecture

Date: 2026-10-05

## Product thesis

AXON should not compete as another agent framework. It should become a **provider-neutral agent compiler + portability/conformance layer**, with assurance built around authority, protocol, recovery and side-effect correctness.

```text
.ax source
    |
    v
Parser -> Type Checker -> Canonical AXON IR
                         |
          +--------------+---------------+
          |              |               |
          v              v               v
      Policy IR      Decision IR      Context IR
          |              |               |
          +--------------+---------------+
                         |
                 Target Adapter ABI
                         |
      +------------------+------------------+
      |          |          |        |      |
      v          v          v        v      v
    Native      MCP        A2A     OpenAI  Cloudflare
    AXON                           Agents   Agents
      |          |          |        |      |
      +------------------+------------------+
                         |
                 Normalized Trace IR
                         |
                 AXON Assurance
```

## Canonical layers

### 1. Language frontend
Own:
- AXON syntax;
- parser/AST;
- static validation;
- type system;
- language-server diagnostics.

Do not couple this layer to provider SDKs.

### 2. Canonical AXON IR
IR must describe semantics, not one framework implementation:
- agents and callable methods;
- tools and typed inputs/outputs;
- flows/delegation;
- memory/context requirements;
- decisions;
- permissions/capabilities;
- approvals;
- budgets;
- lifecycle/recovery expectations;
- observable events.

### 3. Portable IR extensions

**Policy IR**
- principal/agent;
- action;
- resource/tool;
- constraints;
- approval requirements;
- delegation limits.

**Decision IR**
- finite choices;
- typed input;
- confidence/abstention policy;
- cost/latency/privacy constraints;
- backend-independent semantics.

**Context IR**
- source/provenance;
- freshness;
- sensitivity;
- authority/scope;
- retention/expiry.

Do not build a standalone Context OS product yet; first make these semantics useful inside portability and assurance.

### 4. Target Adapter ABI

Every target must implement a common contract:
- `validate(ir)`;
- `compile(ir)`;
- `capability_report(ir)`;
- `run_fixture(ir, fixture)`;
- `normalize_trace(native_trace)`;
- `cost_estimate(ir)`.

Initial adapters:
1. native AXON;
2. MCP;
3. A2A;
4. OpenAI Agents API;
5. Cloudflare Agents.

### 5. Normalized Trace IR

One event model for comparison:
- goal/input;
- model/decision;
- tool call/result;
- delegation;
- approval;
- capability check;
- context read/write;
- checkpoint/recovery;
- side effect;
- error;
- completion.

Use OpenTelemetry IDs/semantics where practical rather than creating proprietary tracing infrastructure.

### 6. AXON Assurance

Differentiate from generic LLM evaluation.

Primary suites:
- authority/capability preservation;
- delegation attenuation;
- approval replay/substitution;
- MCP/A2A/WebMCP contract conformance;
- checkpoint/retry duplicate-side-effect tests;
- context/provenance integrity;
- provider/runtime portability equivalence;
- cost/latency regression.

## Offline-first contract

All core commands must work without paid APIs:

```bash
axon compile --offline
axon test --offline
axon portability --offline
axon assurance --offline
```

Offline mode guarantees:
- no external model calls;
- no provider credentials;
- deterministic fixtures/recordings;
- no telemetry egress unless explicitly configured.

Live compatibility tests are opt-in:

```bash
axon portability --live --target openai
```

## Explicit non-goals

- another generic agent chat framework;
- proprietary A2A transport;
- proprietary MCP replacement;
- generic memory SaaS;
- generic model gateway;
- generic observability dashboard;
- generic cloud sandbox;
- proprietary foundation decision model in phase 1.
