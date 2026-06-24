# AXON Runtime RFC #005 — Memory Runtime

**Status:** Accepted
**Created:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC documents the memory runtime system that enables AXON agents to persist and retrieve state across executions.

---

## SUMMARY

The memory runtime provides a key-value store with section namespacing, semantic memory via BM25/vector search, and persistence to disk. It enables agents to maintain working memory, episodic memory, and semantic memory across multiple runs.

## PROBLEM / MOTIVATION

AXON agents need to remember state between executions and across agent boundaries. The memory system must:

1. Store key-value pairs in named sections
2. Support semantic search via BM25/vector search
3. Persist memory state to disk
4. Load memory state from disk
5. Emit trace events for memory operations
6. Support checkpointing

## CURRENT BOUNDARY CHECK

This RFC enables memory mutation during runtime execution, which is a Phase 2 capability.

- [x] Memory operations are behind the `axon run` CLI command
- [x] Memory persistence is optional (--checkpoint flag)
- [x] No secrets are stored in memory (caller responsibility)
- [x] Trace events are emitted for all memory operations

## IMPLEMENTATION OVERVIEW

The memory system is implemented in `src/axon/memory_store.py` with the following components:

### MemoryStore

```python
class MemoryStore:
    """Key-value store with section namespacing and semantic search."""
    
    def set(self, section: str, key: str, value: Any) -> None
    def get(self, section: str, key: str) -> Any | None
    def remember(self, key: str, value: Any) -> None
    def recall(self, query: str, top_k: int = 5) -> list[Any]
    def forget(self, key: str) -> bool
    def save_to_file(self, path: Path) -> None
    def load_from_file(self, path: Path) -> None
    def snapshot(self) -> dict[str, dict[str, Any]]
```

### Memory Sections

- `working` - Short-term working memory
- `episodic` - Event-based episodic memory
- `semantic` - Fact-based semantic memory
- `config` - Configuration values

### Semantic Memory

Uses BM25/TF-IDF for text-based semantic search with the following features:
- Tokenization and stemming
- Inverse document frequency weighting
- Top-k retrieval

## AXON SYNTAX EXECUTED

```axon
agent MemoryAgent {
    model: @anthropic/claude-4
    tools: []

    fn run(query: Str) -> Result<Str, Error> {
        // Store in working memory
        memory.working["last_query"] = query
        
        // Recall from semantic memory
        let results = recall(query, top_k: 3)
        
        // Store new fact
        remember("fact_" + query, "Learned: " + query)
        
        Ok("Done")
    }
}
```

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events:**

```python
class MemoryRememberEvent(TraceEvent):
    event_type: str = "memory_remember"
    key: str
    value_summary: str

class MemoryRecallEvent(TraceEvent):
    event_type: str = "memory_recall"
    query_summary: str
    result_count: int
    top_keys: list[str]

class MemoryForgetEvent(TraceEvent):
    event_type: str = "memory_forget"
    key: str
    existed: bool

class CheckpointEvent(TraceEvent):
    event_type: str = "checkpoint"
    path: str
    sections: int
    keys: int
```

## TESTING STRATEGY

- [x] Unit tests for MemoryStore
- [x] Unit tests for semantic search
- [x] Integration tests with runtime executor
- [x] Persistence tests
- [x] All tests pass (192 runtime tests)

## REFERENCES

- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Implementation: `src/axon/memory_store.py`
- Tests: `tests/test_persistent_memory.py`, `tests/test_persistence.py`, `tests/test_store.py`
