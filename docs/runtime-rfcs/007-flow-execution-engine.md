# AXON Runtime RFC #007 — Flow Execution Engine

**Status:** Accepted
**Created:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC documents the flow execution engine that enables AXON flow declarations to be executed as directed acyclic graphs (DAGs).

---

## SUMMARY

The flow execution engine provides DAG-based execution of AXON flow declarations. It supports stage-based pipelines with data passing between stages, fan-out/fan-in patterns, and error handling.

## PROBLEM / MOTIVATION

AXON flows define multi-stage processing pipelines. During runtime execution, these flows need to be executed as DAGs with:

1. Stage-by-stage execution
2. Data passing between stages
3. Fan-out/fan-in for parallel processing
4. Error propagation
5. Trace emission for flow operations

## CURRENT BOUNDARY CHECK

This RFC enables flow execution during runtime, which is a Phase 2 capability.

- [x] Flow execution is behind the `axon run --flow <name>` CLI command
- [x] Flow execution uses mock providers by default
- [x] No arbitrary code execution (only AXON expressions)
- [x] Trace events are emitted for all flow operations

## IMPLEMENTATION OVERVIEW

The flow execution engine is implemented in `src/axon/flow_executor.py` with the following components:

### Flow Executor

```python
class FlowExecutor:
    """Executor for AXON flow declarations."""
    
    def execute(
        self,
        flow: FlowDecl,
        inputs: dict[str, Any],
        registry: ToolRegistry,
        agent_registry: dict[str, AgentDecl],
        emitter: TraceEmitter,
        memory_store: MemoryStore | None = None,
    ) -> Result[Any, str]
```

### Stage Execution

- Sequential execution by default
- Fan-out for parallel stages
- Fan-in for aggregation
- Error propagation via Result<T, E>

### Data Passing

- Stage outputs are passed as inputs to downstream stages
- Type checking at stage boundaries
- Support for intermediate results

## AXON SYNTAX EXECUTED

```axon
flow Pipeline(input: Str) -> Str {
    stage Process(input: Str) -> Str
    stage Analyze(data: Str) -> Str
    stage Format(result: Str) -> Str

    Process -> Analyze
    Analyze -> Format
}
```

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events:**

```python
class FlowStartEvent(TraceEvent):
    event_type: str = "flow_start"
    flow_name: str
    inputs: dict[str, Any]

class FlowStageEvent(TraceEvent):
    event_type: str = "flow_stage"
    flow_name: str
    stage_name: str
    inputs: dict[str, Any]

class FlowEndEvent(TraceEvent):
    event_type: str = "flow_end"
    flow_name: str
    result_type: str
    result_summary: str
```

## TESTING STRATEGY

- [x] Unit tests for FlowExecutor
- [x] Integration tests with runtime executor
- [x] Error handling tests
- [x] All tests pass (192 runtime tests)

## REFERENCES

- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Implementation: `src/axon/flow_executor.py`
- Tests: `tests/test_flow_execution.py`
