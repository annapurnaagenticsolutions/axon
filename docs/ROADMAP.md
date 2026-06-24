# AXON Prototype Roadmap

## Current milestone

The Phase 1 prototype now has a stable parser/tooling foundation:

- declaration parsing
- validation
- syntax diagnostics
- AST snapshots
- golden error snapshots
- source formatter
- formatted-source golden snapshots
- FastMCP stub generation
- smoke testing
- provider config loading
- project skeleton commands
- static trace preview and trace-log reading
- release notes / changelog generation for handoff bundles
- release bundle checklist integration for manifest-backed handoff artifacts
- release handoff checklist generation for reviewer-ready bundle summaries

## Next safe areas

1. Keep documentation and CLI help aligned with implemented behavior.
2. Add small validation rules only when behavior is unambiguous.
3. Add runtime capability only behind explicit boundaries (RFC-gated).
4. Preserve provider-agnostic configuration and never put API keys in `.ax` files.

## Completed in Phase 1

- type checker
- token budget estimator
- provider abstraction runtime (mock provider with model completion)
- tool implementation adapters (basic expression-to-Python translation for `act`, `let`, blocks)
- memory runtime (semantic memory with `remember`, `recall`, `forget`)
- RAG indexing and retrieval runtime
- flow execution engine
- trace replay (exact event matching)
- LSP / IDE integration

## Phase 2 ideas

- real provider integration (OpenAI, Anthropic) behind optional extras
- advanced tool implementation adapters (loops, pattern matching, async)
- agent lifecycle management (spawn, pause, resume, terminate)
- distributed multi-agent runtime
- streaming response support



## Example corpus quality gate

Task #22 expanded the checked-in example corpus beyond minimal fixtures. New language changes should keep all `.ax` files in `examples/` parseable, valid, smoke-testable, formatter-idempotent, covered by formatted-source golden snapshots, and capable of generating compilable FastMCP stub code. Add a new realistic example whenever a major AXON declaration or runtime concept is introduced.

## Runtime boundary

Phase 1 runtime RFCs #001–#009 have been implemented. The prototype now executes agent expressions with mocked providers, full trace capture, checkpoint/restore, multi-agent delegation, and persistent semantic memory. New runtime work must still go through the RFC process: state which syntax it executes, how external calls are mocked or gated, how secrets remain redacted, and how failures surface.

## Runtime RFC process

Runtime work must start with `axon runtime-rfc-template` and must reference `docs/RUNTIME_BOUNDARY.md`. The RFC must define scope, non-goals, provider impact, tool dispatch impact, memory/RAG/flow impact, trace guarantees, security, tests, rollback, and acceptance criteria before implementation begins.

## Runtime RFC #001

Task #39 adds `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`, the first concrete runtime proposal. Task #40 implements the first non-executing runtime-plan boundary with `axon runtime-plan`: inspect validated declarations, report disabled capabilities, and avoid provider calls, tool dispatch, memory mutation, RAG indexing, flow orchestration, and trace replay. Task #41 adds runtime-plan golden snapshots so future runtime-planning changes are explicit and reviewable.



## Runtime-plan documentation workflow

Task #43 documents runtime planning as one coherent non-executing workflow. Before any runtime-adjacent implementation, review:

- `docs/RUNTIME_BOUNDARY.md`
- `docs/RUNTIME_PLAN.md`
- `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`

Run:

```bash
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root .
axon runtime-plan-corpus .
```

Runtime plans must keep `declaration_inspection` enabled and all live execution capabilities disabled until a later runtime RFC explicitly changes that boundary.

## Runtime-plan review gate

Before runtime-plan output, snapshots, corpus checks, or runtime-boundary documentation change, reviewers should run `axon runtime-plan-review` and `axon runtime-plan-review-check .` and follow `docs/RUNTIME_PLAN_REVIEW.md`. Any change that enables provider calls, tool dispatch, method execution, memory mutation, RAG indexing/retrieval, flow execution, trace replay, secret resolution, or FastMCP runtime import must first go through a Runtime RFC.

### Runtime governance gate

Before real runtime work starts, runtime-plan-adjacent changes should pass:

```bash
axon runtime-governance .
```

This is an inspection-only governance gate and does not enable execution capabilities.

- runtime-governance evidence handoff integration

## Release handoff workflow

The standard release handoff workflow is documented in `docs/RELEASE_ARTIFACTS.md` and driven by `axon release-artifacts`. It remains inspection-only and should be kept separate from future runtime execution work.


## Phase 1 foundation audit

Before runtime implementation, run `axon foundation-audit .` to verify the parser, validator, snapshots, examples, docs, release handoff, and runtime boundary are still aligned. This checkpoint protects the non-executing runtime boundary before method execution, provider calls, tool dispatch, memory mutation, RAG indexing, RAG retrieval, flow execution, trace replay, secret resolution, or FastMCP runtime import are introduced.
