"""Tests for PersistenceStore implementations."""

import pytest

from axon.persistence_store import SQLitePersistenceStore


@pytest.fixture
def store() -> SQLitePersistenceStore:
    s = SQLitePersistenceStore(":memory:")
    yield s
    s.close()


class TestMemory:
    def test_memory_set_and_get(self, store: SQLitePersistenceStore) -> None:
        store.memory_set("bot-1", "working", "key1", "value1")
        assert store.memory_get("bot-1", "working", "key1") == "value1"
        assert store.memory_get("bot-1", "working", "missing") is None

    def test_memory_get_section(self, store: SQLitePersistenceStore) -> None:
        store.memory_set("bot-1", "working", "a", 1)
        store.memory_set("bot-1", "working", "b", 2)
        section = store.memory_get_section("bot-1", "working")
        assert section == {"a": 1, "b": 2}

    def test_memory_overwrite(self, store: SQLitePersistenceStore) -> None:
        store.memory_set("bot-1", "working", "k", "old")
        store.memory_set("bot-1", "working", "k", "new")
        assert store.memory_get("bot-1", "working", "k") == "new"

    def test_memory_isolation(self, store: SQLitePersistenceStore) -> None:
        store.memory_set("bot-a", "working", "k", "a")
        store.memory_set("bot-b", "working", "k", "b")
        assert store.memory_get("bot-a", "working", "k") == "a"
        assert store.memory_get("bot-b", "working", "k") == "b"


class TestSemanticMemory:
    def test_remember_and_recall(self, store: SQLitePersistenceStore) -> None:
        store.semantic_remember("bot-1", "doc1", "hello world", [1.0, 0.0, 0.0])
        store.semantic_remember("bot-1", "doc2", "goodbye", [0.0, 1.0, 0.0])
        results = store.semantic_recall("bot-1", [1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0] == "hello world"

    def test_forget(self, store: SQLitePersistenceStore) -> None:
        store.semantic_remember("bot-1", "key1", "val", [1.0, 0.0])
        assert store.semantic_forget("bot-1", "key1") is True
        assert store.semantic_forget("bot-1", "key1") is False

    def test_list_keys(self, store: SQLitePersistenceStore) -> None:
        store.semantic_remember("bot-1", "k1", "v1", [1.0])
        store.semantic_remember("bot-1", "k2", "v2", [0.0])
        keys = store.semantic_list_keys("bot-1")
        assert sorted(keys) == ["k1", "k2"]


class TestTraces:
    def test_trace_append_and_read(self, store: SQLitePersistenceStore) -> None:
        store.trace_append("bot-1", "agent_start", {"source": "test.ax"})
        store.trace_append("bot-1", "agent_end", {"result": "ok"})
        events = store.trace_read(agent_name="bot-1")
        assert len(events) == 2
        assert events[0]["event_type"] == "agent_end"  # DESC order
        assert events[1]["event_type"] == "agent_start"

    def test_trace_filter_by_type(self, store: SQLitePersistenceStore) -> None:
        store.trace_append("bot-1", "agent_start", {})
        store.trace_append("bot-1", "agent_end", {})
        events = store.trace_read(agent_name="bot-1", event_type="agent_start")
        assert len(events) == 1
        assert events[0]["event_type"] == "agent_start"

    def test_trace_read_limit(self, store: SQLitePersistenceStore) -> None:
        for i in range(5):
            store.trace_append("bot-1", "tick", {"i": i})
        events = store.trace_read(agent_name="bot-1", limit=2)
        assert len(events) == 2


class TestCheckpoints:
    def test_checkpoint_save_and_load(self, store: SQLitePersistenceStore) -> None:
        cid = store.checkpoint_save("bot-1", {"status": "ok"}, path="/tmp/ckpt.json")
        data = store.checkpoint_load(cid)
        assert data["status"] == "ok"

    def test_checkpoint_list(self, store: SQLitePersistenceStore) -> None:
        store.checkpoint_save("bot-a", {"data": "a"})
        store.checkpoint_save("bot-b", {"data": "b"})
        store.checkpoint_save("bot-a", {"data": "a2"})
        assert len(store.checkpoint_list()) == 3
        assert len(store.checkpoint_list(agent_name="bot-a")) == 2
        assert len(store.checkpoint_list(agent_name="bot-b")) == 1

    def test_checkpoint_load_missing(self, store: SQLitePersistenceStore) -> None:
        with pytest.raises(KeyError):
            store.checkpoint_load("99999")
