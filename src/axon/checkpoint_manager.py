"""Checkpoint and restore manager for AXON agent runtime.

Captures full agent state snapshots (status, output, error, config, memory)
and restores agents from previously saved checkpoints.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from result import Result, Err, Ok

from axon.agent_lifecycle import AgentLifecycleManager, AgentInstance
from axon.memory_store import MemoryStore
from axon.trace_emitter import TraceEmitter


@dataclass
class AgentStateSnapshot:
    """Full runtime state of an agent instance."""

    id: str
    name: str
    source_path: str
    status: str
    last_output: str
    last_error: str
    started_at: float
    updated_at: float
    config: dict[str, Any]
    memory: dict[str, Any] | None = None


class CheckpointManager:
    """Save and restore agent state snapshots."""

    def __init__(
        self,
        lifecycle: AgentLifecycleManager,
        emitter: TraceEmitter | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._emitter = emitter or TraceEmitter()

    def checkpoint(
        self,
        name: str,
        output_path: Path | None = None,
    ) -> Result[Path, str]:
        """Save a snapshot of the named agent to disk.

        Returns the path written on success.
        """
        status_result = self._lifecycle.status(name)
        if isinstance(status_result, Err):
            return Err(status_result.err_value)

        inst = status_result.ok_value
        snapshot = self._build_snapshot(inst)

        if output_path is None:
            checkpoint_dir = Path.cwd() / ".axon_checkpoints"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            output_path = checkpoint_dir / f"{name}_{int(time.time())}.json"

        try:
            output_path.write_text(
                json.dumps(asdict(snapshot), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            return Err(f"Failed to write checkpoint: {exc}")

        memory_keys = sum(len(v) for v in (snapshot.memory or {}).values() if isinstance(v, dict))
        self._emitter.checkpoint_save(
            agent_name=name,
            path=str(output_path),
            sections=len(snapshot.memory or {}),
            keys=memory_keys,
        )
        return Ok(output_path)

    def restore(
        self,
        name: str,
        snapshot_path: Path,
        mock: bool = True,
        provider_name: str | None = None,
    ) -> Result[str, str]:
        """Restore an agent from a snapshot file.

        Returns the new agent ID on success.
        """
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return Err(f"Failed to read snapshot: {exc}")

        source_path = Path(data["source_path"])
        if not source_path.exists():
            # Try relative to snapshot dir
            alt = snapshot_path.parent / source_path.name
            if alt.exists():
                source_path = alt
            else:
                return Err(f"Source file not found: {data['source_path']}")

        config = data.get("config", {})
        args = config.get("args", {})

        # Spawn new instance
        result = self._lifecycle.spawn(
            source_path=source_path,
            name=name,
            args=args,
            mock=mock,
            provider_name=provider_name or config.get("provider_name"),
            trace_output=Path(config["trace_output"]) if config.get("trace_output") else None,
            memory_path=Path(config["memory_path"]) if config.get("memory_path") else None,
            checkpoint=config.get("checkpoint", False),
        )
        if isinstance(result, Err):
            return Err(result.err_value)

        new_id = result.ok_value

        # Restore memory if present
        memory_data = data.get("memory")
        if memory_data is not None:
            inst_result = self._lifecycle.status(name)
            if isinstance(inst_result, Ok):
                inst = inst_result.ok_value
                if inst.executor is not None and inst.executor.config.memory_path is not None:
                    try:
                        memory_store = MemoryStore()
                        memory_store.load(memory_data)
                        memory_store.save_to_file(inst.executor.config.memory_path)
                    except (OSError, ValueError) as exc:
                        return Err(f"Agent spawned but memory restore failed: {exc}")

        self._emitter.checkpoint_restore(
            agent_name=name,
            path=str(snapshot_path),
            new_id=new_id,
        )
        return Ok(new_id)

    def list_checkpoints(self, checkpoint_dir: Path | None = None) -> list[Path]:
        """List checkpoint files in the given directory."""
        if checkpoint_dir is None:
            checkpoint_dir = Path.cwd() / ".axon_checkpoints"
        if not checkpoint_dir.exists():
            return []
        return sorted(
            [p for p in checkpoint_dir.iterdir() if p.suffix == ".json"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def _build_snapshot(self, inst: AgentInstance) -> AgentStateSnapshot:
        config: dict[str, Any] = {}
        if inst.config is not None:
            config = {
                "args": inst.config.args,
                "mock": inst.config.mock,
                "provider_name": inst.config.provider_name,
                "trace_output": str(inst.config.trace_output) if inst.config.trace_output else None,
                "memory_path": str(inst.config.memory_path) if inst.config.memory_path else None,
                "checkpoint": inst.config.checkpoint,
                "flow_name": inst.config.flow_name,
                "agent_name": inst.config.agent_name,
            }

        memory: dict[str, Any] | None = None
        if inst.executor is not None and inst.executor.config.memory_path is not None:
            mem_path = inst.executor.config.memory_path
            if mem_path.exists():
                try:
                    store = MemoryStore()
                    store.load_from_file(mem_path)
                    memory = store.snapshot()
                except (OSError, ValueError):
                    pass

        return AgentStateSnapshot(
            id=inst.id,
            name=inst.name,
            source_path=str(inst.source_path),
            status=inst.status.value,
            last_output=inst.last_output,
            last_error=inst.last_error,
            started_at=inst.started_at,
            updated_at=inst.updated_at,
            config=config,
            memory=memory,
        )
