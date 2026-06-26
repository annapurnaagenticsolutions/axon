"""Tests for the AXON database client (db_client.py)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from axon.db_client import Database, db_builtins


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(base_dir=tmp_path)


@pytest.fixture
def db_with_table(db: Database, tmp_path: Path) -> str:
    db_path = "test.db"
    db.execute(db_path, "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, qty INTEGER)")
    db.execute(db_path, "INSERT INTO items (name, qty) VALUES ('apple', 5)")
    db.execute(db_path, "INSERT INTO items (name, qty) VALUES ('banana', 3)")
    return db_path


class TestDatabaseQuery:
    def test_query_returns_rows_as_dicts(self, db: Database, db_with_table: str) -> None:
        rows = db.query(db_with_table, "SELECT * FROM items ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "apple"
        assert rows[0]["qty"] == 5
        assert rows[1]["name"] == "banana"

    def test_query_with_params(self, db: Database, db_with_table: str) -> None:
        rows = db.query(db_with_table, "SELECT * FROM items WHERE name = ?", ["apple"])
        assert len(rows) == 1
        assert rows[0]["name"] == "apple"

    def test_query_empty_result(self, db: Database, db_with_table: str) -> None:
        rows = db.query(db_with_table, "SELECT * FROM items WHERE name = ?", ["nonexistent"])
        assert rows == []


class TestDatabaseExecute:
    def test_execute_insert(self, db: Database, db_with_table: str) -> None:
        affected = db.execute(db_with_table, "INSERT INTO items (name, qty) VALUES ('cherry', 10)")
        assert affected == 1
        rows = db.query(db_with_table, "SELECT * FROM items WHERE name = ?", ["cherry"])
        assert len(rows) == 1
        assert rows[0]["qty"] == 10

    def test_execute_update(self, db: Database, db_with_table: str) -> None:
        affected = db.execute(db_with_table, "UPDATE items SET qty = ? WHERE name = ?", [99, "apple"])
        assert affected == 1
        rows = db.query(db_with_table, "SELECT qty FROM items WHERE name = ?", ["apple"])
        assert rows[0]["qty"] == 99

    def test_execute_delete(self, db: Database, db_with_table: str) -> None:
        affected = db.execute(db_with_table, "DELETE FROM items WHERE name = ?", ["banana"])
        assert affected == 1
        rows = db.query(db_with_table, "SELECT * FROM items")
        assert len(rows) == 1


class TestDatabaseTransaction:
    def test_transaction_multiple_statements(self, db: Database, db_with_table: str) -> None:
        total = db.transaction(db_with_table, [
            {"sql": "INSERT INTO items (name, qty) VALUES ('date', 8)"},
            {"sql": "INSERT INTO items (name, qty) VALUES ('elderberry', 12)"},
        ])
        assert total == 2
        rows = db.query(db_with_table, "SELECT * FROM items")
        assert len(rows) == 4

    def test_transaction_with_params(self, db: Database, db_with_table: str) -> None:
        total = db.transaction(db_with_table, [
            {"sql": "INSERT INTO items (name, qty) VALUES (?, ?)", "params": ["fig", 6]},
            {"sql": "UPDATE items SET qty = ? WHERE name = ?", "params": [100, "apple"]},
        ])
        assert total == 2

    def test_transaction_rollback_on_error(self, db: Database, db_with_table: str) -> None:
        with pytest.raises(sqlite3.OperationalError):
            db.transaction(db_with_table, [
                {"sql": "INSERT INTO items (name, qty) VALUES ('grape', 7)"},
                {"sql": "INVALID SQL STATEMENT"},
            ])
        rows = db.query(db_with_table, "SELECT * FROM items WHERE name = ?", ["grape"])
        assert len(rows) == 0


class TestDatabaseIntrospection:
    def test_tables(self, db: Database, db_with_table: str) -> None:
        tables = db.tables(db_with_table)
        assert "items" in tables

    def test_schema(self, db: Database, db_with_table: str) -> None:
        schema = db.schema(db_with_table, "items")
        assert len(schema) == 3
        names = [col["name"] for col in schema]
        assert "id" in names
        assert "name" in names
        assert "qty" in names
        assert schema[0]["pk"] is True


class TestDatabaseSandbox:
    def test_path_traversal_rejected(self, db: Database) -> None:
        with pytest.raises(PermissionError, match="escapes sandbox"):
            db.query("../../../etc/passwd", "SELECT 1")

    def test_absolute_path_rejected(self, db: Database) -> None:
        with pytest.raises(PermissionError, match="escapes sandbox"):
            db.query("/etc/passwd", "SELECT 1")


class TestDbBuiltins:
    def test_db_builtins_returns_database(self, tmp_path: Path) -> None:
        builtins = db_builtins(base_dir=tmp_path)
        assert "db" in builtins
        assert isinstance(builtins["db"], Database)

    def test_db_builtins_default_base(self) -> None:
        builtins = db_builtins()
        assert "db" in builtins
        assert isinstance(builtins["db"], Database)


class TestDatabaseConnectionReuse:
    def test_connection_reused(self, db: Database, db_with_table: str) -> None:
        db.query(db_with_table, "SELECT * FROM items")
        db.query(db_with_table, "SELECT * FROM items")
        assert db_with_table in db._connections
        assert len(db._connections) == 1

    def test_close_clears_connections(self, db: Database, db_with_table: str) -> None:
        db.query(db_with_table, "SELECT * FROM items")
        assert len(db._connections) == 1
        db.close()
        assert len(db._connections) == 0
