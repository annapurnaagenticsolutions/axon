"""Tests for AXON RAG indexing and retrieval runtime (RFC #006)."""

from pathlib import Path

from axon.cli import run_file
from axon.rag_chunker import sliding_window_chunks
from axon.rag_embedder import mock_embed
from axon.rag_indexer import index_rag
from axon.vector_store import VectorStore


def test_mock_embedder_deterministic():
    """Mock embedder returns identical vectors for identical text."""
    v1 = mock_embed("hello", dimension=64)
    v2 = mock_embed("hello", dimension=64)
    v3 = mock_embed("world", dimension=64)

    assert len(v1) == 64
    assert v1 == v2
    assert v1 != v3


def test_mock_embedder_dimension():
    """Mock embedder respects dimension parameter."""
    v = mock_embed("test", dimension=256)
    assert len(v) == 256


def test_chunker_splits_text():
    """Sliding window chunker splits text with overlap."""
    text = "a" * 200
    chunks = sliding_window_chunks(text, size=100, overlap=20)

    assert len(chunks) >= 2
    for chunk_text, meta in chunks:
        assert len(chunk_text) <= 100
        assert "chunk_index" in meta


def test_chunker_empty_text():
    """Chunker returns empty list for empty text."""
    assert sliding_window_chunks("") == []


def test_indexer_populates_store(tmp_path: Path):
    """Indexer reads files and populates VectorStore."""
    doc = tmp_path / "doc.md"
    doc.write_text("This is a test document about artificial intelligence.", encoding="utf-8")

    from axon.ast_nodes import RagDecl

    rag = RagDecl(
        name="TestRag",
        source=str(tmp_path / "*.md"),
        chunker="Chunker::sliding(size: 32, overlap: 8)",
        embedder="@mock/embed",
        store="VectorDB::memory",
    )
    store = VectorStore(dimension=128)
    stats = index_rag(rag, store, source_base=tmp_path)

    assert stats["documents_indexed"] == 1
    assert stats["chunks_indexed"] > 0
    assert store.count() > 0


def test_rag_retrieval_e2e(tmp_path: Path):
    """End-to-end: agent calls RAG retrieve and gets chunks back."""
    # Create a knowledge base file
    kb = tmp_path / "kb.md"
    kb.write_text(
        "The quick brown fox jumps over the lazy dog. "
        "Python is a programming language. "
        "Machine learning is a subset of artificial intelligence.",
        encoding="utf-8",
    )

    source = f'''rag KnowledgeBase {{
    source: "{kb.name}"
    chunker: Chunker::sliding(size: 64, overlap: 16)
    embedder: @mock/embed
    store: VectorDB::memory

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {{
        store.search(embed(query), top_k)
    }}
}}

agent Bot {{
    model: @mock/gpt
    tools: [KnowledgeBase.retrieve]
    fn run(q: Str) -> Str {{
        let results = act KnowledgeBase.retrieve(query: q, top_k: 3)?
        results[0].text
    }}
}}'''

    p = tmp_path / "rag_test.ax"
    p.write_text(source, encoding="utf-8")

    code, output = run_file(p, args={"q": "artificial intelligence"})
    assert code == 0
    assert output != ""


def test_rag_retrieval_trace_events(tmp_path: Path):
    """RAG retrieval emits trace events."""
    kb = tmp_path / "kb.md"
    kb.write_text("Hello world. This is a test document.", encoding="utf-8")

    source = f'''rag KB {{
    source: "{kb.name}"
    chunker: Chunker::sliding(size: 64, overlap: 16)
    embedder: @mock/embed
    store: VectorDB::memory

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {{
        store.search(embed(query), top_k)
    }}
}}

agent Bot {{
    model: @mock/gpt
    tools: [KB.retrieve]
    fn run(q: Str) -> Str {{
        let r = act KB.retrieve(query: q)?
        r[0].text
    }}
}}'''

    p = tmp_path / "rag_trace.ax"
    p.write_text(source, encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"

    code, output = run_file(p, args={"q": "hello"}, trace_output=trace_path)
    assert code == 0

    import json
    events = [json.loads(line) for line in trace_path.read_text().strip().split("\n")]
    event_types = [e["event_type"] for e in events]

    assert "rag_index_start" in event_types
    assert "rag_index_end" in event_types
    assert "rag_retrieve_start" in event_types
    assert "rag_retrieve_end" in event_types
