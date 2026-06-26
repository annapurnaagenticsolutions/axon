"""Database client for AXON tool dispatch.

Provides ``db.query``, ``db.execute``, ``db.transaction``, ``db.tables``,
and ``db.schema`` builtins that AXON ``tool`` bodies can call directly.

Uses Python's built-in ``sqlite3`` module so that compiler-core tests
remain free of external dependencies.  The database path is resolved
relative to a configurable ``base_dir`` for sandbox safety.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """Sandboxed SQLite database operations for AXON tool bodies.

    The database path is resolved relative to ``base_dir``.  Attempts to
    escape the base directory via ``..`` or absolute paths are rejected
    with ``PermissionError``.
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self._base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
        self._connections: dict[str, sqlite3.Connection] = {}

    def _resolve(self, path: str) -> Path:
        target = (self._base / path).resolve()
        try:
            target.relative_to(self._base)
        except ValueError:
            raise PermissionError(
                f"Database path '{path}' escapes sandbox base directory: {self._base}"
            )
        return target

    def _connect(self, path: str) -> sqlite3.Connection:
        if path not in self._connections:
            target = self._resolve(path)
            self._connections[path] = sqlite3.connect(
                str(target),
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._connections[path].row_factory = sqlite3.Row
        return self._connections[path]

    def query(
        self,
        path: str,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return rows as a list of dicts."""
        conn = self._connect(path)
        cursor = conn.execute(sql, params or [])
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute(
        self,
        path: str,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        """Execute a single SQL statement and return rows affected."""
        conn = self._connect(path)
        cursor = conn.execute(sql, params or [])
        conn.commit()
        return cursor.rowcount

    def transaction(
        self,
        path: str,
        statements: list[dict[str, Any]],
    ) -> int:
        """Execute multiple SQL statements in a single transaction.

        Each statement is a dict with ``sql`` (str) and optional ``params`` (list).
        Returns total rows affected across all statements.
        """
        conn = self._connect(path)
        total = 0
        try:
            for stmt in statements:
                sql = stmt.get("sql", "")
                params = stmt.get("params", [])
                cursor = conn.execute(sql, params)
                total += cursor.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return total

    def tables(self, path: str) -> list[str]:
        """Return a list of table names in the database."""
        rows = self.query(
            path,
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        )
        return [row["name"] for row in rows]

    def schema(self, path: str, table: str) -> list[dict[str, Any]]:
        """Return column information for a table."""
        rows = self.query(path, f"PRAGMA table_info({table})")
        return [
            {
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "pk": bool(row["pk"]),
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close all open database connections."""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def db_builtins(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Return the ``db`` builtin to inject into tool scopes."""
    return {"db": Database(base_dir=base_dir)}
