# AXON Runtime RFC #006 — RAG Indexing/Retrieval Runtime

**Status:** Accepted
**Created:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC documents the RAG (Retrieval-Augmented Generation) indexing and retrieval runtime that enables AXON agents to search indexed documents.

---

## SUMMARY

The RAG runtime provides document indexing, chunking, embedding, and vector search capabilities. It enables agents to retrieve relevant context from indexed document collections during execution.

## PROBLEM / MOTIVATION

AXON agents need to retrieve relevant documents to augment their context. The RAG system must:

1. Index documents from file paths or URLs
2. Chunk documents into searchable segments
3. Embed chunks using embedding models
4. Store embeddings in a vector store
5. Retrieve top-k relevant chunks for queries
6. Emit trace events for RAG operations

## CURRENT BOUNDARY CHECK

This RFC enables RAG operations during runtime execution, which is a Phase 2 capability.

- [x] RAG operations are behind the `axon run` CLI command
- [x] RAG indexing is optional (only when RAG declarations exist)
- [x] No network access during indexing (local files only)
- [x] Trace events are emitted for all RAG operations

## IMPLEMENTATION OVERVIEW

The RAG system is implemented across multiple modules:

### RAG Components

```python
# src/axon/rag_chunker.py
class Chunker:
    """Splits documents into chunks."""
    
    def chunk(self, text: str, size: int = 512, overlap: int = 64) -> list[str]

# src/axon/rag_embedder.py
class Embedder:
    """Generates embeddings for text chunks."""
    
    def embed(self, text: str) -> list[float]
    def embed_batch(self, texts: list[str]) -> list[list[float]]

# src/axon/rag_indexer.py
class Indexer:
    """Indexes documents for retrieval."""
    
    def index(self, source_path: Path) -> None
    def search(self, query: str, top_k: int = 5) -> list[Chunk]

# src/axon/rag_registry.py
class RagRegistry:
    """Registry for RAG collections."""
    
    def register(self, name: str, rag: RagDecl) -> None
    def dispatch(self, name: str, kwargs: dict, emitter: TraceEmitter) -> Result[Any, ToolError]
    def register_all(self, declarations: list) -> None
```

### Chunk Types

```python
@dataclass
class Chunk:
    id: str
    text: str
    source: str
    start_line: int
    end_line: int
    embedding: list[float] | None = None
```

## AXON SYNTAX EXECUTED

```axon
rag ProductDocs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}

agent SupportAgent {
    model: @anthropic/claude-4
    tools: [ProductDocs]

    fn run(query: Str) -> Result<Str, Error> {
        let chunks = act ProductDocs.retrieve(query: query, top_k: 3)?
        let context = chunks.map(|c| c.text).join("\n")
        Ok(context)
    }
}
```

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events:**

```python
class RagRetrieveEvent(TraceEvent):
    event_type: str = "rag_retrieve"
    rag_name: str
    query_summary: str
    top_k: int
    result_count: int
    chunk_ids: list[str]
```

## TESTING STRATEGY

- [x] Unit tests for Chunker
- [x] Unit tests for Embedder
- [x] Unit tests for Indexer
- [x] Integration tests with runtime executor
- [x] All tests pass (192 runtime tests)

## REFERENCES

- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Implementation: `src/axon/rag_chunker.py`, `src/axon/rag_embedder.py`, `src/axon/rag_indexer.py`, `src/axon/rag_registry.py`
- Tests: `tests/test_rag.py`, `tests/test_rag_execution.py`
