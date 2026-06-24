# AXON Runtime RFC #004 — Minimal Executing Agent Runtime

**Status:** Accepted
**Created:** 2026-06-08
**Accepted:** 2026-06-09
**Owner:** AXON Maintainers

> This RFC proposes the first end-to-end executing runtime for AXON. It enables `axon run hello.ax` to execute one agent, dispatch one mock tool, evaluate simple expressions, and emit a real AEL trace. No network calls. No API keys. Mock only.

---

## SUMMARY

Propose a minimal executing agent runtime that interprets simple AXON method bodies, dispatches to mock tools, and emits AEL trace events. This is the first RFC that crosses the execution boundary: method bodies run, tool calls resolve, and traces are produced — but everything remains deterministic, local, and mock-based.

The intended output is a working `axon run examples/hello.ax` that:

1. Parses `hello.ax` into AST declarations
2. Evaluates the agent's `run()` method body
3. Dispatches `act Greet(name: "World")` to the mock tool registry
4. Evaluates the tool body `"Hello, {name}!"` with parameter substitution
5. Returns `"Hello, World!"`
6. Writes a JSONL AEL trace with `agent_start`, `method_start`, `tool_dispatch`, `tool_return`, `method_return`, `agent_end` events

This is the Phase 1 deliverable defined in the AXON vision document: *"one agent, one tool, one model call. Everything else builds from there."*

---

## PROBLEM / MOTIVATION

AXON has spent Phase 0 and Phase 1a building an excellent static toolchain: parser, validator, formatter, AST snapshots, FastMCP stub generation, type checker, and runtime-plan inspector. But AXON is still a **config format** — it describes agents but does not run them.

The vision document is explicit about the risk:

> *"The most important next step before Phase 1 starts is the LLM readability test... Phase 1 deliverable: `axon run hello_agent.ax` executes — one agent, one tool, one model call."*

Without execution, AXON cannot be adopted as a language. No one adopts a programming language they cannot run. This RFC crosses that threshold safely by keeping every external call mocked.

---

## CURRENT BOUNDARY CHECK

This RFC proposes to change the execution boundary from `docs/RUNTIME_BOUNDARY.md`:

- [ ] **This RFC enables AXON agent body execution** — This is the primary change
- [ ] **This RFC enables mock tool dispatch** — Limited to tools defined in the same source file
- [x] Do not call real model providers — Mock provider only
- [x] Do not dispatch `act` calls to real tools — Mock tool registry only
- [x] Do not resolve, print, or snapshot API keys — No keys needed for mock execution
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary — No provider SDKs imported
- [x] Define deterministic test doubles before adding live provider or tool behavior — Mock provider and mock tool registry defined
- [x] Document exactly which AXON syntax subset the runtime will execute — Listed below
- [x] State trace emission guarantees before runtime actions are implemented — AEL events defined below

---

## PROPOSED RUNTIME SCOPE

Add a minimal expression evaluator and mock execution engine that:

1. **Expression evaluator** (`src/axon/evaluator.py`)
   - Evaluate `LiteralExpr` — strings, ints, bools, floats
   - Evaluate `VariableExpr` — parameter and `let` binding lookup
   - Evaluate `StringInterpolationExpr` — `{var}` substitution from scope
   - Evaluate `LetExpr` — bind value to scope, evaluate body
   - Evaluate `ReturnExpr` — return value from method
   - Evaluate `CallExpr` — dispatch to mock tool registry
   - Evaluate `OkExpr` / `ErrorExpr` — wrap in `Result[T, E]`
   - Evaluate `UnaryOpExpr` / `BinaryOpExpr` — basic arithmetic and boolean ops
   - Scope chain: parameters → `let` bindings → tool results

2. **Mock tool registry** (`src/axon/tool_registry.py`)
   - Register `ToolDecl` objects from parsed source
   - Dispatch `act ToolName(args)` by looking up the tool, evaluating its body expression with argument scope
   - Return `Result[T, ToolError]`
   - Error if tool not found, if arity mismatch, or if body evaluation fails

3. **Mock provider** (`src/axon/providers/mock_provider.py`)
   - Already exists from RFC #003 foundation
   - Used for any `@plan()`, `@summarize()`, `@classify()` calls (these may return static mock responses)
   - Not required for `hello.ax` but present for forward compatibility

