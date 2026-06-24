# RFC #021 — Load Testing & Chaos Engineering

**Status:** Draft  
**Phase:** 10 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Provide a load testing harness and chaos engineering suite to verify AXON runtime resilience under pressure. The harness measures agent spawn rate, concurrent execution throughput, and recovery from failures. The chaos suite injects agent kills, provider errors, and memory pressure to validate supervision and checkpointing.

## Motivation

Current benchmarks only cover parsing and type-checking. Production needs:
- How many agents can spawn concurrently before the supervisor collapses?
- What happens when a provider returns errors mid-stream?
- Does checkpointing work under memory pressure?
- Can the API server handle sustained request load?

## Goals

- `LoadTestHarness` class for configurable concurrent agent spawning
- `ChaosInjector` class for failure injection (agent kill, provider error, delay)
- Benchmark metrics: spawn latency, execution throughput, error rate, recovery time
- `pytest` integration with configurable load parameters
- No live network calls (mock provider only)

## Non-Goals

- Distributed load testing (multi-node)
- Long-running soak tests (>1 hour)
- Network-level chaos (packet loss, partition)
- Production traffic replay

## Design

### LoadTestHarness

```python
class LoadTestHarness:
    def __init__(self, source_path: Path, mock: bool = True) -> None: ...
    def run_spawn_test(self, count: int, concurrency: int) -> LoadTestResult: ...
    def run_execution_test(self, count: int, concurrency: int) -> LoadTestResult: ...
    def run_supervisor_test(self, children: int, restart_rate: float) -> LoadTestResult: ...
```

### ChaosInjector

```python
class ChaosInjector:
    def __init__(self, lifecycle: AgentLifecycleManager) -> None: ...
    def kill_random_agent(self) -> None: ...
    def inject_provider_error(self, agent_name: str) -> None: ...
    def inject_delay(self, ms: int) -> None: ...
```

### LoadTestResult

```python
@dataclass
class LoadTestResult:
    total_requests: int
    successful: int
    failed: int
    avg_latency_ms: float
    p99_latency_ms: float
    throughput_per_second: float
    errors: list[str]
```

## Testing Strategy

- `test_spawn_10_concurrent_agents` — verify spawn rate
- `test_spawn_50_sequential_agents` — verify memory stability
- `test_supervisor_recovery_under_chaos` — kill agents, verify restart
- `test_api_server_under_load` — HTTP load test with TestClient
- `test_checkpoint_under_memory_pressure` — large memory state, verify checkpoint

## Acceptance Criteria

- 10 concurrent agents spawn in < 5 seconds
- Supervisor recovers 90% of killed agents within 10 seconds
- API server handles 100 requests/second with < 100ms p99 latency
- No memory leaks across 50 sequential spawns
