# AXON Runtime RFC #006 — RAG Indexing and Retrieval Runtime

**Status:** Draft
**Created:** 2026-06-09
**Owner:** axon-dev

> Runtime work must be proposed before implementation. This template is intentionally strict because runtime behavior can call providers, dispatch tools, mutate memory, index RAG data, execute flows, or replay traces.

---

## SUMMARY

Propose a minimal RAG (Retrieval-Augmented Generation) indexing and retrieval runtime for AXON. This enables `rag` declarations to be populated with document embeddings and queried at runtime. A mock embedder produces deterministic vectors without API keys; a simple sliding-window chunker splits source text; and `store.search(embed(query), top_k)` executes inside RAG method bodies.

The intended output is a working `axon run examples/rag.ax --arg question="How do I reset my password?"` where:
1. `ProductDocs` RAG is auto-indexed from source files
2. `act ProductDocs.retrieve(query: question)` returns matching chunks
3. The agent uses those chunks in its response generation

This RFC keeps the scope intentionally narrow: in-memory vector store only, mock embeddings, no real vector DBs or reranking.

## PROBLEM / MOTIVATION

AXON already parses `rag` declarations with `source`, `chunker`, `embedder`, and `store` fields, and the `RagRegistry` can dispatch `act ProductDocs.retrieve(...)` calls. But the vector store is always empty — no indexing happens at runtime. Without indexing, every RAG retrieval returns zero results, making RAG declarations non-functional.

The `examples/rag.ax` file in the example corpus declares a `ProductDocs` RAG with a `retrieve()` method. This example should return relevant chunks when queried, not an empty list. RAG indexing is the natural next step after flow execution (RFC #005): it adds persistent document storage and similarity search to the runtime.

This RFC keeps the scope narrow: mock-only embeddings, in-memory store, simple text chunking. No real embedder APIs, no external vector databases, no reranking.

## CURRENT BOUNDARY CHECK

Confirm the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md` and state exactly what this RFC proposes to change.

Required confirmations:

- [x] This RFC explicitly permits executing RAG method bodies and indexing documents.
- [x] This RFC uses existing mock tool dispatch and agent delegation from RFC #004.
- [x] Do not call real model providers for embeddings — mock embedder only.
- [x] Do not resolve, print, or snapshot API keys.
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary.
- [x] Deterministic test doubles (mock embedder, in-memory vector store) defined.
- [x] Document exactly which AXON syntax subset the runtime will execute — listed below.
- [x] Trace emission guarantees defined below.

## PROPOSED RUNTIME SCOPE

Add a minimal RAG indexing and retrieval runtime that:

1. **Mock embedder** (`src/axon/rag_embedder.py`)
   - Deterministic text-to-vector function using hash-based embeddings
   - No API keys, no network calls, no provider SDKs
   - Produces fixed-dimension float vectors for any input string

2. **Text chunker** (`src/axon/rag_chunker.py`)
   - Sliding-window chunker: split text into chunks of N characters with overlap
   - Simple word-boundary awareness (don't split mid-word when possible)
   - Returns list of `(text, metadata)` tuples

3. **RAG indexer** (`src/axon/rag_indexer.py`)
   - Read source files from `rag.source` glob patterns
   - Chunk each file's text
   - Embed each chunk with the mock embedder
   - Store `(embedding, text, metadata)` in the `VectorStore`
   - Auto-index on first RAG dispatch if the store is empty

4. **RAG method evaluation enhancements**
   - Inject `embed` function into RAG method evaluation scope
   - `store.search(embed(query), top_k)` works via existing `VectorStore.search()`
   - Return `List<Chunk>` from RAG methods (list of dicts with `text`, `score`, `metadata`)

5. **CLI integration**
   - `axon run <file.ax> --arg question="..."` works with RAG-enabled agents
   - No new CLI flags needed — indexing is automatic

## NON-GOALS

- Do not implement unrelated runtime subsystems.
- Do not broaden provider/tool/memory behavior beyond this RFC.

## AXON SYNTAX EXECUTED

This RFC executes the following AXON constructs inside RAG declarations:

```axon
// RAG declaration (parsed, partially executed)
rag ProductDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3   // parsed but ignored; mock embedder used
    store: VectorDB::postgres(...)   // parsed but ignored; in-memory store used

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}

