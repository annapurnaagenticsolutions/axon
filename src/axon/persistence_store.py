"""Persistence store abstraction for AXON runtime.

Provides SQLite and PostgreSQL backends for agent memory, trace events,
and checkpoint storage. SQLite is the default (built-in); PostgreSQL is
an optional extra.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    norm_a = _norm(a)
    norm_b = _norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return _dot(a, b) / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Schema (shared between SQLite and Postgres)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    source_path TEXT NOT NULL,
    status TEXT NOT NULL,
    last_output TEXT,
    last_error TEXT,
    created_at REAL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS memory_sections (
    agent_name TEXT NOT NULL,
    section TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at REAL DEFAULT (unixepoch()),
    PRIMARY KEY (agent_name, section, key)
);

CREATE TABLE IF NOT EXISTS semantic_memory (
    agent_name TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    embedding TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    PRIMARY KEY (agent_name, key)
);

CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp REAL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    snapshot_path TEXT,
    snapshot_data TEXT NOT NULL,
    created_at REAL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class PersistenceStore(ABC):
    """Abstract persistence backend for AXON runtime."""

    @abstractmethod
    def memory_set(self, agent_name: str, section: str, key: str, value: Any) -> None:
        """Store a value in a memory section."""
        ...

    @abstractmethod
    def memory_get(self, agent_name: str, section: str, key: str) -> Any:
        """Retrieve a value from a memory section."""
        ...

    @abstractmethod
    def memory_get_section(self, agent_name: str, section: str) -> dict[str, Any]:
        """Retrieve an entire memory section."""
        ...

    @abstractmethod
    def semantic_remember(self, agent_name: str, key: str, value: Any, embedding: list[float]) -> None:
        """Store a semantic memory entry."""
        ...

    @abstractmethod
    def semantic_recall(self, agent_name: str, query_embedding: list[float], top_k: int = 5) -> list[Any]:
        """Recall top-k semantically similar entries."""
        ...

    @abstractmethod
    def semantic_forget(self, agent_name: str, key: str) -> bool:
        """Remove a semantic memory entry. Returns True if removed."""
        ...

    @abstractmethod
    def semantic_list_keys(self, agent_name: str) -> list[str]:
        """Return all semantic memory keys for an agent."""
        ...

    @abstractmethod
    def trace_append(self, agent_name: str, event_type: str, payload: dict[str, Any]) -> None:
        """Append a trace event."""
        ...

    @abstractmethod
    def trace_read(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Read trace events with optional filters."""
        ...

    @abstractmethod
    def checkpoint_save(self, agent_name: str, snapshot: dict[str, Any], path: str | None = None) -> str:
        """Save a checkpoint. Returns the checkpoint identifier."""
        ...

    @abstractmethod
    def checkpoint_load(self, checkpoint_id: str) -> dict[str, Any]:
        """Load a checkpoint by identifier."""
        ...

    @abstractmethod
    def checkpoint_list(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        """List checkpoints, optionally filtered by agent."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the store and release resources."""
        ...


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

class SQLitePersistenceStore(PersistenceStore):
    """SQLite-backed persistence store.

    Uses the built-in ``sqlite3`` module. Pass ``":memory:"`` for an
    in-memory database (useful in tests).
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()

    # -- Memory -----------------------------------------------------------

    def memory_set(self, agent_name: str, section: str, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO memory_sections (agent_name, section, key, value, updated_at) VALUES (?, ?, ?, ?, unixepoch())",
                (agent_name, section, key, json.dumps(value)),
            )
            self._conn.commit()

    def memory_get(self, agent_name: str, section: str, key: str) -> Any:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM memory_sections WHERE agent_name = ? AND section = ? AND key = ?",
                (agent_name, section, key),
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["value"])

    def memory_get_section(self, agent_name: str, section: str) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM memory_sections WHERE agent_name = ? AND section = ?",
                (agent_name, section),
            ).fetchall()
            return {row["key"]: json.loads(row["value"]) for row in rows}

    # -- Semantic memory --------------------------------------------------

    def semantic_remember(self, agent_name: str, key: str, value: Any, embedding: list[float]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO semantic_memory (agent_name, key, value, embedding, timestamp) VALUES (?, ?, ?, ?, datetime('now'))",
                (agent_name, key, json.dumps(value), json.dumps(embedding)),
            )
            self._conn.commit()

    def semantic_recall(self, agent_name: str, query_embedding: list[float], top_k: int = 5) -> list[Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value, embedding FROM semantic_memory WHERE agent_name = ?",
                (agent_name,),
            ).fetchall()
        scored: list[tuple[float, Any]] = []
        for row in rows:
            emb = json.loads(row["embedding"])
            similarity = _cosine_similarity(query_embedding, emb)
            scored.append((similarity, json.loads(row["value"])))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [value for _score, value in scored[:top_k]]

    def semantic_forget(self, agent_name: str, key: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM semantic_memory WHERE agent_name = ? AND key = ?",
                (agent_name, key),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def semantic_list_keys(self, agent_name: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key FROM semantic_memory WHERE agent_name = ?",
                (agent_name,),
            ).fetchall()
            return [row["key"] for row in rows]

    # -- Traces -----------------------------------------------------------

    def trace_append(self, agent_name: str, event_type: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO trace_events (agent_name, event_type, payload, timestamp) VALUES (?, ?, ?, unixepoch())",
                (agent_name, event_type, json.dumps(payload)),
            )
            self._conn.commit()

    def trace_read(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query = "SELECT agent_name, event_type, payload, timestamp FROM trace_events WHERE 1=1"
        params: list[Any] = []
        if agent_name is not None:
            query += " AND agent_name = ?"
            params.append(agent_name)
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [
            {
                "agent_name": row["agent_name"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    # -- Checkpoints ------------------------------------------------------

    def checkpoint_save(self, agent_name: str, snapshot: dict[str, Any], path: str | None = None) -> str:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO checkpoints (agent_name, snapshot_path, snapshot_data, created_at) VALUES (?, ?, ?, unixepoch())",
                (agent_name, path, json.dumps(snapshot)),
            )
            self._conn.commit()
            return str(cur.lastrowid)

    def checkpoint_load(self, checkpoint_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT snapshot_data FROM checkpoints WHERE id = ?",
                (checkpoint_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Checkpoint {checkpoint_id} not found")
        return json.loads(row["snapshot_data"])

    def checkpoint_list(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT id, agent_name, snapshot_path, created_at FROM checkpoints"
        params: list[Any] = []
        if agent_name is not None:
            query += " WHERE agent_name = ?"
            params.append(agent_name)
        query += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "agent_name": row["agent_name"],
                "snapshot_path": row["snapshot_path"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # -- Lifecycle --------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()
