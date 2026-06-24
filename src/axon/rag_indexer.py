"""RAG indexer for AXON.

Reads source files, chunks them, embeds each chunk, and stores in a
VectorStore. Auto-indexes on first RAG dispatch if the store is empty.
"""

from __future__ import annotations

import glob
import time
from pathlib import Path
from typing import Any

from axon.ast_nodes import RagDecl
from axon.rag_chunker import sliding_window_chunks
from axon.rag_embedder import mock_embed
from axon.vector_store import VectorStore


def index_rag(
    rag: RagDecl,
    store: VectorStore,
    source_base: Path | None = None,
) -> dict[str, Any]:
    """Index a RAG declaration into the given VectorStore.

    Args:
        rag: The RagDecl to index.
        store: The VectorStore to populate.
        source_base: Base directory for resolving relative source paths.

    Returns:
        Dict with indexing statistics.
    """
    start_time = time.time()

    # Parse chunker settings from raw string (simple heuristic)
    chunk_size = 512
    chunk_overlap = 64
    if "size:" in rag.chunker:
        try:
            size_part = rag.chunker.split("size:")[1].split(",")[0].strip()
            chunk_size = int(size_part)
        except (ValueError, IndexError):
            pass
    if "overlap:" in rag.chunker:
        try:
            overlap_part = rag.chunker.split("overlap:")[1].split(")")[0].strip()
            chunk_overlap = int(overlap_part)
        except (ValueError, IndexError):
            pass

    # Resolve source glob
    source_pattern = rag.source.strip().strip('"').strip("'")
    if source_base is not None and not Path(source_pattern).is_absolute():
        source_pattern = str(source_base / source_pattern)

    files = glob.glob(source_pattern, recursive=True)
    files = [f for f in files if Path(f).is_file()]

    docs_indexed = 0
    chunks_indexed = 0

    for file_path in files:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if not text.strip():
            continue

        docs_indexed += 1
        chunks = sliding_window_chunks(
            text, size=chunk_size, overlap=chunk_overlap
        )

        for chunk_text, metadata in chunks:
            embedding = mock_embed(chunk_text, dimension=store.dimension)
            meta = dict(metadata)
            meta["source_file"] = file_path
            store.add(chunk_text, embedding, metadata=meta)
            chunks_indexed += 1

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "rag_name": rag.name,
        "source_pattern": source_pattern,
        "documents_indexed": docs_indexed,
        "chunks_indexed": chunks_indexed,
        "duration_ms": duration_ms,
    }