// Agent using RAG (existing RFC #004 behavior)
agent SupportAgent {
    model: @mock/gpt
    tools: [ProductDocs.retrieve]
    fn handle(question: Str) -> Result<Str, AgentError> {
        let context = act ProductDocs.retrieve(query: question)?
        Ok(context[0].text)
    }
}
```

Specifically:
- `rag` declarations with `source`, `chunker`, `embedder`, `store` fields
- `fn retrieve(...)` method bodies inside `rag` blocks
- `store.search(embed(query), top_k)` expression evaluation
- `act ProductDocs.retrieve(...)` dispatch (existing behavior)
- All existing expression syntax inside tool/agent bodies (from RFC #004)

## PROVIDER PLUGIN IMPACT

No changes to the provider plugin protocol. RAG indexing uses a mock embedder that never calls providers. The RAG `embedder` field (e.g., `@openai/text-embed-3`) is parsed but ignored at runtime — the mock embedder is always used.

- Mock embedder: deterministic hash-based vectors, no API keys
- Real embedders: deferred to future RFC
- No timeout or cost tracking in this RFC

## TOOL DISPATCH IMPACT

RAG retrieval is dispatched through the existing `RagRegistry.dispatch()` mechanism (already in place). This RFC only adds:

- Auto-indexing before first dispatch (if store is empty)
- `embed()` function injection into RAG method scope
- No changes to tool dispatch boundaries or permissions

## MEMORY / RAG / FLOW IMPACT

- **RAG indexes: EXECUTED** — This is the primary change of this RFC.
- **Memory:** No new memory behavior. Existing RFC #004 behavior unchanged.
- **Flow:** No changes to flow execution. Existing RFC #005 behavior unchanged.

## TRACE AND OBSERVABILITY GUARANTEES

The following AEL trace events are emitted during RAG operations:

1. `rag_index_start` — `rag_name`, `source_pattern`
2. `rag_index_end` — `rag_name`, `documents_indexed`, `chunks_indexed`, `duration_ms`
3. `rag_retrieve_start` — `rag_name`, `method_name`, `query` (redacted)
4. `rag_retrieve_end` — `rag_name`, `method_name`, `result_count`, `duration_ms`

Existing trace events (tool_dispatch, tool_return) are also emitted when `act ProductDocs.retrieve(...)` is dispatched.

Intentionally not recorded: full document text, embedding vectors, raw chunk content.

## SECURITY AND SECRET HANDLING

No new secret handling introduced by this RFC. RAG indexing:
- Uses mock embedder (no API keys)
- Reads local files only (no network access)
- Redacts query text in trace events
- Never snapshots embedding vectors in traces

## TESTING STRATEGY

- [x] unit tests for mock embedder (deterministic output, dimension correctness)
- [x] unit tests for text chunker (chunk size, overlap, word boundaries)
- [x] unit tests for RAG indexer (glob reading, chunking, embedding, storing)
- [x] unit tests for RAG retrieval (empty store, indexed store, top-k results)
- [x] trace emission tests (rag_index_start, rag_index_end, rag_retrieve_start, rag_retrieve_end)
- [x] end-to-end test: agent calls `act ProductDocs.retrieve(query: ...)` and gets chunks back
- [x] existing tests remain passing (no regression)
- [x] no accidental network calls in compiler-core tests

## ROLLBACK PLAN

RAG indexing is additive:
1. Delete `src/axon/rag_embedder.py`, `src/axon/rag_chunker.py`, `src/axon/rag_indexer.py` to remove indexing
2. Remove `embed` injection from `RagRegistry.dispatch()`
3. Remove trace event methods from `TraceEmitter`
4. Parser, validator, formatter, codegen, and docs workflows are unaffected — they already parse `rag` declarations statically
5. `act ProductDocs.retrieve(...)` continues to dispatch but returns empty results (pre-RFC #006 behavior)

## ACCEPTANCE CRITERIA

- [x] RFC #006 document accepted.
- [x] Mock embedder produces deterministic vectors for any text input.
- [x] Text chunker splits source documents with configurable size and overlap.
- [x] RAG indexer reads source files, chunks, embeds, and stores them in VectorStore.
- [x] Auto-indexing happens on first RAG dispatch when store is empty.
- [x] `store.search(embed(query), top_k)` evaluates correctly inside RAG methods.
- [x] RAG retrieval returns `List<Chunk>` with `text`, `score`, and `metadata`.
- [x] Trace events emitted for RAG indexing and retrieval.
- [x] All existing tests pass (no regression).
- [x] End-to-end test: agent with RAG tool returns non-empty chunk list.

## OPEN QUESTIONS

- **Deferred:** Real embedder APIs (OpenAI, Cohere), external vector databases (Postgres/pgvector, Pinecone), reranking, pipe operator `|>`, lambda/filter expressions in RAG bodies.
- **Future RFC #007:** Trace replay — deterministic replay of emitted AEL traces as actions.
