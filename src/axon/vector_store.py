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


class ChromaVectorStore:
    """ChromaDB-backed vector store. Falls back to in-memory VectorStore if chromadb not installed."""

    def __init__(self, dimension: int = 128, collection_name: str = "axon_rag", persist_path: str | None = None) -> None:
        self.dimension = dimension
        self._fallback: VectorStore | None = None
        self._collection = None
        try:
            import chromadb
            client = chromadb.PersistentClient(path=persist_path or ".axon_chroma") if persist_path else chromadb.Client()
            self._collection = client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        except Exception:
            self._fallback = VectorStore(dimension=dimension)

    def add(self, text: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> int:
        if self._fallback is not None:
            return self._fallback.add(text, embedding, metadata)
        doc_id = str(self.count())
        self._collection.add(ids=[doc_id], documents=[text], embeddings=[embedding], metadatas=[metadata or {}])
        return int(doc_id)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if self._fallback is not None:
            return self._fallback.search(query_embedding, top_k)
        results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        out = []
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            out.append({
                "id": int(results["ids"][0][i]),
                "text": doc,
                "score": 1.0 - results["distances"][0][i] if "distances" in results else 0.0,
                "metadata": results.get("metadatas", [{}])[0][i] if "metadatas" in results else {},
            })
        return out

    def count(self) -> int:
        if self._fallback is not None:
            return self._fallback.count()
        return self._collection.count()

    def clear(self) -> None:
        if self._fallback is not None:
            self._fallback.clear()
            return
        self._collection.delete(ids=self._collection.get()["ids"])


class PgVectorStore:
    """PostgreSQL pgvector-backed store. Falls back to in-memory if psycopg2/pgvector not available."""

    def __init__(self, dimension: int = 128, dsn: str = "", table_name: str = "axon_vectors") -> None:
        self.dimension = dimension
        self._fallback: VectorStore | None = None
        self._conn = None
        self._table = table_name
        try:
            import psycopg2
            self._conn = psycopg2.connect(dsn)
            self._conn.autocommit = True
            with self._conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, text TEXT, embedding vector({dimension}), metadata JSONB DEFAULT '{{}}')")
        except Exception:
            self._fallback = VectorStore(dimension=dimension)

    def add(self, text: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> int:
        if self._fallback is not None:
            return self._fallback.add(text, embedding, metadata)
        import json
        with self._conn.cursor() as cur:
            cur.execute(f"INSERT INTO {self._table} (text, embedding, metadata) VALUES (%s, %s, %s) RETURNING id", (text, str(embedding), json.dumps(metadata or {})))
            return cur.fetchone()[0]

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if self._fallback is not None:
            return self._fallback.search(query_embedding, top_k)
        import json
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT id, text, metadata, 1 - (embedding <=> %s) AS score FROM {self._table} ORDER BY embedding <=> %s LIMIT %s", (str(query_embedding), str(query_embedding), top_k))
            rows = cur.fetchall()
        return [{"id": r[0], "text": r[1], "metadata": r[2] if isinstance(r[2], dict) else json.loads(r[2] or "{}"), "score": round(float(r[3]), 6)} for r in rows]

    def count(self) -> int:
        if self._fallback is not None:
            return self._fallback.count()
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            return cur.fetchone()[0]

    def clear(self) -> None:
        if self._fallback is not None:
            self._fallback.clear()
            return
        with self._conn.cursor() as cur:
            cur.execute(f"TRUNCATE {self._table}")


def create_store(ref: str, dimension: int = 128, **kwargs) -> VectorStore | ChromaVectorStore | PgVectorStore:
    """Create a vector store based on a reference string.

    Supported refs:
      - ``memory`` or ``mock`` → in-memory VectorStore
      - ``chroma`` or ``chroma:path`` → ChromaVectorStore
      - ``pgvector`` or ``pgvector:dsn`` → PgVectorStore
    """
    ref = ref.strip().lower()
    if ref.startswith("chroma"):
        parts = ref.split(":", 1)
        path = parts[1] if len(parts) > 1 else None
        return ChromaVectorStore(dimension=dimension, persist_path=path, **kwargs)
    if ref.startswith("pgvector"):
        parts = ref.split(":", 1)
        dsn = parts[1] if len(parts) > 1 else ""
        return PgVectorStore(dimension=dimension, dsn=dsn, **kwargs)
    return VectorStore(dimension=dimension)
