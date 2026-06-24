# AXON Runtime RFC #001 — Minimal Non-Executing Runtime Plan

**Status:** Draft
**Created:** 2026-06-01
**Owner:** AXON Maintainers

> This RFC intentionally does **not** permit live AXON agent execution. It defines the minimum runtime architecture boundary needed before any later RFC can safely add provider calls, tool dispatch, memory mutation, RAG indexing, flow orchestration, or trace replay.

---

## SUMMARY

This RFC proposes a minimal, non-executing runtime layer for AXON. The goal is to create a small runtime design boundary that can hold future execution concepts without changing the current compiler/tooling behavior.

The proposed runtime layer may construct validated, inspectable runtime plans from parsed AXON declarations, but it must not execute AXON method bodies, call model providers, dispatch tools, mutate memory, build RAG indexes, execute flows, or replay traces.

The intended output is a deterministic runtime plan object or report that answers:

- which agents exist
- which methods they expose
- which tools they reference
- which prompts, RAG blocks, flows, and type aliases are available
- which trace events are statically previewable
- which runtime capabilities are intentionally disabled

This gives AXON a safe bridge between compiler tooling and future execution work.

## PROBLEM / MOTIVATION

AXON has a strong parser, validator, code generator, formatter, smoke harness, trace model, trace preview, project quality gate, and documentation foundation. The next major risk is moving too quickly from static tooling into live runtime behavior.

Runtime behavior is sensitive because it can:

- call external provider APIs
- dispatch tools that may access files, networks, databases, tickets, or Slack
- mutate memory stores
- index documents into vector databases
- execute multi-agent flows
- produce trace logs that may contain user data or secrets

Before any live behavior is implemented, AXON needs a minimal runtime design contract that preserves the current safety boundary while making future runtime RFCs easier to reason about.


## Runtime Capability Boundary

The only enabled runtime capability is:

```text
declaration_inspection
```

The following execution capabilities remain disabled by Runtime RFC #001:

```text
method_execution
provider_calls
tool_dispatch
memory_mutation
rag_indexing
rag_retrieval
flow_execution
trace_replay
secret_resolution
fastmcp_runtime_import
```

## CURRENT BOUNDARY CHECK

The current boundary from `docs/RUNTIME_BOUNDARY.md` remains in force.

Required confirmations for this RFC:

- [x] Do not execute AXON agent bodies until a later accepted RFC explicitly allows it.
- [x] Do not call model providers from compiler-core modules.
- [x] Do not dispatch `act` calls to real tools.
- [x] Do not resolve, print, or snapshot API keys or other secrets.
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.
- [x] Define deterministic test doubles before adding live provider or tool behavior.
- [x] Document exactly which AXON syntax subset the runtime will inspect.
- [x] State trace emission guarantees before runtime actions are implemented.

This RFC proposes to add only a conceptual non-executing runtime plan boundary. It does not propose a live execution engine.

## PROPOSED RUNTIME SCOPE

The minimal runtime may eventually provide a small set of safe, deterministic primitives:

1. **Runtime plan construction**
   - Input: parsed and validated AXON declarations.
   - Output: structured metadata describing available agents, methods, tools, prompts, RAG blocks, flows, and disabled capabilities.

2. **Capability gating**
   - Every potentially live subsystem starts disabled by default.
   - The plan explicitly marks provider calls, tool dispatch, memory writes, RAG indexing, flow execution, and trace replay as unavailable.

3. **Static trace preview attachment**
   - The runtime plan may reference static trace preview events extracted by the existing `trace-preview` subsystem.
   - These events are previews only, not evidence of actual execution.

4. **Deterministic testability**
   - The runtime plan must be generated without network access, provider SDK imports, FastMCP imports, secret resolution, filesystem mutation, or background processes.

5. **Future extension point**
   - Later RFCs may extend this plan into mock execution, tool dispatch, provider calls, memory runtime, RAG runtime, flow execution, or trace replay.
   - Each extension must have its own RFC.

## NON-GOALS

- Do not execute `fn` method bodies.
- Do not interpret AXON expressions.
- Do not call `@plan`, `@summarize`, `@classify`, `@answer`, or any other model-backed operation.
- Do not dispatch `act ToolName(...)` to real tools.
- Do not mutate `Memory<ShortTerm>`, `Memory<Semantic>`, or `Memory<Episodic>`.
- Do not build or query vector indexes.
- Do not execute `flow` DAGs.
- Do not replay trace logs.
- Do not import provider SDKs.
- Do not import FastMCP in compiler-core modules.
- Do not add non-stdlib dependencies to the compiler core.
- Do not resolve environment variables containing secrets.

## AXON SYNTAX EXECUTED

No AXON syntax is executed by this RFC.

The proposed non-executing runtime may inspect these declarations and fields:

```axon
import { WebSearch } from "axon:tools/web"

type Priority = "low" | "medium" | "high"

prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {
    """
    Summarize: {text}
    """
}

tool WebSearch(query: Str) -> Result<List<Any>, ToolError> {
    /// Searches the web.
    http.get(query)
}

agent ResearchAgent {
    model: @anthropic/claude-haiku
    tools: [WebSearch]
    memory: Memory<ShortTerm>(capacity: 500)

    fn run(topic: Str) -> Result<Report, AgentError> {
        think "Need to research {topic}"
        let result = act WebSearch(query: topic)?
        store memory.working["result"] = result
        Ok(@summarize(result))
    }
}
```

