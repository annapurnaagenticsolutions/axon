# RFC #014 — Persistence: Checkpoint & Restore

**Status:** Draft  
**Phase:** 3 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Extend AXON's runtime with durable agent checkpointing and restore. A checkpoint captures the full runtime state of a managed agent (status, last output/error, configuration, and memory). Restore re-creates an agent from a checkpoint, optionally resuming execution. This enables fault-tolerant long-running agents, experiment reproducibility, and graceful recovery from process restarts.

## Motivation

Currently `MemoryStore` supports basic JSON save/load, but there is no unified mechanism to:
- Save a snapshot of a running agent's complete state
- Restore an agent to a previously saved state
- Capture checkpoint trace events for auditability

Phase 3 closes this gap with a `CheckpointManager` that works with `AgentLifecycleManager` and a CLI surface for explicit checkpoint/restore operations.

## Goals

- `AgentStateSnapshot` capturing: id, name, source path, status, last output, last error, config, and memory
- `CheckpointManager.save()` / `.load()` with JSON serialization
- Integration with `AgentLifecycleManager` (snapshot a running agent, restore as new instance)
- CLI: `axon agent checkpoint NAME [--output path]` and `axon agent restore NAME --snapshot path`
- Trace events: `checkpoint_save`, `checkpoint_restore`
- All tests avoid real filesystem races; use `tmp_path` fixtures

## Non-Goals

- Distributed checkpointing (single process only)
- Incremental/differential checkpoints (full snapshots only)
- Automatic checkpointing on intervals (explicit CLI only for this sprint)
- Cross-version snapshot compatibility (snapshots are best-effort)

## Design

### AgentStateSnapshot

```python
@dataclass
class AgentStateSnapshot:
    id: str
    name: str
    source_path: str
    status: str
    last_output: str
    last_error: str
    started_at: float
    updated_at: float
    config: dict[str, Any]
    memory: dict[str, Any] | None
```

### CheckpointManager

```python
class CheckpointManager:
    def __init__(self, lifecycle: AgentLifecycleManager) -> None: ...
    def checkpoint(self, name: str, output_path: Path | None = None) -> Result[Path, str]: ...
    def restore(self, name: str, snapshot_path: Path) -> Result[str, str]: ...
    def list_checkpoints(self, checkpoint_dir: Path) -> list[Path]: ...
```

- `checkpoint`: queries `lifecycle.status()`, extracts memory via `executor.config.memory_path`, writes JSON snapshot
- `restore`: reads snapshot, spawns new agent with same config, optionally loads memory

### Lifecycle Integration

`AgentLifecycleManager` gains:
- `checkpoint(name)` → delegates to a registered `CheckpointManager`
- `restore(name, snapshot_path)` → delegates to `CheckpointManager`

### CLI Surface

```bash
axon agent checkpoint NAME [--output path.json]
axon agent restore NAME --snapshot path.json [--mock] [--provider]
```

### Trace Events

| Event | Fields | Description |
|---|---|---|
| `checkpoint_save` | `agent_name`, `path`, `sections`, `keys` | Snapshot written to disk |
| `checkpoint_restore` | `agent_name`, `path`, `new_id` | Agent restored from snapshot |

## Testing Strategy

- Unit test `CheckpointManager.checkpoint()` produces valid JSON with expected fields
- Unit test `CheckpointManager.restore()` spawns agent and loads memory
- Unit test CLI dispatch for `checkpoint` and `restore` subcommands
- Verify no regressions in existing `agent_lifecycle` tests

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Snapshot bloat from large memory stores | Document size limits; future work: incremental snapshots |
| Restore with stale source path | Error if source file missing; allow relative paths resolved from CWD |
| Memory path not set → snapshot incomplete | Gracefully omit memory section; warn user |

## Future Work

- Automatic periodic checkpointing
- Incremental snapshots
- Compression / encryption of checkpoint files
- Distributed checkpoint store (S3, etc.)
