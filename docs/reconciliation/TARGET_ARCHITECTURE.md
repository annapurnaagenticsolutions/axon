# AXON Target Architecture

Date: 2026-10-07

## Product thesis

AXON should not compete as another agent framework, protocol implementation, generic portability format, or observability product.

It should become a **typed multi-target agent compiler + semantic assurance layer**.

The differentiated contract is:

> **Compile one typed agent contract to multiple runtimes, then prove that meaning, authority, recovery behavior and side effects remain within declared bounds.**

Protocol wire compatibility is delegated to official MCP/A2A conformance suites.

```text
.ax source
    |
    v
Parser -> Type Checker -> Canonical AXON Semantic IR
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
              Protocol conformance gates
             (official MCP/A2A suites)
                         |
                 Normalized Trace IR
                         |
                 AXON Assurance
                         |
          semantic / authority / recovery /
             side-effect equivalence
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

### 2. Canonical AXON Semantic IR
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
- observable events;
- declared side effects and idempotency expectations where relevant.

The IR is the foundation of AXON's differentiation. "Portable JSON" alone is not.

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

Do not build a standalone Context OS product yet; first make these semantics useful inside compilation and assurance.

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

An adapter must declare unsupported/lossy semantics explicitly; silent semantic degradation is a failure.

### 5. Protocol conformance gate

Do not recreate official protocol TCKs.

- MCP targets run the official MCP conformance suite.
- A2A targets run the official A2A validation/TCK tooling as available.
- AXON consumes those results as prerequisites for higher-level assurance.

### 6. Normalized Trace IR

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

### 7. AXON Assurance

Differentiate from generic LLM evaluation and protocol validation.

Primary suites:
- semantic equivalence across targets;
- authority/capability preservation;
- delegation attenuation;
- approval replay/substitution;
- checkpoint/retry duplicate-side-effect tests;
- context/provenance integrity;
- declared-loss detection;
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
- competing MCP/A2A protocol TCK;
- generic portability file format as the product;
- generic memory SaaS;
- generic model gateway;
- generic observability dashboard;
- generic cloud sandbox;
- proprietary foundation decision model in phase 1.
