# AXON Runtime RFC #009 — Persistent Agent Memory

**Status:** Draft
**Created:** 2026-06-09
**Owner:** axon-dev

> Runtime work must be proposed before implementation. This template is intentionally strict because runtime behavior can call providers, dispatch tools, mutate memory, index RAG data, execute flows, or replay traces.

---

## SUMMARY

Propose a minimal persistent agent memory runtime for AXON. This extends the existing `MemoryStore` with **semantic memory** — vector-based storage and retrieval that persists across runs via `--memory` and `--checkpoint`. The runtime provides:

1. **`memory.remember(key, value)`** — stores a value with an embedding for semantic search
2. **`memory.recall(query, top_k)`** — searches stored memories by semantic similarity
3. **`memory.forget(key)`** — removes a memory entry
4. **Persistence via `--memory` / `--checkpoint`** — semantic entries are saved/loaded alongside working memory

The intended output is an agent that remembers facts across executions and recalls them by meaning, not just exact key matching:
```axon
agent Bot {
    model: @mock/gpt
    fn run(question: Str) -> Str {
        let facts = memory.recall(query: question, top_k: 3)
        facts
    }
}
```

With `--memory memory.json` the agent loads previously remembered facts. With `--checkpoint` new facts are persisted for the next run.

## PROBLEM / MOTIVATION

AXON already has `memory.working["key"] = value` for transient key-value storage within a single run, and `--memory` / `--checkpoint` for persistence. But real agents need:

1. **Semantic recall** — "What do I know about machine learning?" should find entries about "deep learning", "neural networks", and "training models" even if none use the exact query words. Exact key lookup is insufficient.

2. **Persistent learning** — An agent that indexes documents in one run should recall that knowledge in subsequent runs without re-indexing. The `--memory` file should survive across executions.

3. **Forgetting** — Agents need to remove outdated or incorrect memories. A `forget` operation is essential for long-running agents.

This RFC keeps the scope narrow: in-memory vector search using the existing mock embedder, JSON persistence, no external vector DB.

## CURRENT BOUNDARY CHECK

Confirm the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md` and state exactly what this RFC proposes to change.

Required confirmations:

- [x] This RFC explicitly permits semantic memory operations inside agent bodies.
- [x] This RFC uses existing mock embedder from RFC #006 (no provider calls).
- [x] Do not dispatch real tools without mocking.
- [x] Do not resolve, print, or snapshot API keys.
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.
- [x] Deterministic test doubles (mock embedder + in-memory cosine similarity) defined.
- [x] Document exactly which AXON syntax subset the runtime will execute — listed below.
- [x] Trace emission guarantees defined below.

## PROPOSED RUNTIME SCOPE

Extend `MemoryStore` with semantic memory capabilities:

1. **Semantic storage** (`memory.remember`)
   - Computes embedding of `value` via existing `mock_embed`
   - Stores entry: `{"key": str, "value": Any, "embedding": list[float], "timestamp": str}`
   - Entries live in a `_semantic` section within `MemoryStore`

2. **Semantic recall** (`memory.recall`)
   - Computes embedding of `query` via existing `mock_embed`
   - Cosine similarity search against all remembered entries
   - Returns top_k values sorted by similarity (descending)
   - Returns empty list if no memories exist

3. **Forgetting** (`memory.forget`)
   - Removes entry by exact key match from semantic store
   - No-op if key does not exist

4. **Persistence**
   - Semantic entries are included in `MemoryStore.to_json()` / `from_json()`
   - `--memory` loads semantic memories at runtime start
   - `--checkpoint` saves semantic memories at runtime end
   - Existing `memory.working` persistence unchanged

5. **Trace events**
   - `memory_remember` — `key`, `value_summary`
   - `memory_recall` — `query_summary`, `result_count`, `top_keys`
   - `memory_forget` — `key`, `existed`

6. **Runtime integration**
   - `memory.remember`, `memory.recall`, `memory.forget` are callable via the existing `memory` scope object
   - No new CLI flags needed (uses existing `--memory` and `--checkpoint`)

## NON-GOALS

- Do not implement unrelated runtime subsystems.
- Do not broaden provider/tool/memory behavior beyond this RFC.

## AXON SYNTAX EXECUTED

This RFC executes the following constructs inside agent bodies:

```axon
// Remember a fact for later semantic recall
memory.remember("ml_basics", "Machine learning is a subset of AI")

