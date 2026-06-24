"""In-memory vector store for AXON RAG.

Provides cosine-similarity search over document embeddings.
Real backends (Postgres/pgvector, Pinecone, Chroma, etc.) will replace this.
"""

from __future__ import annotations

import math
from typing import Any


class VectorStore:
    """Simple in-memory vector store with cosine similarity search.

    Documents are stored as (id, text, embedding) tuples.
    Embeddings are fixed-length float vectors.
    """

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension
        self._docs: list[dict[str, Any]] = []

    def add(self, text: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> int:
        """Add a document with its embedding vector.

        Returns the document index.
        """
        if len(embedding) != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}"
            )
        doc_id = len(self._docs)
        self._docs.append(
            {
                "id": doc_id,
                "text": text,
                "embedding": embedding,
                "metadata": metadata or {},
            }
        )
        return doc_id

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Search for the top-k most similar documents.

        Returns a list of result dicts with keys: id, text, score, metadata.
        """
        if len(query_embedding) != self.dimension:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {self.dimension}, got {len(query_embedding)}"
            )

        query_norm = _norm(query_embedding)
        if query_norm == 0:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for doc in self._docs:
            doc_emb = doc["embedding"]
            doc_norm = _norm(doc_emb)
            if doc_norm == 0:
                continue
            similarity = _dot(query_embedding, doc_emb) / (query_norm * doc_norm)
            scored.append((similarity, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, doc in scored[:top_k]:
            results.append(
                {
                    "id": doc["id"],
                    "text": doc["text"],
                    "score": round(score, 6),
                    "metadata": doc["metadata"],
                }
            )
        return results

    def count(self) -> int:
        """Return the number of documents in the store."""
        return len(self._docs)

    def clear(self) -> None:
        """Remove all documents."""
        self._docs = []


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))
