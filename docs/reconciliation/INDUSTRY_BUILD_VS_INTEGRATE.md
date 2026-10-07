# Industry Build vs Integrate

Date: 2026-10-07

Goal: avoid rebuilding fast-moving commodity infrastructure.

| Area | Decision | Reason |
|---|---|---|
| MCP transport/server protocol | INTEGRATE | Mature interoperability standard; AXON should compile/expose targets |
| MCP protocol conformance | INTEGRATE | Use the official MCP conformance suite; do not build a competing protocol TCK |
| A2A communication | INTEGRATE | Stable v1.0 standard for agent-to-agent interoperability |
| A2A protocol validation/TCK | INTEGRATE | Use official A2A Inspector/TCK; AXON adds semantics above wire compatibility |
| WebMCP | INTEGRATE + COMPILE | Emerging browser-agent contract; AXON may generate/test typed action contracts |
| OpenAI Agents API | TARGET ADAPTER | Hosted durable agent execution, orchestration, compaction, tools and sandbox already provided |
| Cloudflare Agents | TARGET ADAPTER | Durable identity/state/scheduling/recovery and edge hosting already provided |
| Generic hosted sandbox | INTEGRATE | OpenAI/Cloudflare and others supply execution isolation |
| Generic agent gateway | INTEGRATE | Existing gateways cover routing/auth/observability; do not compete at commodity layer |
| Generic tracing dashboard | INTEGRATE | OTel ecosystem + existing LLM observability products are mature |
| Generic memory API | DO NOT BUILD | Crowded and increasingly native to runtimes |
| Generic repo security scanner | DO NOT BUILD | Codex Security and existing SAST ecosystems cover this |
| Decision-model API | ABSTRACT | Define AXON Decision IR; target OpenAI Decisions/Jev/Laya/CLM/rules rather than own model initially |
| Generic agent portability specification | DO NOT CLAIM AS MOAT | Cross-framework agent specifications and portability efforts already exist |
| Typed multi-target agent compiler | BUILD | AXON already has language/IR/compiler assets; differentiate through typed semantics and target compilation |
| Protocol conformance | INTEGRATE | Delegate wire/spec correctness to official MCP/A2A suites |
| Cross-runtime semantic equivalence | BUILD | Verify meaning, authority, recovery and side effects across targets after protocol conformance passes |
| Authority/capability assurance | BUILD | Protocol/runtime providers do not fully solve delegated authority correctness |
| Recovery/side-effect assurance | BUILD | High-value gap beyond ordinary LLM evals and protocol TCKs |
| Policy IR + test generation | BUILD/INTEGRATE | Own portable abstraction; compile to existing policy engines where appropriate |
| WebMCP contract generation + assurance | BUILD | Higher-value layer than simple WebMCP linting |

## Differentiation boundary

AXON must not market "portability" or "conformance" as if those are unoccupied categories.

The defensible proposition is:

> **Typed agent source -> canonical semantic IR -> multiple runtime targets -> normalized execution evidence -> proof of semantic, authority, recovery and side-effect equivalence.**

Official protocol tests answer:
- "Does this MCP/A2A implementation speak the protocol correctly?"

AXON Assurance should answer:
- "Did the same agent contract preserve its meaning and authority after compilation to another runtime?"
- "Did retries/recovery duplicate a side effect?"
- "Did delegation broaden authority?"
- "Did approvals, context provenance, budgets or decision semantics change?"

## Current external anchors

- OpenAI DevDay 2026: Codex cloud, multi-agent CLI, code review, Codex Security, Decisions API, Agents API.
- OpenAI Agents API: managed sessions/orchestration/context compaction/recovery with optional sandbox.
- Cloudflare Agents: durable identity, state, connections, scheduling and recovery.
- MCP 2026-07-28: stateless core, routing, extensions and authorization hardening; official conformance suite exists.
- A2A v1.0: production-ready interoperability; official Inspector/TCK initiatives exist.
- Open Agent Specification research demonstrates that cross-framework agent specification/comparison is already an active category.

## Cost rule

Default order:
1. deterministic fixtures/mocks;
2. open-source/local execution;
3. Cloudflare free allocation/startup credits;
4. paid hosted models only for explicit compatibility/evaluation tests.

Normal CI must not require paid model calls.
