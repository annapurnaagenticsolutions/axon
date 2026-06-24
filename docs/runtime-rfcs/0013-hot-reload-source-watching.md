# RFC #013 — Hot-Reload & Source Watching

**Status:** Draft  
**Phase:** 2C Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Provide file-system watching for AXON source files so that agents (and supervised children) can be automatically reloaded when their `.ax` sources change on disk. This removes the manual `terminate`/`spawn` cycle during development and enables rapid iteration on agent definitions, tools, and flows.

## Motivation

During agent development a typical workflow is:

1. Edit `my_agent.ax`.
2. Re-run `axon run my_agent.ax` or `axon agent terminate my_agent && axon agent spawn my_agent.ax --name my_agent`.

This cycle is tedious and slows iteration. Hot-reload automates it: the runtime watches the source file, detects changes, and re-spawns the agent with the new source transparently.

## Goals

- Poll-based file watching (zero external dependencies).
- Automatic agent reload on source change.
- Integration with `AgentLifecycleManager` (terminate → re-spawn).
- Optional integration with `AgentSupervisor` (watch all supervised children).
- Trace events for reload actions.
- CLI command: `axon watch <source.ax>`.

## Non-Goals

- IDE-level incremental compilation (whole-file re-parse).
- In-place AST patching (full re-spawn only).
- Watching non-`.ax` files (e.g., tool JSON, RAG corpora).
- Network/distributed file watching (local filesystem only).

## Design

### SourceWatcher

A polling-based file watcher using `pathlib.Path.stat().st_mtime`.

```python
class SourceWatcher:
    """Polls files and invokes a callback on change."""

    def __init__(self, poll_interval_ms: int = 1000) -> None: ...
    def add_file(self, path: Path, callback: Callable[[Path], None]) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

- Uses a single background `threading.Thread`.
- Each poll iteration compares current `st_mtime` against last known value.
- Thread-safe: `add_file` can be called from any thread via a lock.

### AgentReloader

Bridges `SourceWatcher` with `AgentLifecycleManager`:

```python
class AgentReloader:
    """Watches an agent source and reloads it via the lifecycle manager."""

    def __init__(self, lifecycle: AgentLifecycleManager, watcher: SourceWatcher) -> None: ...
    def watch(self, spec: ChildSpec) -> None: ...
    def unwatch(self, name: str) -> None: ...
```

On change:
1. Emit `agent_reload_start(name, source_path)`.
2. `lifecycle.terminate(name, reason="source_change")`.
3. `lifecycle.spawn(...)` with same spec.
4. Emit `agent_reload_end(name, new_id)`.

### Supervisor Integration

A supervisor can optionally attach a `SourceWatcher` so that all children are watched:

```python
# In AgentSupervisor.start() when watch=True
self._watcher = SourceWatcher(poll_interval_ms=self._poll_interval * 1000)
self._reloader = AgentReloader(self._lifecycle, self._watcher)
for spec in self._children:
    self._reloader.watch(spec)
self._watcher.start()
```

When a child source changes, the reloader handles the reload; the supervisor monitor loop continues to watch for runtime failures.

### CLI Surface

```bash
# Watch a single agent
axon watch my_agent.ax --name my_agent --arg q=hello --mock --poll-interval 500

# Watch all children of a supervisor
axon supervisor start --name sup --strategy one_for_one \
  --child bot1.ax::b1 --child bot2.ax::b2 --watch

# Stop watching (stop the supervisor / terminate the standalone watcher)
axon agent terminate my_agent
axon supervisor stop sup
```

### Trace Events

| Event | Fields | Description |
|---|---|---|
| `source_reload_start` | `agent_name`, `source_path` | File change detected |
| `source_reload_end` | `agent_name`, `new_id` | Agent successfully re-spawned |
| `source_reload_error` | `agent_name`, `error` | Reload failed |

## Testing Strategy

- Unit test `SourceWatcher` detects mtime changes via explicit `os.utime`.
- Unit test `AgentReloader` invokes terminate → spawn sequence.
- Unit test CLI `watch` command dispatches to the watcher.
- All tests must avoid real file-system races (use `time.sleep` sparingly).

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Rapid edit bursts trigger too many reloads | Debounce: 1-second minimum between reloads for the same file |
| Reload races with running agent | `terminate` waits for thread exit; new `spawn` starts fresh executor |
| Supervisor double-restart (watcher + monitor) | Watcher reload uses same lifecycle; supervisor monitor sees fresh healthy child |

## Future Work

- Native OS notifications via `watchdog` as an optional extra.
- Watch directories for multi-agent projects.
- Incremental re-parse (avoid full `RuntimeExecutor` rebuild).
