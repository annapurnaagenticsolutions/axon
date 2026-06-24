# RFC #018 — PostgreSQL-backed Persistence

**Status:** Draft  
**Phase:** 7 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Replace file-based persistence (JSON memory, JSONL traces, JSON checkpoints) with a relational database backend. This sprint introduces a `PersistenceStore` abstraction with `SQLitePersistenceStore` (built-in, for local dev/tests) and `PostgresPersistenceStore` (for production). All existing `MemoryStore`, trace emission, and checkpoint logic are refactored to use the store abstraction, with zero breaking changes to the CLI or API.

## Motivation

Current state:
- `MemoryStore` is in-memory with optional JSON file save/load
- `TraceEmitter` writes JSONL files
- `CheckpointManager` writes JSON snapshots

Problems for production:
- No ACID guarantees across agent restarts
- Concurrent agent writes can corrupt JSON files
- No query capability for traces or memory
- No cross-process sharing

## Goals

- `PersistenceStore` abstract base class with methods for memory, traces, and checkpoints
- `SQLitePersistenceStore` using built-in `sqlite3` (default for dev/tests)
- `PostgresPersistenceStore` using `psycopg` (optional extra, for production)
- Schema: agents, memory_sections, semantic_memory, trace_events, checkpoints
- Config-driven: `AXON_DB_URL` env var or `--db-url` CLI flag
- All existing tests pass with SQLite backend
- No breaking changes to CLI or API

## Non-Goals

- Full ORM (SQLAlchemy, Django ORM)
- Database replication or clustering
- Migration framework beyond simple CREATE TABLE scripts
- pgvector extension (future RAG sprint)

## Schema

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    source_path TEXT NOT NULL,
    status TEXT NOT NULL,
    last_output TEXT,
    last_error TEXT,
    created_at REAL DEFAULT (unixepoch())
);

CREATE TABLE memory_sections (
    agent_name TEXT NOT NULL,
    section TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,  -- JSON
    updated_at REAL DEFAULT (unixepoch()),
    PRIMARY KEY (agent_name, section, key)
);

CREATE TABLE semantic_memory (
    agent_name TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,  -- JSON
    embedding TEXT NOT NULL,  -- JSON array
    timestamp TEXT NOT NULL,
    PRIMARY KEY (agent_name, key)
);

CREATE TABLE trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON
    timestamp REAL DEFAULT (unixepoch())
);

CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    snapshot_data TEXT NOT NULL,  -- JSON
    created_at REAL DEFAULT (unixepoch())
);
```

## Design

### PersistenceStore ABC

```python
class PersistenceStore(ABC):
    def memory_set(self, agent_name: str, section: str, key: str, value: Any) -> None: ...
    def memory_get(self, agent_name: str, section: str, key: str) -> Any: ...
    def memory_get_section(self, agent_name: str, section: str) -> dict[str, Any]: ...
    def semantic_remember(self, agent_name: str, key: str, value: Any, embedding: list[float]) -> None: ...
    def semantic_recall(self, agent_name: str, query_embedding: list[float], top_k: int) -> list[Any]: ...
    def trace_append(self, agent_name: str, event_type: str, payload: dict[str, Any]) -> None: ...
    def trace_read(self, agent_name: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]: ...
    def checkpoint_save(self, agent_name: str, snapshot: dict[str, Any]) -> str: ...
    def checkpoint_load(self, agent_name: str, checkpoint_id: str) -> dict[str, Any]: ...
    def close(self) -> None: ...
```

### Config Integration

`RuntimeConfig` gains `db_url: str | None = None`. If set, the runtime uses the store instead of in-memory files.

## Testing Strategy

- Unit test `SQLitePersistenceStore` with in-memory `:memory:` database
- Unit test `MemoryStore` integration with `SQLitePersistenceStore`
- Verify existing tests still pass (they use the default in-memory path)
- Add `AXON_DB_URL` env var test

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| psycopg not installed in dev environments | SQLite backend is the default; psycopg is optional |
| Schema drift between versions | Simple version table; future migration scripts |
| Performance of SQLite for large traces | Document 10MB soft limit; Postgres for large scale |
