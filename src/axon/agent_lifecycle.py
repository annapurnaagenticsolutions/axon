"""Agent lifecycle manager for AXON runtime.

Provides spawn, pause, resume, terminate, and status tracking for
in-process agent instances.  Each agent runs in its own background
thread with an independent RuntimeExecutor, MemoryStore, and trace
emitter.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Optional

from result import Result, Err, Ok

from axon.runtime import RuntimeConfig, RuntimeExecutor
from axon.streaming_collector import StreamingCollector
from axon.trace_emitter import TraceEmitter


class AgentStatus(Enum):
    """Lifecycle states for an AXON agent instance."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class AgentInstance:
    """A running (or paused/terminated) agent instance."""

    id: str
    name: str
    source_path: Path
    status: AgentStatus = AgentStatus.IDLE
    config: Optional[RuntimeConfig] = None
    executor: Optional[RuntimeExecutor] = None
    trace_emitter: Optional[TraceEmitter] = None
    last_output: str = ""
    last_error: str = ""
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def _touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_path": str(self.source_path),
            "status": self.status.value,
            "last_output": self.last_output,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }


class AgentLifecycleError(Exception):
    """Raised when a lifecycle operation is invalid."""


class AgentLifecycleManager:
    """Manages a registry of agent instances with lifecycle transitions."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentInstance] = {}
        self._by_name: dict[str, str] = {}  # name -> id
        self._lock = threading.Lock()
        self._work_queues: dict[str, Queue] = {}
        self._threads: dict[str, threading.Thread] = {}

    def spawn(
        self,
        source_path: Path,
        name: str,
        args: dict[str, Any] | None = None,
        mock: bool = True,
        provider_name: str | None = None,
        trace_output: Path | None = None,
        memory_path: Path | None = None,
        checkpoint: bool = False,
        stream: bool = False,
    ) -> Result[str, str]:
        """Spawn a new agent instance and return its ID."""
        with self._lock:
            if name in self._by_name:
                existing_id = self._by_name[name]
                existing = self._agents.get(existing_id)
                if existing and existing.status != AgentStatus.TERMINATED:
                    return Err(f"Agent '{name}' already exists (id={existing_id})")

            instance_id = str(uuid.uuid4())[:8]
            config = RuntimeConfig(
                source_path=source_path,
                args=args or {},
                mock=mock,
                provider_name=provider_name,
                trace_output=trace_output,
                memory_path=memory_path,
                checkpoint=checkpoint,
                stream=stream,
            )
            executor = RuntimeExecutor(config)
            emitter = TraceEmitter()
            emitter.agent_start(agent_name=name, source_file=str(source_path))

            instance = AgentInstance(
                id=instance_id,
                name=name,
                source_path=source_path,
                status=AgentStatus.IDLE,
                config=config,
                executor=executor,
                trace_emitter=emitter,
            )
            instance._touch()
            self._agents[instance_id] = instance
            self._by_name[name] = instance_id

            # Create work queue and start background thread
            queue: Queue = Queue()
            self._work_queues[instance_id] = queue
            thread = threading.Thread(
                target=self._agent_loop,
                args=(instance_id, queue),
                daemon=True,
                name=f"axon-agent-{name}",
            )
            self._threads[instance_id] = thread
            thread.start()

            # Immediately enqueue a run() job
            queue.put({"type": "run"})
            instance.status = AgentStatus.RUNNING
            instance._touch()

            return Ok(instance_id)

    def pause(self, name: str) -> Result[None, str]:
        """Pause a running agent."""
        with self._lock:
            instance = self._get_instance(name)
            if instance is None:
                return Err(f"Agent '{name}' not found")
            if instance.status not in (AgentStatus.RUNNING, AgentStatus.IDLE):
                return Err(f"Cannot pause agent '{name}' in state {instance.status.value}")
            instance.status = AgentStatus.PAUSED
            instance._touch()
            if instance.trace_emitter:
                instance.trace_emitter.agent_pause(agent_name=instance.name)
            return Ok(None)

    def resume(self, name: str) -> Result[None, str]:
        """Resume a paused agent."""
        with self._lock:
            instance = self._get_instance(name)
            if instance is None:
                return Err(f"Agent '{name}' not found")
            if instance.status != AgentStatus.PAUSED:
                return Err(f"Cannot resume agent '{name}' in state {instance.status.value}")
            instance.status = AgentStatus.RUNNING
            instance._touch()
            if instance.trace_emitter:
                instance.trace_emitter.agent_resume(agent_name=instance.name)
            # Signal the queue to continue
            queue = self._work_queues.get(instance.id)
            if queue is not None:
                queue.put({"type": "resume"})
            return Ok(None)

    def terminate(self, name: str, reason: str = "user_request") -> Result[None, str]:
        """Terminate an agent."""
        with self._lock:
            instance = self._get_instance(name)
            if instance is None:
                return Err(f"Agent '{name}' not found")
            if instance.status == AgentStatus.TERMINATED:
                return Ok(None)  # idempotent
            instance.status = AgentStatus.TERMINATED
            instance._touch()
            if instance.trace_emitter:
                instance.trace_emitter.agent_terminate(
                    agent_name=instance.name, reason=reason
                )
            # Signal the queue to exit
            queue = self._work_queues.get(instance.id)
            if queue is not None:
                queue.put({"type": "terminate"})
            return Ok(None)

    def status(self, name: str) -> Result[AgentInstance, str]:
        """Get the current status of an agent."""
        with self._lock:
            instance = self._get_instance(name)
            if instance is None:
                return Err(f"Agent '{name}' not found")
            return Ok(instance)

    def list_agents(self) -> list[AgentInstance]:
        """Return all non-terminated agent instances."""
        with self._lock:
            return [
                inst for inst in self._agents.values()
                if inst.status != AgentStatus.TERMINATED
            ]

    def shutdown_all(self, reason: str = "shutdown") -> None:
        """Gracefully terminate all running agents."""
        with self._lock:
            names = [
                inst.name
                for inst in self._agents.values()
                if inst.status not in (AgentStatus.TERMINATED,)
            ]
        for name in names:
            self.terminate(name, reason=reason)

    def _get_instance(self, name: str) -> Optional[AgentInstance]:
        instance_id = self._by_name.get(name)
        if instance_id is None:
            return None
        return self._agents.get(instance_id)

    def _agent_loop(self, instance_id: str, queue: Queue) -> None:
        """Background thread for an agent instance."""
        instance = self._agents.get(instance_id)
        if instance is None or instance.executor is None:
            return

        while True:
            try:
                # Poll work queue with timeout so we can check status
                item = queue.get(timeout=0.5)
            except Empty:
                # Check if we should continue running
                with self._lock:
                    inst = self._agents.get(instance_id)
                    if inst is None or inst.status == AgentStatus.TERMINATED:
                        break
                    if inst.status == AgentStatus.PAUSED:
                        continue  # skip execution while paused
                continue

            if item["type"] == "terminate":
                break

            if item["type"] == "resume":
                continue  # status already changed, just loop

            if item["type"] == "run":
                executor = instance.executor
                if executor is None:
                    continue
                try:
                    result = executor.execute()
                    with self._lock:
                        inst = self._agents.get(instance_id)
                        if inst is not None:
                            if isinstance(result, Err):
                                inst.last_error = str(result.err_value)
                                inst.status = AgentStatus.ERROR
                            else:
                                inst.last_output = str(result.ok_value)
                                inst.status = AgentStatus.IDLE
                            inst._touch()
                except Exception as exc:
                    with self._lock:
                        inst = self._agents.get(instance_id)
                        if inst is not None:
                            inst.last_error = str(exc)
                            inst.status = AgentStatus.ERROR
                            inst._touch()

            # After run completes, if still idle and not paused/terminated,
            # stay idle and wait for more work (could be message-bus driven later)

        # Cleanup
        with self._lock:
            inst = self._agents.get(instance_id)
            if inst is not None:
                inst.status = AgentStatus.TERMINATED
                inst._touch()
