# Codex Handoff — Reconciliation Batch 1

Use this as the local Codex ExecPlan.

## Mission

Reconcile AXON and AgentOps Mesh before implementing new product features. Preserve behavior; eliminate architecture/documentation ambiguity.

## Non-negotiable constraints

1. Do not introduce paid SaaS dependencies.
2. Default test path must require no OpenAI/Anthropic/other paid API keys.
3. Do not delete working behavior.
4. Do not create a third runtime, tracing system, gateway or memory service.
5. Prefer MCP, A2A and OpenTelemetry.
6. Any live provider integration must have deterministic fixtures/recordings.
7. Keep compiler core free from provider SDK dependencies.
8. Do not make large-scale refactors before the baseline suite passes.
9. Treat source/tests as stronger evidence than stale documentation.
10. Record cost implications for every proposed hosted dependency.

## Workstreams

Use separate worktrees/subagents where available.

### A — Baseline
- Run all commands in `VERIFIED_TEST_BASELINE.md`.
- Save exact outputs/test counts.
- Fix only test-environment breakage required to establish baseline.
- Do not hide failures.

### B — Documentation truth
Reconcile:
- README.md
- AXON_STATE_AND_PLAN.md
- ENHANCEMENT_ROADMAP.md
- CHANGELOG.md
- docs/ARCHITECTURE.md
- docs/RUNTIME_BOUNDARY.md
- Mesh README/cross-project references.

Generate capability/status information from one source where practical.

### C — Ownership mapping
Use `OVERLAP_MATRIX.md`.
For every duplicate, identify:
- canonical owner;
- callers;
- tests;
- migration risk;
- whether Mesh should consume AXON output or retain independent assurance logic.

No code moves in this subtask unless trivial and behavior-preserving.

### D — Adapter design
Draft a versioned Target Adapter ABI:
- validate;
- compile;
- capability_report;
- run_fixture;
- normalize_trace;
- cost_estimate.

Map existing native/MCP code to this interface before writing A2A/OpenAI/Cloudflare adapters.

### E — Offline contract
Design and test:
- `--offline`;
- no network/model calls;
- deterministic provider/tool fixtures;
- no telemetry egress.

## Required outputs

Update/add:
- CURRENT_STATE.md
- OVERLAP_MATRIX.md
- INDUSTRY_BUILD_VS_INTEGRATE.md
- TARGET_ARCHITECTURE.md
- MIGRATION_PLAN.md
- VERIFIED_TEST_BASELINE.md

Also produce:
- `CAPABILITY_MANIFEST.json`
- `TARGET_ADAPTER_RFC.md`
- `TRACE_IR_RFC.md`
- `MESH_MIGRATION_MAP.md`

## Stop condition for Batch 1

Do **not** implement A2A/OpenAI/Cloudflare target adapters yet.

Stop when:
- baseline tests are actually run;
- stale docs are reconciled;
- canonical ownership is agreed in code/docs;
- Target Adapter ABI and normalized Trace IR are reviewable;
- offline execution invariant is specified and tested at architecture level.

The next batch begins with A2A target implementation, then OpenAI Agents, then Cloudflare Agents.
