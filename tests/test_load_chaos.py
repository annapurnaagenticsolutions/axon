"""Load testing and chaos engineering tests for AXON runtime."""

from pathlib import Path

import pytest

from axon.agent_lifecycle import AgentLifecycleManager
from axon.chaos_injector import ChaosInjector
from axon.load_test_harness import LoadTestHarness


@pytest.fixture
def simple_source(tmp_path: Path) -> Path:
    source = tmp_path / "load_bot.ax"
    source.write_text(
        'agent LoadBot {\n'
        '    model: @mock/gpt\n'
        '    tools: []\n'
        '    fn run(q: Str) -> Str { q }\n'
        '}\n',
        encoding="utf-8",
    )
    return source


class TestLoadSpawn:
    def test_spawn_10_concurrent(self, simple_source: Path) -> None:
        harness = LoadTestHarness(simple_source, mock=True)
        try:
            result = harness.run_spawn_test(count=10, concurrency=5)
            assert result.successful == 10, f"Expected 10 successes, got {result.successful}"
            assert result.avg_latency_ms < 5000, f"Spawn too slow: {result.avg_latency_ms:.2f}ms"
            assert result.throughput_per_second > 0
        finally:
            harness.cleanup()

    def test_spawn_50_sequential(self, simple_source: Path) -> None:
        harness = LoadTestHarness(simple_source, mock=True)
        try:
            result = harness.run_spawn_test(count=50, concurrency=1)
            assert result.successful == 50
            assert result.failed == 0
            # No memory leak check: if we get here without OOM, we're fine
        finally:
            harness.cleanup()


class TestLoadExecution:
    def test_execute_10_concurrent(self, simple_source: Path) -> None:
        harness = LoadTestHarness(simple_source, mock=True)
        try:
            result = harness.run_execution_test(count=10, concurrency=5)
            assert result.successful == 10, f"Expected 10 successes, got {result.successful}, errors: {result.errors}"
            assert result.avg_latency_ms < 10000, f"Execution too slow: {result.avg_latency_ms:.2f}ms"
        finally:
            harness.cleanup()


class TestSupervisorResilience:
    def test_supervisor_with_5_children(self, simple_source: Path) -> None:
        harness = LoadTestHarness(simple_source, mock=True)
        try:
            result = harness.run_supervisor_test(children=5, chaos_interval=0)
            assert result.successful >= 3, f"Expected >=3 running, got {result.successful}"
        finally:
            harness.cleanup()

    def test_supervisor_recovery_under_chaos(self, simple_source: Path) -> None:
        harness = LoadTestHarness(simple_source, mock=True)
        try:
            result = harness.run_supervisor_test(children=5, chaos_interval=0.5)
            # After chaos, supervisor should have restarted some agents
            assert result.successful >= 1, f"Expected >=1 recovered, got {result.successful}"
        finally:
            harness.cleanup()


class TestChaosInjector:
    def test_kill_random_agent(self, simple_source: Path) -> None:
        lifecycle = AgentLifecycleManager()
        lifecycle.spawn(simple_source, name="victim", args={"q": "hello"}, mock=True)
        lifecycle.spawn(simple_source, name="survivor", args={"q": "hello"}, mock=True)

        injector = ChaosInjector(lifecycle)
        victim = injector.kill_random_agent()
        assert victim in ("victim", "survivor")

        status = lifecycle.status(victim)
        assert status.is_ok
        assert status.ok_value.status.value == "terminated"

        lifecycle.terminate("victim", reason="cleanup")
        lifecycle.terminate("survivor", reason="cleanup")

    def test_kill_all_agents(self, simple_source: Path) -> None:
        lifecycle = AgentLifecycleManager()
        for i in range(5):
            lifecycle.spawn(simple_source, name=f"bot-{i}", args={"q": "hello"}, mock=True)

        injector = ChaosInjector(lifecycle)
        killed = injector.kill_all_agents()
        assert killed == 5
        assert len(lifecycle.list_agents()) == 0

    def test_inject_delay(self) -> None:
        import time
        injector = ChaosInjector(AgentLifecycleManager())
        t0 = time.time()
        injector.inject_delay(100)
        elapsed = (time.time() - t0) * 1000
        assert 80 <= elapsed <= 300  # Allow scheduling jitter


class TestLoadResult:
    def test_result_success_rate(self) -> None:
        from axon.load_test_harness import LoadTestResult

        result = LoadTestResult(total_requests=100, successful=95, failed=5)
        assert result.success_rate == 0.95

    def test_result_to_dict(self) -> None:
        from axon.load_test_harness import LoadTestResult

        result = LoadTestResult(
            total_requests=10,
            successful=9,
            failed=1,
            avg_latency_ms=12.5,
            p99_latency_ms=45.0,
            throughput_per_second=5.0,
            errors=["one error"],
        )
        d = result.to_dict()
        assert d["total_requests"] == 10
        assert d["success_rate"] == 0.9
        assert d["avg_latency_ms"] == 12.5
        assert d["p99_latency_ms"] == 45.0
        assert d["throughput_per_second"] == 5.0
