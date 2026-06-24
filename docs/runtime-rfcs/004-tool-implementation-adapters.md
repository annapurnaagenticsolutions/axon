# AXON Runtime RFC #004 — Tool Implementation Adapters

**Status:** Accepted
**Created:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC documents the tool implementation adapter system that enables AXON agents to dispatch tool calls during runtime execution.

---

## SUMMARY

The tool implementation adapter system provides a registry-based mechanism for mapping AXON `act` expressions to concrete tool implementations. It supports mock tools for testing, built-in tools, and user-defined tool adapters.

## PROBLEM / MOTIVATION

AXON agents use `act ToolName(args)` to invoke tools. During runtime execution, these expressions need to be dispatched to actual implementations. The system must:

1. Register tools from parsed AXON declarations
2. Support built-in tools (e.g., `http.get`, `str.split`)
3. Support user-defined tool adapters
4. Provide mock tools for testing
5. Emit trace events for tool dispatches
6. Handle errors via Result<T, E>

## CURRENT BOUNDARY CHECK

This RFC enables tool dispatch during runtime execution, which is a Phase 2 capability.

- [x] Tool dispatch is behind the `axon run` CLI command
- [x] Mock tools are available for testing
- [x] No secrets are exposed during tool dispatch
- [x] Trace events are emitted for all tool calls

## IMPLEMENTATION OVERVIEW

The tool adapter system is implemented in `src/axon/tool_registry.py` with the following components:

### ToolRegistry

```python
class ToolRegistry:
    """Registry for tool implementations."""
    
    def register(self, name: str, implementation: ToolImplementation) -> None
    def dispatch(self, name: str, kwargs: dict[str, Any]) -> Result[Any, ToolError]
    def register_all(self, declarations: list) -> None
```

### MockToolRegistry

```python
class MockToolRegistry(ToolRegistry):
    """Mock registry for testing with configurable responses."""
    
    def set_response(self, name: str, response: Any) -> None
    def set_error(self, name: str, error: ToolError) -> None
```

### Built-in Tools

- `http.get(url: Str) -> Result<Str, HttpError>`
- `http.post(url: Str, body: Str) -> Result<Str, HttpError>`
- `str.split(s: Str, delimiter: Str) -> List<Str>`
- `str.join(items: List<Str>, delimiter: Str) -> Str`
- `math.add(a: Int, b: Int) -> Int`
- `math.mul(a: Int, b: Int) -> Int`

### Error Types

```python
class ToolErrorKind(Enum):
    NOT_FOUND = "not_found"
    INVALID_ARGUMENT = "invalid_argument"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"

class ToolError:
    kind: ToolErrorKind
    message: str
```

## AXON SYNTAX EXECUTED

```axon
tool Search(query: Str) -> Result<Str, HttpError> {
    http.get("https://api.example.com/search?q={query}")
}

agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [Search]

    fn run(query: Str) -> Result<Str, Error> {
        let result = act Search(query: query)?
        Ok(result)
    }
}
```

The `act Search(query: query)` expression is dispatched to the registered tool implementation.

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events:**

```python
class ToolDispatchEvent(TraceEvent):
    event_type: str = "tool_dispatch"
    method_name: str
    tool_name: str
    arguments: dict[str, Any]

class ToolReturnEvent(TraceEvent):
    event_type: str = "tool_return"
    method_name: str
    tool_name: str
    result_type: str  # "ok" | "error"
    result_summary: str
```

## TESTING STRATEGY

- [x] Unit tests for ToolRegistry
- [x] Unit tests for MockToolRegistry
- [x] Integration tests with runtime executor
- [x] Error handling tests
- [x] All tests pass (192 runtime tests)

## REFERENCES

- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Implementation: `src/axon/tool_registry.py`
- Tests: `tests/test_tool_registry.py`
