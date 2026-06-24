# AXON Runtime RFC #008 — Trace Replay

**Status:** Accepted
**Created:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC documents the trace replay system that enables deterministic replay of AXON agent executions from captured trace logs.

---

## SUMMARY

The trace replay system allows AXON executions to be replayed from captured trace logs. It supports deterministic replay of tool dispatches, model calls, and agent delegations, enabling debugging and regression testing.

## PROBLEM / MOTIVATION

AXON executions need to be reproducible for debugging and testing. The trace replay system must:

1. Capture all runtime events in trace logs
2. Replay tool dispatches from captured results
3. Replay model calls from captured responses
4. Replay agent delegations from captured results
5. Emit replay-specific trace events

## CURRENT BOUNDARY CHECK

This RFC enables trace replay during runtime, which is a Phase 2 capability.

- [x] Trace replay is behind the `axon run --replay <trace.jsonl>` CLI command
- [x] Replay uses captured trace logs (no live provider calls)
- [x] No secrets are exposed during replay
- [x] Replay events are emitted as trace events

## IMPLEMENTATION OVERVIEW

The trace replay system is implemented in `src/axon/trace_replayer.py` with the following components:

### TraceReplayer

```python
class TraceReplayer:
    """Replayer for AXON trace logs."""
    
    def __init__(self, trace_path: Path)
    
    def replay_tool_dispatch(self, name: str, kwargs: dict) -> Result[Any, str]
    def replay_model_call(self, prompt: str) -> Result[Any, str]
    def replay_delegate(self, agent_name: str, kwargs: dict) -> Result[Any, str]
```

### Trace Matching

- Tool dispatches matched by tool name and argument hash
- Model calls matched by prompt hash
- Delegations matched by agent name and argument hash

### Replay Events

```python
class ReplayStartEvent(TraceEvent):
    event_type: str = "replay_start"
    trace_file: str
    source_file: str

class ReplayEndEvent(TraceEvent):
    event_type: str = "replay_end"
    result_type: str
    result_summary: str
```

## AXON SYNTAX EXECUTED

```bash
# Capture a trace
axon run agent.ax --trace-output trace.jsonl

# Replay from trace
axon run agent.ax --replay trace.jsonl
```

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events:**

- `replay_start` - Replay session started
- `replay_end` - Replay session ended
- `tool_dispatch` - Replayed tool dispatch
- `model_call` - Replayed model call
- `delegate_call` - Replayed agent delegation

## TESTING STRATEGY

- [x] Unit tests for TraceReplayer
- [x] Integration tests with runtime executor
- [x] Round-trip tests (capture + replay)
- [x] All tests pass (192 runtime tests)

## REFERENCES

- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Implementation: `src/axon/trace_replayer.py`
- Tests: `tests/test_trace_replay.py`
