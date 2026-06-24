"""Worker pool for AXON concurrency runtime.

Provides round-robin and least-loaded dispatch strategies
for managing a pool of identical workers.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Callable

from result import Ok, Err


@dataclass
class WorkerPool:
    """A pool of workers with configurable dispatch strategy."""

    size: int
    target: Any  # Agent name or callable
    strategy: str = "round_robin"  # round_robin, least_loaded
    _workers: list[Any] = field(default_factory=list)
    _index: int = field(default=0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _loads: dict[int, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._workers = list(range(self.size))
        self._loads = {i: 0 for i in range(self.size)}

    def dispatch(
        self,
        args: dict[str, Any],
        executor: Callable[[Any, dict[str, Any]], Any],
    ) -> Future:
        """Dispatch work to a worker and return a Future."""
        fut: Future = Future()

        with self._lock:
            if self.strategy == "round_robin":
                worker_id = self._workers[self._index % self.size]
                self._index += 1
            elif self.strategy == "least_loaded":
                worker_id = min(self._workers, key=lambda w: self._loads[w])
            else:
                worker_id = self._workers[0]
            self._loads[worker_id] += 1

        def _run() -> None:
            try:
                result = executor(worker_id, args)
                self._loads[worker_id] -= 1
                if isinstance(result, Ok):
                    fut.set_result(result.ok_value)
                elif isinstance(result, Err):
                    fut.set_exception(RuntimeError(str(result.err_value)))
                else:
                    fut.set_result(result)
            except Exception as exc:
                self._loads[worker_id] = max(0, self._loads.get(worker_id, 1) - 1)
                fut.set_exception(exc)

        threading.Thread(target=_run, daemon=True).start()
        return fut

    def stats(self) -> dict[str, Any]:
        """Return pool statistics."""
        with self._lock:
            return {
                "size": self.size,
                "strategy": self.strategy,
                "loads": dict(self._loads),
                "total_dispatched": self._index if self.strategy == "round_robin" else sum(self._loads.values()),
            }
