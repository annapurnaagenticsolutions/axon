"""Load testing harness for AXON runtime.

Measures agent spawn rate, concurrent execution throughput,
and recovery behavior under pressure.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from result import Ok

from axon.agent_lifecycle import AgentLifecycleManager
from axon.agent_supervisor import AgentSupervisor, ChildSpec, RestartStrategy


@dataclass
class LoadTestResult:
    """Results from a load test run."""

    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    throughput_per_second: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "throughput_per_second": round(self.throughput_per_second, 2),
            "errors": self.errors[:10],  # Cap error detail
        }


class LoadTestHarness:
    """Configurable load testing for AXON agent runtime."""

    def __init__(self, source_path: Path, mock: bool = True) -> None:
        self.source_path = source_path
        self.mock = mock
        self.lifecycle = AgentLifecycleManager()

    def run_spawn_test(self, count: int, concurrency: int) -> LoadTestResult:
        """Spawn *count* agents with *concurrency* parallel threads.

        Returns timing and success metrics.
        """
        latencies: list[float] = []
        errors: list[str] = []
        lock = threading.Lock()
        start_time = time.time()
        semaphore = threading.Semaphore(concurrency)

        def worker(index: int) -> None:
            with semaphore:
                t0 = time.time()
                name = f"load-bot-{index}"
                result = self.lifecycle.spawn(
                    source_path=self.source_path,
                    name=name,
                    args={"q": "hello"},
                    mock=self.mock,
                )
                latency = (time.time() - t0) * 1000
                with lock:
                    latencies.append(latency)
                    if isinstance(result, Ok):
                        pass  # success
                    else:
                        errors.append(f"spawn {name}: {result.err_value}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_time = time.time() - start_time
        return self._build_result(count, latencies, errors, total_time)

    def run_execution_test(self, count: int, concurrency: int) -> LoadTestResult:
        """Execute *count* agents sequentially via RuntimeExecutor.

        Each agent runs its ``run()`` method once.
        """
        from axon.runtime import RuntimeConfig, RuntimeExecutor

        latencies: list[float] = []
        errors: list[str] = []
        lock = threading.Lock()
        start_time = time.time()
        semaphore = threading.Semaphore(concurrency)

        def worker(index: int) -> None:
            with semaphore:
                t0 = time.time()
                config = RuntimeConfig(
                    source_path=self.source_path,
                    args={"q": "hello"},
                    mock=self.mock,
                )
                executor = RuntimeExecutor(config)
                try:
                    result = executor.execute()
                    latency = (time.time() - t0) * 1000
                    with lock:
                        latencies.append(latency)
                        if not result.is_ok:
                            errors.append(f"execution {index}: {result.err_value}")
                except Exception as exc:
                    latency = (time.time() - t0) * 1000
                    with lock:
                        latencies.append(latency)
                        errors.append(f"execution {index}: {exc}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_time = time.time() - start_time
        return self._build_result(count, latencies, errors, total_time)

    def run_supervisor_test(self, children: int, chaos_interval: float = 0.0) -> LoadTestResult:
        """Start a supervisor with *children* agents, optionally injecting chaos.

        *chaos_interval* seconds between random agent kills (0 = no chaos).
        """
        latencies: list[float] = []
        errors: list[str] = []
        start_time = time.time()

        supervisor = AgentSupervisor(
            name="load-supervisor",
            strategy=RestartStrategy.ONE_FOR_ONE,
            max_restarts=children * 2,
            max_seconds=60,
            lifecycle_manager=self.lifecycle,
        )
        for i in range(children):
            supervisor.add_child(ChildSpec(source_path=self.source_path, name=f"child-{i}", args={"q": "hello"}))

        t0 = time.time()
        start_result = supervisor.start()
        latencies.append((time.time() - t0) * 1000)
        if isinstance(start_result, Ok):
            pass
        else:
            errors.append(f"supervisor start: {start_result.err_value}")

        # Optional chaos injection
        if chaos_interval > 0 and children > 0:
            for _ in range(min(children, 5)):
                time.sleep(chaos_interval)
                import random
                victim = f"child-{random.randrange(children)}"
                self.lifecycle.terminate(victim, reason="chaos")

        # Let supervisor recover briefly
        time.sleep(3.0)

        # Count running children
        running = 0
        for i in range(children):
            status = self.lifecycle.status(f"child-{i}")
            if isinstance(status, Ok) and status.ok_value.status.value in ("running", "idle"):
                running += 1

        supervisor.stop()
        total_time = time.time() - start_time

        result = self._build_result(children, latencies, errors, total_time)
        result.successful = running
        result.failed = children - running
        return result

    def cleanup(self) -> None:
        """Terminate all agents created during the test."""
        for inst in list(self.lifecycle.list_agents()):
            self.lifecycle.terminate(inst.name, reason="test_cleanup")

    @staticmethod
    def _build_result(
        total: int, latencies: list[float], errors: list[str], total_time: float
    ) -> LoadTestResult:
        if latencies:
            sorted_lat = sorted(latencies)
            avg = sum(latencies) / len(latencies)
            p99_idx = int(len(sorted_lat) * 0.99)
            p99 = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]
        else:
            avg = 0.0
            p99 = 0.0
        successful = total - len(errors)
        throughput = total / total_time if total_time > 0 else 0.0
        return LoadTestResult(
            total_requests=total,
            successful=successful,
            failed=len(errors),
            avg_latency_ms=avg,
            p99_latency_ms=p99,
            throughput_per_second=throughput,
            errors=errors,
        )