Inspection may record that the method body contains `think`, `act`, `store`, and model-backed `@summarize` syntax. It must not run any of them.

## PROVIDER PLUGIN IMPACT

No provider plugin is called or required by this RFC.

Provider-related behavior remains limited to:

- parsing provider model strings such as `@anthropic/claude-haiku`
- reading `axon.toml` safely through the existing config loader
- reporting provider names and defaults without resolving secrets
- marking provider execution as disabled in runtime plan metadata

No provider SDK imports are allowed in compiler-core modules.

Future provider execution requires a separate RFC that defines:

- provider protocol interface
- mock provider behavior
- timeout behavior
- retry behavior
- token/cost accounting
- redaction rules
- failure surfaces
- trace fields

## TOOL DISPATCH IMPACT

No tool dispatch is allowed by this RFC.

Tool-related behavior remains limited to:

- parsing `tool` declarations
- validating references from `agent.tools`
- generating FastMCP stubs
- smoke-loading generated stubs with fake FastMCP
- including tool metadata in a non-executing runtime plan

Future tool dispatch requires a separate RFC that defines:

- dispatch permissions
- mock tool registry
- real tool registry
- sandboxing expectations
- argument schema validation
- result schema validation
- retry and timeout behavior
- error propagation
- trace emission
- audit logging

## MEMORY / RAG / FLOW IMPACT

No memory mutation, RAG indexing, RAG retrieval, or flow execution is allowed by this RFC.

The minimal runtime plan may inspect:

- `memory: Memory<ShortTerm>` declarations
- `rag` block metadata such as source, chunker, embedder, and store strings
- `flow` stage declarations and raw body text

It must mark each of these as non-executing.

Future RFCs should split these subsystems:

1. Memory runtime RFC
2. RAG indexing RFC
3. RAG retrieval RFC
4. Flow execution RFC
5. Multi-agent scheduling RFC

## TRACE AND OBSERVABILITY GUARANTEES

This RFC permits no runtime trace emission because no runtime action occurs.

It may allow a runtime plan to reference existing static trace preview events from `trace-preview` with clear labeling:

```text
source: static-preview
executed: false
```

A future execution RFC must define:

- exact event ordering
- required fields
- timestamps
- agent and method identifiers
- redaction rules
- provider/tool latency fields
- error event shape
- replay boundaries
- what is intentionally not recorded

## SECURITY AND SECRET HANDLING

The minimal non-executing runtime plan must be secret-safe.

Required rules:

- Do not resolve environment placeholders such as `${OPENAI_API_KEY}`.
- Do not print provider API keys.
- Do not include secrets in snapshots.
- Do not include secrets in runtime plan JSON.
- Do not make network calls.
- Do not read arbitrary project files beyond explicitly provided AXON/config paths.
- Do not write trace logs unless a later RFC allows trace emission.
- Do not import provider SDKs.
- Do not import FastMCP in compiler-core runtime planning code.

## TESTING STRATEGY

A future implementation of this RFC must include:

- [x] unit tests for runtime plan construction
- [ ] tests proving no provider SDKs are imported
- [ ] tests proving no FastMCP import is required
- [ ] tests proving secrets are redacted or absent
- [ ] tests proving provider/tool/memory/RAG/flow execution flags are disabled by default
- [x] tests proving runtime plan JSON is stable
- [ ] tests proving malformed declarations fail through existing parser/validator paths
- [ ] tests proving static trace preview events are labeled as non-executed
- [x] docs updated with runtime plan behavior

## ROLLBACK PLAN

Because this RFC proposes only a non-executing plan boundary, rollback is simple:

- remove the runtime-plan module or command if implemented later
- keep parser, validator, formatter, codegen, smoke, config, and trace-preview unchanged
- keep `docs/RUNTIME_BOUNDARY.md` as the governing boundary
- keep all existing project quality gates unchanged

No user AXON source files should require migration.

## ACCEPTANCE CRITERIA

This RFC draft is accepted only when:

- [ ] `docs/RUNTIME_BOUNDARY.md` still clearly states that live runtime execution is not implemented.
- [x] The minimal runtime plan design is implemented as an inspection-only Task #40 foundation.
- [ ] Any implementation remains stdlib-only in compiler core.
- [ ] Any implementation emits no provider calls, tool calls, memory writes, RAG indexing, flow execution, or trace replay.
- [ ] Any implementation has deterministic tests.
- [ ] Any implementation is covered by docs and handoff guidance.
- [ ] Later live runtime behavior is deferred to separate RFCs.

## OPEN QUESTIONS

- Resolved in Task #40: expose both a Python API and `axon runtime-plan` CLI command.
- Open: decide later whether runtime-plan output belongs in `axon project-info`.
- Should static trace preview events be embedded in the runtime plan or referenced separately?
- What is the first live runtime RFC after this: mock tool dispatch, mock provider completion, or memory runtime?
- Should the runtime plan schema become a stable JSON contract for external tooling?
