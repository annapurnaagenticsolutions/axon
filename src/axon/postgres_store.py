"""PostgreSQL-backed persistence store for AXON runtime.

Requires ``psycopg`` (install with ``pip install psycopg[binary]``).
"""

from __future__ import annotations

import json
import math
import threading
from typing import Any

from axon.persistence_store import PersistenceStore, SCHEMA_SQL


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


class PostgresPersistenceStore(PersistenceStore):
    """PostgreSQL-backed persistence store.

    Args:
        dsn: PostgreSQL connection string (e.g. ``postgresql://user:pass@host/db``)
    """

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise ImportError(
                "psycopg is required for PostgresPersistenceStore. "
                "Install it with: pip install psycopg[binary]"
            ) from exc

        self._dsn = dsn
        self._conn = psycopg.connect(dsn)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        # Adapt SQLite-specific schema to PostgreSQL
        pg_schema = SCHEMA_SQL.replace("AUTOINCREMENT", "GENERATED ALWAYS AS IDENTITY")
        pg_schema = pg_schema.replace("unixepoch()", "EXTRACT(EPOCH FROM NOW())")
        pg_schema = pg_schema.replace("datetime('now')", "NOW()")
        pg_schema = pg_schema.replace("INSERT OR IGNORE", "INSERT")
        pg_schema = pg_schema.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
        # Remove the schema_version insert since PG doesn't support OR IGNORE the same way
        # We'll handle version checking separately if needed
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(pg_schema)
            self._conn.commit()

    # -- Memory -----------------------------------------------------------

    def memory_set(self, agent_name: str, section: str, key: str, value: Any) -> None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_sections (agent_name, section, key, value, updated_at)
                    VALUES (%s, %s, %s, %s, EXTRACT(EPOCH FROM NOW()))
                    ON CONFLICT (agent_name, section, key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = EXTRACT(EPOCH FROM NOW())
                    """,
                    (agent_name, section, key, json.dumps(value)),
                )
            self._conn.commit()

    def memory_get(self, agent_name: str, section: str, key: str) -> Any:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM memory_sections WHERE agent_name = %s AND section = %s AND key = %s",
                    (agent_name, section, key),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def memory_get_section(self, agent_name: str, section: str) -> dict[str, Any]:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT key, value FROM memory_sections WHERE agent_name = %s AND section = %s",
                    (agent_name, section),
                )
                rows = cur.fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    # -- Semantic memory --------------------------------------------------

    def semantic_remember(self, agent_name: str, key: str, value: Any, embedding: list[float]) -> None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO semantic_memory (agent_name, key, value, embedding, timestamp)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (agent_name, key) DO UPDATE
                    SET value = EXCLUDED.value, embedding = EXCLUDED.embedding, timestamp = NOW()
                    """,
                    (agent_name, key, json.dumps(value), json.dumps(embedding)),
                )
            self._conn.commit()

    def semantic_recall(self, agent_name: str, query_embedding: list[float], top_k: int = 5) -> list[Any]:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT key, value, embedding FROM semantic_memory WHERE agent_name = %s",
                    (agent_name,),
                )
                rows = cur.fetchall()
        scored: list[tuple[float, Any]] = []
        for row in rows:
            emb = json.loads(row[2])
            similarity = _cosine_similarity(query_embedding, emb)
            scored.append((similarity, json.loads(row[1])))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [value for _score, value in scored[:top_k]]

    def semantic_forget(self, agent_name: str, key: str) -> bool:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM semantic_memory WHERE agent_name = %s AND key = %s",
                    (agent_name, key),
                )
                deleted = cur.rowcount
            self._conn.commit()
            return deleted > 0

    def semantic_list_keys(self, agent_name: str) -> list[str]:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT key FROM semantic_memory WHERE agent_name = %s",
                    (agent_name,),
                )
                rows = cur.fetchall()
        return [row[0] for row in rows]

    # -- Traces -----------------------------------------------------------

    def trace_append(self, agent_name: str, event_type: str, payload: dict[str, Any]) -> None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO trace_events (agent_name, event_type, payload, timestamp) VALUES (%s, %s, %s, EXTRACT(EPOCH FROM NOW()))",
                    (agent_name, event_type, json.dumps(payload)),
                )
            self._conn.commit()

    def trace_read(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if agent_name is not None:
            conditions.append("agent_name = %s")
            params.append(agent_name)
        if event_type is not None:
            conditions.append("event_type = %s")
            params.append(event_type)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT agent_name, event_type, payload, timestamp FROM trace_events {where} ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [
            {
                "agent_name": row[0],
                "event_type": row[1],
                "payload": json.loads(row[2]),
                "timestamp": row[3],
            }
            for row in rows
        ]

    # -- Checkpoints ------------------------------------------------------

    def checkpoint_save(self, agent_name: str, snapshot: dict[str, Any], path: str | None = None) -> str:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO checkpoints (agent_name, snapshot_path, snapshot_data, created_at) VALUES (%s, %s, %s, EXTRACT(EPOCH FROM NOW())) RETURNING id",
                    (agent_name, path, json.dumps(snapshot)),
                )
                cid = cur.fetchone()[0]
            self._conn.commit()
            return str(cid)

    def checkpoint_load(self, checkpoint_id: str) -> dict[str, Any]:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT snapshot_data FROM checkpoints WHERE id = %s",
                    (checkpoint_id,),
                )
                row = cur.fetchone()
        if row is None:
            raise KeyError(f"Checkpoint {checkpoint_id} not found")
        return json.loads(row[0])

    def checkpoint_list(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT id, agent_name, snapshot_path, created_at FROM checkpoints"
        params: list[Any] = []
        if agent_name is not None:
            query += " WHERE agent_name = %s"
            params.append(agent_name)
        query += " ORDER BY created_at DESC"
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "agent_name": row[1],
                "snapshot_path": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    # -- Lifecycle --------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()