4. **Trace emitter** (`src/axon/trace_emitter.py`)
   - Emit `AgentStartEvent` when execution begins
   - Emit `MethodStartEvent` when `fn run()` is entered
   - Emit `ToolDispatchEvent` when `act` is encountered
   - Emit `ToolReturnEvent` when tool body evaluates
   - Emit `MethodReturnEvent` when method returns
   - Emit `AgentEndEvent` when execution completes
   - Write events as JSONL to trace file or stdout

5. **Runtime executor update** (`src/axon/runtime.py`)
   - Replace placeholder `execute()` with real execution:
     1. Parse source → declarations
     2. Find agent → resolve `run()` method
     3. Build parameter scope from CLI args
     4. Evaluate method body via expression evaluator
     5. Handle `act` dispatch via mock tool registry
     6. Emit trace events via trace emitter
     7. Return `Result[T, AgentError]`

6. **CLI integration** (`src/axon/cli.py`)
   - `axon run examples/hello.ax` — execute with default args
   - `axon run examples/hello.ax --arg q="World"` — pass arguments
   - `axon run examples/hello.ax --trace trace.jsonl` — write AEL trace
   - `axon run examples/hello.ax --mock` — explicitly use mock mode (default)

---

## NON-GOALS

- Do not implement real provider calls (RFC #003 covers real providers)
- Do not implement real tool dispatch to external systems (separate RFC)
- Do not implement memory mutation (`store`, `memory.recall`) — separate RFC
- Do not implement RAG indexing/retrieval — separate RFC
- Do not implement flow execution — separate RFC
- Do not implement async/concurrency (`go`, `await`, `select`, `chan`) — separate RFC
- Do not implement complex control flow (`if`, `for`, `match`) in this RFC — add in RFC #005
- Do not implement `think` or `observe` as runtime effects — they are trace-only for now
- Do not implement `?` error propagation as a runtime operator — simplify to basic error wrapping
- Do not require type checking at runtime — RFC #002 handles this statically
- Do not change the AXON language syntax

---

## AXON SYNTAX EXECUTED

This RFC enables execution of the following minimal AXON subset:

```axon
tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]

    fn run(q: Str) -> Str {
        let greeting = act Greet(name: q)?
        return greeting
    }
}
```

**Permitted constructs in method bodies:**

| Construct | Evaluation |
|-----------|------------|
| `let x = expr` | Bind `expr` result to `x` in scope |
| `return expr` | Return `expr` result from method |
| `act ToolName(args)` | Dispatch to mock tool registry, evaluate tool body |
| `"Hello, {name}!"` | String interpolation from scope |
| `42`, `"text"`, `true`, `false` | Literal values |
| `x` | Variable lookup in scope |
| `Ok(expr)` | Wrap in `Ok()` result |
| `+`, `-`, `*`, `/`, `==`, `!=` | Basic arithmetic and comparison |

**Not permitted in this RFC:**
- `if/else` — deferred to RFC #005
- `for` loops — deferred
- `match` — deferred
- `go/await/select/chan` — async deferred
- `store memory...` — memory deferred
- `@plan()`, `@summarize()`, etc. — provider-backed operations deferred (mock returns static response)
- `think "..."` — trace-only, no runtime effect
- `observe ...` — trace-only, no runtime effect

---

## PROVIDER PLUGIN IMPACT

**No real provider calls.**

The only provider interaction is the mock provider from RFC #003:

```python
class MockProviderPlugin:
    """Deterministic mock provider."""
    
    def complete(self, prompt: str, model: str) -> Result[str, ProviderError]:
        return Ok(f"Mock completion for: {prompt[:50]}...")
```

If a method body contains `@plan("...")` or `@summarize("...")`, the evaluator calls the mock provider and returns a static response. This allows parsing and structure without requiring API keys.

**No API keys needed.**
**No network calls.**
**No provider SDK imports in compiler core.**

---

## TOOL DISPATCH IMPACT

**Mock tool registry only.**

Tools are dispatched by name to the mock registry:

```python
class MockToolRegistry:
    """Registry for tools defined in the current AXON source."""
    
    def register(self, tool: ToolDecl) -> None:
        ...
    
    def dispatch(self, name: str, args: dict[str, Any]) -> Result[Any, ToolError]:
        """Evaluate tool body expression with args injected into scope."""
        ...
```

- Tools must be defined in the same `.ax` file as the calling agent
- Tool body expressions are evaluated by the expression evaluator
- `StringInterpolationExpr` in tool bodies uses argument scope
- No external HTTP calls, no filesystem access, no database queries

**Error handling:**
- Tool not found → `Err(ToolError.NotFound)`
- Missing required argument → `Err(ToolError.MissingArgument)`
- Body evaluation failure → `Err(ToolError.EvaluationFailed)`

---

## MEMORY / RAG / FLOW IMPACT

**None.**

- No memory mutation (`store`, `memory.recall`)
- No RAG indexing or retrieval
- No flow execution
- If `store` or `memory` syntax appears in a method body, the evaluator returns `Err(AgentError.NotImplemented)` with a clear message: *"Memory operations are not yet implemented. See RFC #006."*

---

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events Emitted:**

```python
@dataclass
class AgentStartEvent(TraceEvent):
    event_type: str = "agent_start"
    agent_name: str
    source_file: str
    timestamp: str  # ISO 8601

@dataclass
class MethodStartEvent(TraceEvent):
    event_type: str = "method_start"
    agent_name: str
    method_name: str
    arguments: dict[str, Any]  # scalar values only, redacted if secret-like

@dataclass
class ToolDispatchEvent(TraceEvent):
    event_type: str = "tool_dispatch"
    agent_name: str
    method_name: str
    tool_name: str
    arguments: dict[str, Any]

@dataclass
class ToolReturnEvent(TraceEvent):
    event_type: str = "tool_return"
    agent_name: str
    method_name: str
    tool_name: str
    result_type: str  # "ok" | "error"
    result_summary: str  # type name or error kind, not full value

@dataclass
class MethodReturnEvent(TraceEvent):
    event_type: str = "method_return"
    agent_name: str
    method_name: str
    result_type: str
    result_summary: str

@dataclass
class AgentEndEvent(TraceEvent):
    event_type: str = "agent_end"
    agent_name: str
    result_type: str
    duration_ms: int
```

**Ordering guarantees:**
- Events are emitted in strict chronological order
- Tool dispatch → Tool return (always paired)
- Method start → Method return (always paired)
- Agent start → ... → Agent end (always paired)

**Intentionally not recorded:**
- Full prompt text for `@` operations (may contain secrets)
- Full tool return values (only type/summary)
- API keys or authentication tokens
- Internal scope state
- Stack traces (use error kind + message instead)

---

## SECURITY AND SECRET HANDLING

**No secrets required.**
- Mock execution requires no API keys
- No environment variable resolution for provider keys
- No `.env` file access

**No network access.**
- No HTTPS calls
- No DNS resolution
- No socket connections

**No filesystem mutation.**
- Only reads the specified `.ax` source file
- Trace output is written to user-specified path only
- No temp files, no log files beyond explicit trace output

**Trace safety.**
- Argument values in traces are scalar only (str, int, bool)
- String values longer than 100 chars are truncated with `...`
- Values matching `*_KEY`, `*_SECRET`, `*_TOKEN`, `password` patterns are redacted to `[REDACTED]`

---

## TESTING STRATEGY

- [ ] Unit tests for expression evaluator (`tests/test_evaluator.py`)
  - Literal evaluation
  - Variable lookup
  - String interpolation
  - Let binding
  - Return expression
  - Basic arithmetic
  - Ok/Error wrapping
- [ ] Unit tests for mock tool registry (`tests/test_tool_registry.py`)
  - Register tool from ToolDecl
  - Dispatch with correct arguments
  - Error on missing tool
  - Error on missing argument
- [ ] Integration test: `axon run examples/hello.ax` returns `"Hello, World!"`
- [ ] Integration test: `axon run examples/hello.ax --trace` produces valid JSONL
- [ ] Trace event tests: all 6 event types emitted in correct order
- [ ] Error path tests: missing tool, bad argument, unknown variable
- [ ] No accidental network calls — mock provider asserts no `requests`/`httpx` imports
- [ ] No API key loading — test runs without any env vars set
- [ ] Docs updated with `axon run` CLI reference

---

## ROLLBACK PLAN

This runtime behavior can be disabled by:

1. Removing or disabling the `axon run` CLI command
2. Keeping `src/axon/evaluator.py`, `src/axon/tool_registry.py`, and `src/axon/trace_emitter.py` but not invoking them
3. Reverting `src/axon/runtime.py` to the placeholder implementation
4. Existing parser, validator, formatter, codegen, snapshot, runtime-plan workflows remain completely unchanged

The rollback is safe because:
- Execution is a new CLI command (`axon run`), not a change to existing commands
- No existing files are modified by the runtime
- Parser and AST are unchanged
- All existing tests continue to pass

---

## ACCEPTANCE CRITERIA

- [x] `axon run examples/hello.ax` executes and returns `"Hello, World!"`
- [x] `axon run examples/hello.ax --arg q="Universe"` returns `"Hello, Universe!"`
- [x] `axon run examples/hello.ax --trace trace.jsonl` produces a valid JSONL file with all 6 trace event types
- [x] Execution completes without API keys, network access, or provider SDK imports
- [x] Mock tool registry evaluates tool body expressions correctly
- [x] Expression evaluator handles literals, variables, interpolation, let, return, call, Ok/Error, and basic operators
- [x] Existing non-runtime commands (`build`, `validate`, `format`, `snapshot`, `runtime-plan`) remain non-executing
- [x] All existing tests pass
- [x] New tests cover evaluator, tool registry, trace emission, and end-to-end execution
- [x] `docs/RUNTIME_BOUNDARY.md` updated to reflect the new execution boundary
- [x] `docs/runtime-rfcs/README.md` updated to list RFC #004

---

## OPEN QUESTIONS

- Should `if/else` be added in this RFC or deferred? *(Recommendation: defer to RFC #005 — keep this RFC minimal)*
- Should `@plan()` and other `@` operations return static mocks or raise `NotImplementedError`? *(Recommendation: static mocks with deterministic responses so the demo works end-to-end)*
- Should the trace emitter write to stdout by default or require `--trace`? *(Recommendation: require `--trace`, stdout gets plain output only)*
- Should `act` calls support `?` error propagation in this RFC? *(Recommendation: yes, minimal `?` as syntactic sugar for unwrap-or-return-error)*
- Which future RFC should handle real provider calls? *(Recommendation: update RFC #003 to integrate with this evaluator)*
- Which future RFC should handle real tool dispatch? *(Recommendation: RFC #005 — Tool Dispatch Runtime)*
- Which future RFC should handle memory? *(Recommendation: RFC #006 — Memory Runtime)*
- Which future RFC should handle control flow? *(Recommendation: RFC #005 or RFC #007)*

---

## IMPLEMENTATION PLAN

### Phase A — Expression Evaluator (2-3 days)

1. `src/axon/evaluator.py`
   - `evaluate(expr: Expr, scope: Scope) -> Result[Any, EvalError]`
   - Handle all permitted expression types from AXON SYNTAX EXECUTED section
   - Scope as a simple chain of dicts for variable lookup

2. `src/axon/evaluator_errors.py`
   - `EvalError` dataclass with `kind` (UnknownVariable, TypeMismatch, etc.) and `message`

3. `tests/test_evaluator.py`
   - Unit tests for each expression type

### Phase B — Mock Tool Registry (1-2 days)

4. `src/axon/tool_registry.py`
   - `MockToolRegistry` class
   - `register(tool: ToolDecl)`
   - `dispatch(name: str, args: dict) -> Result[Any, ToolError]`
   - Evaluate tool body with argument scope

5. `src/axon/tool_registry_errors.py`
   - `ToolError` dataclass

6. `tests/test_tool_registry.py`

### Phase C — Trace Emitter (1-2 days)

7. `src/axon/trace_emitter.py`
   - `TraceEmitter` class
   - Methods for each event type
   - JSONL serialization
   - File writing or stdout

8. `tests/test_trace_emitter.py`

### Phase D — Runtime Integration (2-3 days)

9. Update `src/axon/runtime.py`
   - Replace placeholder `execute()` with real flow:
     1. Parse source
     2. Find agent and `run()` method
     3. Build scope from CLI args
     4. Evaluate method body
     5. Handle `act` → tool registry
     6. Emit trace events
     7. Return result

10. Update `src/axon/cli.py`
    - `run_file()` passes trace path and args to `RuntimeConfig`
    - Add `--arg`, `--trace` flags

### Phase E — End-to-End Demo (1 day)

11. Verify `axon run examples/hello.ax` works
12. Verify trace output is correct
13. Add integration test
14. Update documentation

### Total estimated time: 7-11 days

---

## REFERENCES

- AXON vision / Phase 1 deliverable: `axon_language.md`
- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Runtime RFC #001: `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`
- Runtime RFC #002: `docs/runtime-rfcs/002-expression-type-checking.md`
- Runtime RFC #003: `docs/runtime-rfcs/003-provider-abstraction-runtime.md`
- Expression AST: `src/axon/expression_ast.py`
- Expression parser: `src/axon/expression_parser.py`
- Current runtime stub: `src/axon/runtime.py`
- CLI run command: `src/axon/cli.py::run_file()`
- Example source: `examples/hello.ax`
- AEL trace format: `docs/TRACE_FORMAT.md` (if exists) or define in trace emitter
