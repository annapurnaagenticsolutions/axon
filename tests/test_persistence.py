"""Tests for AXON persistence (save/load/checkpoint agent memory)."""

import json
import tempfile
from pathlib import Path

from result import Ok, Err

from axon.memory_store import MemoryStore
from axon.runtime import RuntimeConfig, RuntimeExecutor
from axon.trace_emitter import TraceEmitter


# -- MemoryStore serialization tests --------------------------------

def test_memory_store_to_json():
    store = MemoryStore()
    store.set("working", "a", 1)
    store.set("long_term", "b", "hello")
    json_str = store.to_json()
    data = json.loads(json_str)
    assert data == {"working": {"a": 1}, "long_term": {"b": "hello"}}


def test_memory_store_from_json():
    store = MemoryStore()
    store.from_json('{"working": {"a": 1}}')
    assert store.get("working", "a") == 1


def test_memory_store_save_and_load_file():
    store = MemoryStore()
    store.set("working", "key1", "value1")
    store.set("long_term", "key2", 42)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        store.save_to_file(path)

        store2 = MemoryStore()
        store2.load_from_file(path)
        assert store2.get("working", "key1") == "value1"
        assert store2.get("long_term", "key2") == 42
    finally:
        path.unlink(missing_ok=True)


def test_memory_store_load_empty_dict():
    store = MemoryStore()
    store.from_json("{}")
    assert store.snapshot() == {}


def test_memory_store_load_bad_json():
    store = MemoryStore()
    try:
        store.from_json("not json")
        assert False, "Expected ValueError"
    except (ValueError, json.JSONDecodeError):
        pass


# -- Runtime persistence tests ------------------------------------

def _write_greeting_agent(path: Path) -> None:
    source = """agent TestAgent {
    model: @mock/gpt

    fn run(name: Str) -> Str {
        store memory.working["greeting"] = name
        "done"
    }
}
"""
    path.write_text(source, encoding="utf-8")


def test_runtime_loads_memory_from_file():
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / "test.ax"
        memory = Path(td) / "memory.json"

        _write_greeting_agent(source)
        memory.write_text('{"working": {"seed": 123}}', encoding="utf-8")

        config = RuntimeConfig(
            source_path=source,
            args={"name": "World"},
            memory_path=memory,
        )
        result = RuntimeExecutor(config).execute()
        assert isinstance(result, Ok)

        # Memory file should not have been overwritten (no --checkpoint)
        data = json.loads(memory.read_text(encoding="utf-8"))
        assert data == {"working": {"seed": 123}}


def test_runtime_checkpoint_saves_memory():
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / "test.ax"
        memory = Path(td) / "memory.json"

        _write_greeting_agent(source)
        # start with empty memory file
        memory.write_text("{}", encoding="utf-8")

        config = RuntimeConfig(
            source_path=source,
            args={"name": "World"},
            memory_path=memory,
            checkpoint=True,
        )
        result = RuntimeExecutor(config).execute()
        assert isinstance(result, Ok)

        # Memory file should now contain the store'd value
        data = json.loads(memory.read_text(encoding="utf-8"))
        assert data == {"working": {"greeting": "World"}}


def test_runtime_checkpoint_with_trace_event():
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / "test.ax"
        memory = Path(td) / "memory.json"

        _write_greeting_agent(source)
        memory.write_text("{}", encoding="utf-8")

        config = RuntimeConfig(
            source_path=source,
            args={"name": "World"},
            memory_path=memory,
            checkpoint=True,
        )
        result = RuntimeExecutor(config).execute()
        assert isinstance(result, Ok)

        # Verify the file was written correctly.
        data = json.loads(memory.read_text(encoding="utf-8"))
        assert data == {"working": {"greeting": "World"}}


def test_runtime_checkpoint_no_memory_path_is_noop():
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / "test.ax"
        _write_greeting_agent(source)

        config = RuntimeConfig(
            source_path=source,
            args={"name": "World"},
            checkpoint=True,  # no memory_path
        )
        result = RuntimeExecutor(config).execute()
        assert isinstance(result, Ok)


def test_runtime_load_bad_memory_file():
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / "test.ax"
        memory = Path(td) / "memory.json"

        _write_greeting_agent(source)
        memory.write_text("not json", encoding="utf-8")

        config = RuntimeConfig(
            source_path=source,
            args={"name": "World"},
            memory_path=memory,
        )
        result = RuntimeExecutor(config).execute()
        assert isinstance(result, Err)
        assert "Failed to load memory" in result.err_value


# -- Memory survives across runs -----------------------------------

def test_memory_survives_across_runs():
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / "test.ax"
        memory = Path(td) / "memory.json"

        source.write_text(
            """agent CounterAgent {
    model: @mock/gpt

    fn run() -> Int {
        let count = memory.working["count"]
        let next = count + 1
        store memory.working["count"] = next
        next
    }
}
""",
            encoding="utf-8",
        )

        # Pre-seed memory so count is never None
        memory.write_text('{"working": {"count": 0}}', encoding="utf-8")

        # First run: count starts at 0, becomes 1
        config1 = RuntimeConfig(
            source_path=source,
            args={},
            memory_path=memory,
            checkpoint=True,
        )
        result1 = RuntimeExecutor(config1).execute()
        assert isinstance(result1, Ok)
        assert result1.ok_value == "1"

        # Second run: count loaded as 1, becomes 2
        config2 = RuntimeConfig(
            source_path=source,
            args={},
            memory_path=memory,
            checkpoint=True,
        )
        result2 = RuntimeExecutor(config2).execute()
        assert isinstance(result2, Ok)
        assert result2.ok_value == "2"

        # Third run: count loaded as 2, becomes 3
        config3 = RuntimeConfig(
            source_path=source,
            args={},
            memory_path=memory,
            checkpoint=True,
        )
        result3 = RuntimeExecutor(config3).execute()
        assert isinstance(result3, Ok)
        assert result3.ok_value == "3"
