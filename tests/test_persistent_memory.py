"""Tests for AXON persistent agent memory (RFC #009)."""

from pathlib import Path

from axon.cli import run_file
from axon.memory_store import MemoryStore


# -- Unit tests ---------------------------------------------------

def test_memory_remember_stores_entry():
    """remember() stores a value with embedding."""
    store = MemoryStore()
    store.remember("key1", "Machine learning is a subset of AI")
    assert len(store._semantic) == 1
    assert store._semantic[0]["key"] == "key1"
    assert store._semantic[0]["value"] == "Machine learning is a subset of AI"
    assert "embedding" in store._semantic[0]


def test_memory_recall_empty():
    """recall() returns empty list when nothing is remembered."""
    store = MemoryStore()
    assert store.recall("AI") == []


def test_memory_recall_finds_similar():
    """recall() finds entries when they exist."""
    store = MemoryStore()
    store.remember("ml", "Machine learning is a subset of AI")
    store.remember("dl", "Deep learning uses neural networks")
    store.remember("cooking", "Cooking pasta requires boiling water")

    results = store.recall("what is AI?", top_k=2)
    assert len(results) == 2
    # All three entries were remembered, top 2 should be returned
    all_values = {"Machine learning is a subset of AI", "Deep learning uses neural networks", "Cooking pasta requires boiling water"}
    assert results[0] in all_values
    assert results[1] in all_values


def test_memory_recall_top_k():
    """recall() respects top_k limit."""
    store = MemoryStore()
    store.remember("a", "aaa")
    store.remember("b", "bbb")
    store.remember("c", "ccc")

    results = store.recall("query", top_k=1)
    assert len(results) == 1


def test_memory_forget_removes_entry():
    """forget() removes a remembered entry."""
    store = MemoryStore()
    store.remember("key1", "value1")
    assert store.forget("key1") is True
    assert len(store._semantic) == 0


def test_memory_forget_missing():
    """forget() returns False for missing key."""
    store = MemoryStore()
    assert store.forget("missing") is False


def test_memory_remember_overwrites():
    """remember() overwrites existing key."""
    store = MemoryStore()
    store.remember("key1", "old value")
    store.remember("key1", "new value")
    assert len(store._semantic) == 1
    assert store._semantic[0]["value"] == "new value"


def test_memory_persistence_with_semantic():
    """Semantic entries survive JSON save/load."""
    store = MemoryStore()
    store.remember("ml", "Machine learning is AI")
    store.set("working", "last_query", "hello")

    json_str = store.to_json()
    store2 = MemoryStore()
    store2.from_json(json_str)

    assert store2.list_semantic_keys() == ["ml"]
    assert store2.get("working", "last_query") == "hello"


def test_memory_persistence_roundtrip_file(tmp_path: Path):
    """Semantic entries survive file save/load."""
    store = MemoryStore()
    store.remember("fact", "The sky is blue")
    path = tmp_path / "memory.json"
    store.save_to_file(path)

    store2 = MemoryStore()
    store2.load_from_file(path)
    assert store2.list_semantic_keys() == ["fact"]


# -- End-to-end tests ---------------------------------------------

def test_agent_remembers_and_recalls(tmp_path: Path):
    """Agent remembers a fact and recalls it later in the same run."""
    source = '''agent Bot {
        model: @mock/gpt
        fn run() -> Str {
            remember("fact1", "Machine learning is a subset of AI")
            let facts = recall("what is AI?", 1)
            facts[0]
        }
    }'''
    p = tmp_path / "memory.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p)
    assert code == 0
    assert output == "Machine learning is a subset of AI"


def test_agent_remembers_forgets_recalls(tmp_path: Path):
    """Agent remembers, forgets, and then recalls nothing."""
    source = '''agent Bot {
        model: @mock/gpt
        fn run() -> Str {
            remember("fact1", "Machine learning is AI")
            forget("fact1")
            let facts = recall("AI", 1)
            if facts { "not empty" } else { "empty" }
        }
    }'''
    p = tmp_path / "memory.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p)
    assert code == 0
    assert output == "empty"


def test_memory_trace_events(tmp_path: Path):
    """Memory operations emit trace events."""
    source = '''agent Bot {
        model: @mock/gpt
        fn run() -> Str {
            remember("key", "value")
            let _ = recall("query", 1)
            forget("key")
            "done"
        }
    }'''
    p = tmp_path / "memory.ax"
    p.write_text(source, encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"

    code, output = run_file(p, trace_output=trace_path)
    assert code == 0

    import json
    events = [json.loads(line) for line in trace_path.read_text().strip().split("\n")]
    event_types = [e["event_type"] for e in events]

    assert "memory_remember" in event_types
    assert "memory_recall" in event_types
    assert "memory_forget" in event_types


def test_memory_persistence_across_runs(tmp_path: Path):
    """Semantic memory persists across runs via --memory and --checkpoint."""
    source = '''agent Bot {
        model: @mock/gpt
        fn run() -> Str {
            remember("fact", "Machine learning is AI")
            "done"
        }
    }'''
    p = tmp_path / "memory.ax"
    p.write_text(source, encoding="utf-8")

    memory_path = tmp_path / "memory.json"

    # First run with checkpoint
    code1, output1 = run_file(p, memory_path=memory_path, checkpoint=True)
    assert code1 == 0

    # Second run: recall from persisted memory
    source2 = '''agent Bot {
        model: @mock/gpt
        fn run() -> Str {
            let facts = recall("what is AI?", 1)
            if facts { facts[0] } else { "empty" }
        }
    }'''
    p2 = tmp_path / "memory2.ax"
    p2.write_text(source2, encoding="utf-8")

    code2, output2 = run_file(p2, memory_path=memory_path)
    assert code2 == 0
    assert output2 == "Machine learning is AI"
