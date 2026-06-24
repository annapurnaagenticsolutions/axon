"""Agent supervision tree for AXON runtime.

Provides Erlang/OTP-inspired supervision with restart strategies:
one_for_one, one_for_all, and rest_for_one.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from result import Ok, Err

from axon.agent_lifecycle import AgentLifecycleManager, AgentStatus
from axon.trace_emitter import TraceEmitter


class RestartStrategy(Enum):
    """How the supervisor reacts when a child fails."""

    ONE_FOR_ONE = "one_for_one"
    ONE_FOR_ALL = "one_for_all"
    REST_FOR_ONE = "rest_for_one"


@dataclass
class ChildSpec:
    """Specification for a supervised child agent."""

    source_path: Path
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    mock: bool = True
    provider_name: str | None = None


@dataclass
class RestartIntensity:
    """Restart rate limiter."""

    max_restarts: int = 5
    max_seconds: int = 60
    _window: deque[float] = field(default_factory=deque, repr=False)

    def can_restart(self) -> bool:
        now = time.time()
        cutoff = now - self.max_seconds
        # Remove timestamps outside the window
        while self._window and self._window[0] < cutoff:
            self._window.popleft()
        return len(self._window) < self.max_restarts

    def record_restart(self) -> None:
        self._window.append(time.time())


@dataclass
class SupervisorState:
    """Runtime state of a supervisor instance."""

    name: str
    strategy: RestartStrategy
    intensity: RestartIntensity
    children: list[ChildSpec]
    running: bool = False
    shutdown_reason: str | None = None


class AgentSupervisor:
    """Monitors a group of child agents and restarts them on failure."""

    def __init__(
        self,
        name: str,
        strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE,
        max_restarts: int = 5,
        max_seconds: int = 60,
        poll_interval_ms: int = 2000,
        lifecycle_manager: AgentLifecycleManager | None = None,
    ) -> None:
        self._name = name
        self._strategy = strategy
        self._intensity = RestartIntensity(max_restarts=max_restarts, max_seconds=max_seconds)
        self._poll_interval = poll_interval_ms / 1000.0
        self._children: list[ChildSpec] = []
        self._lifecycle = lifecycle_manager if lifecycle_manager is not None else AgentLifecycleManager()
        self._emitter = TraceEmitter()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def strategy(self) -> RestartStrategy:
        return self._strategy

    @property
    def children(self) -> list[ChildSpec]:
        with self._lock:
            return list(self._children)

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def add_child(self, spec: ChildSpec) -> None:
        """Register a child spec before starting the supervisor."""
        with self._lock:
            self._children.append(spec)

    def start(self):
        """Spawn all children and start the monitor thread."""
        with self._lock:
            if self._running:
                return Ok(None)
            self._running = True
            self._emitter.supervisor_start(
                name=self._name,
                strategy=self._strategy.value,
                child_count=len(self._children),
            )

        for spec in self._children:
            self._start_child(spec)

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name=f"axon-supervisor-{self._name}",
        )
        self._monitor_thread.start()
        return Ok(None)

    def stop(self, reason: str = "user_request") -> None:
        """Stop the supervisor and terminate all children."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        for spec in self._children:
            self._lifecycle.terminate(spec.name, reason=reason)

        self._emitter.supervisor_shutdown(name=self._name, reason=reason)

    def state(self) -> SupervisorState:
        """Return the current supervisor state."""
        with self._lock:
            return SupervisorState(
                name=self._name,
                strategy=self._strategy,
                intensity=self._intensity,
                children=list(self._children),
                running=self._running,
                shutdown_reason=self._shutdown_reason(),
            )

    def _shutdown_reason(self) -> str | None:
        # Used for state snapshot only; actual shutdown tracking is via _running
        return None

    def _start_child(self, spec: ChildSpec) -> None:
        result = self._lifecycle.spawn(
            source_path=spec.source_path,
            name=spec.name,
            args=spec.args,
            mock=spec.mock,
            provider_name=spec.provider_name,
        )
        if isinstance(result, Ok):
            self._emitter.supervisor_child_start(
                name=self._name, child_name=spec.name
            )
        else:
            self._emitter.supervisor_child_restart(
                name=self._name,
                child_name=spec.name,
                reason=f"spawn failed: {result.err_value}",
            )

    def _restart_child(self, spec: ChildSpec) -> None:
        # Terminate first to clean up any stale state
        self._lifecycle.terminate(spec.name, reason="restart")
        self._start_child(spec)
        self._emitter.supervisor_child_restart(
            name=self._name, child_name=spec.name, reason="failure"
        )

    def _restart_all(self) -> None:
        for spec in self._children:
            self._lifecycle.terminate(spec.name, reason="restart_all")
        for spec in self._children:
            self._start_child(spec)

    def _restart_rest(self, failed_index: int) -> None:
        # Terminate failed and all children after it
        for spec in self._children[failed_index:]:
            self._lifecycle.terminate(spec.name, reason="restart_rest")
        # Restart in order
        for spec in self._children[failed_index:]:
            self._start_child(spec)

    def _monitor_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break

            # Check each child
            failed_indices: list[int] = []
            for i, spec in enumerate(self._children):
                status_result = self._lifecycle.status(spec.name)
                if not isinstance(status_result, Ok):
                    continue
                inst = status_result.ok_value
                if inst.status in (AgentStatus.ERROR, AgentStatus.TERMINATED):
                    failed_indices.append(i)

            for idx in failed_indices:
                if not self._intensity.can_restart():
                    # Max intensity exceeded — shut down
                    self.stop(reason="max_restart_intensity_exceeded")
                    return
                self._intensity.record_restart()
                spec = self._children[idx]

                if self._strategy == RestartStrategy.ONE_FOR_ONE:
                    self._restart_child(spec)
                elif self._strategy == RestartStrategy.ONE_FOR_ALL:
                    self._restart_all()
                elif self._strategy == RestartStrategy.REST_FOR_ONE:
                    self._restart_rest(idx)

            time.sleep(self._poll_interval)