// Recall facts semantically similar to a query
let facts = memory.recall(query: "what is AI?", top_k: 3)

// Forget a specific memory
memory.forget("ml_basics")

// Existing working memory (unchanged)
store memory.working["last_question"] = question
```

Specifically:
- `memory.remember(key, value)` — stores value with embedding
- `memory.recall(query, top_k)` — semantic search, returns list of values
- `memory.forget(key)` — removes entry by key
- `store memory.working["key"] = value` — existing key-value storage (unchanged)

## PROVIDER PLUGIN IMPACT

No changes to provider plugin protocol. Semantic memory uses the existing `mock_embed` function (RFC #006) to produce deterministic embeddings. No provider calls are made for memory operations.

## TOOL DISPATCH IMPACT

No changes to tool dispatch. Memory operations are pure in-memory computations. Existing tool dispatch boundaries and permissions remain unchanged.

## MEMORY / RAG / FLOW IMPACT

- **Memory: EXTENDED** — `MemoryStore` gains semantic storage (`_semantic` section with embeddings), `remember`, `recall`, `forget` methods. Existing `working` section and persistence unchanged.
- **RAG:** No changes to RAG indexing or retrieval. Existing RFC #006 behavior unchanged.
- **Flow:** No changes to flow execution. Existing RFC #005 behavior unchanged.

## TRACE AND OBSERVABILITY GUARANTEES

The following AEL trace events are emitted during memory operations:

1. `memory_remember` — `key`, `value_summary`
2. `memory_recall` — `query_summary`, `result_count`, `top_keys`
3. `memory_forget` — `key`, `existed`
4. `store` — (existing event, unchanged)

Intentionally not recorded: full embeddings (too large), full values (only summaries), similarity scores.

## SECURITY AND SECRET HANDLING

No new secret handling introduced. Persistent agent memory:
- Uses existing mock embedder (no API keys)
- Memory files are user-controlled JSON (no secrets auto-written)
- Trace summaries are truncated to 50 characters
- No network access for memory operations

## TESTING STRATEGY

- [x] unit tests for `MemoryStore.remember` / `recall` / `forget`
- [x] unit tests for semantic similarity ordering
- [x] unit tests for memory persistence (save/load JSON with semantic entries)
- [x] end-to-end test: agent remembers, recalls, and forgets facts
- [x] trace emission tests (memory_remember, memory_recall, memory_forget)
- [x] existing tests remain passing (no regression)
- [x] no accidental network calls in compiler-core tests

## ROLLBACK PLAN

Persistent agent memory is additive:
1. Remove `remember`, `recall`, `forget` methods from `MemoryStore`
2. Remove `memory_remember`, `memory_recall`, `memory_forget` from `TraceEmitter`
3. Revert `MemoryStore.to_json()` / `from_json()` to exclude `_semantic` section
4. Parser, validator, formatter, codegen, and docs workflows unaffected — memory is runtime-only
5. Existing `memory.working` behavior continues unchanged

## ACCEPTANCE CRITERIA

- [x] RFC #009 document accepted.
- [x] `MemoryStore` supports `remember`, `recall`, `forget`.
- [x] Semantic memory persists via `--memory` and `--checkpoint`.
- [x] Trace events emitted for memory operations.
- [x] All existing tests pass (no regression).
- [x] CLI reference updated if new flags added.

## OPEN QUESTIONS

- **Deferred:** External vector DB integration (Pinecone, Weaviate, Qdrant), memory compression/summarization, memory access control, cross-agent shared memory, episodic vs procedural memory distinction.
- **Future RFC #010:** Agent lifecycle management — spawn, pause, resume, halt agents with state persistence.
