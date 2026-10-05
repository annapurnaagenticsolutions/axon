# Industry Build vs Integrate

Date: 2026-10-05

Goal: avoid rebuilding fast-moving commodity infrastructure.

| Area | Decision | Reason |
|---|---|---|
| MCP transport/server protocol | INTEGRATE | Mature interoperability standard; AXON should compile/expose targets |
| A2A communication | INTEGRATE | Stable v1.0 standard for agent-to-agent interoperability |
| WebMCP | INTEGRATE + COMPILE | Emerging browser-agent contract; AXON may generate/test contracts |
| OpenAI Agents API | TARGET ADAPTER | Hosted durable agent execution, orchestration, compaction, tools and sandbox already provided |
| Cloudflare Agents | TARGET ADAPTER | Durable identity/state/scheduling/recovery and edge hosting already provided |
| Generic hosted sandbox | INTEGRATE | OpenAI/Cloudflare and others supply execution isolation |
| Generic agent gateway | INTEGRATE | Existing gateways cover routing/auth/observability; do not compete at commodity layer |
| Generic tracing dashboard | INTEGRATE | OTel ecosystem + existing LLM observability products are mature |
| Generic memory API | DO NOT BUILD | Crowded and increasingly native to runtimes |
| Generic repo security scanner | DO NOT BUILD | Codex Security and existing SAST ecosystems cover this |
| Decision-model API | ABSTRACT | Define AXON Decision IR; target OpenAI Decisions/Jev/Laya/CLM/rules rather than own model initially |
| Agent portability compiler | BUILD | Existing runtimes increase need for provider-neutral semantics |
| Cross-runtime conformance | BUILD | Differentiated: verify semantic/authority equivalence across targets |
| Authority/capability assurance | BUILD | Protocol/runtime providers do not fully solve delegated authority correctness |
| Recovery/side-effect assurance | BUILD | High-value gap beyond ordinary LLM evals |
| Policy IR + test generation | BUILD/INTEGRATE | Own portable abstraction; compile to existing policy engines where appropriate |
| WebMCP contract generation + assurance | BUILD | Higher-value layer than simple WebMCP linting |

## Current external anchors

- OpenAI DevDay 2026: Codex cloud, multi-agent CLI, code review, Codex Security, Decisions API, Agents API.
- OpenAI Agents API: managed sessions/orchestration/context compaction/recovery with optional sandbox.
- Cloudflare Agents: durable identity, state, connections, scheduling and recovery.
- MCP 2026-07-28: stateless core, routing, extensions and authorization hardening.
- A2A v1.0: production-ready agent interoperability; use official SDK/TCK rather than proprietary transport.

## Cost rule

Default order:
1. deterministic fixtures/mocks;
2. open-source/local execution;
3. Cloudflare free allocation/startup credits;
4. paid hosted models only for explicit compatibility/evaluation tests.

Normal CI must not require paid model calls.
