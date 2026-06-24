"""In-memory store for AXON agent memory.

This is a mock implementation for the executing runtime.
Real memory backends (vector DB, persistent store, etc.) will replace this.

Supports semantic memory via deterministic embeddings and cosine-similarity recall.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from axon.rag_embedder import mock_embed


class _MissingNoneDict(dict):
    """Dict that returns None for missing keys instead of raising KeyError."""

    def __getitem__(self, key: Any) -> Any:
        return self.get(key)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    norm_a = _norm(a)
    norm_b = _norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return _dot(a, b) / (norm_a * norm_b)


class MemoryStore:
    """Simple nested-dict memory store for AXON agents.

    Supports semantic memory via deterministic embeddings and cosine-similarity recall.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._semantic: list[dict[str, Any]] = []

    def set(self, section: str, key: str, value: Any) -> None:
        """Store a value in a memory section."""
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value

    def get(self, section: str, key: str) -> Any:
        """Retrieve a value from a memory section."""
        return self._data.get(section, {}).get(key)

    def get_section(self, section: str) -> dict[str, Any]:
        """Retrieve an entire memory section."""
        return dict(self._data.get(section, {}))

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to sections (memory.working[key])."""
        if name.startswith("_"):
            raise AttributeError(name)
        # Return bound methods for semantic memory operations
        if name in ("remember", "recall", "forget"):
            return getattr(self, name)
        return _MissingNoneDict(self._data.get(name, {}))

    # -- Semantic memory -------------------------------------------------

    def remember(self, key: str, value: Any) -> None:
        """Store a value with an embedding for later semantic recall."""
        text = str(value)
        embedding = mock_embed(text)
        # Remove existing entry with same key
        self._semantic = [e for e in self._semantic if e["key"] != key]
        self._semantic.append(
            {
                "key": key,
                "value": value,
                "embedding": embedding,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def recall(self, query: str, top_k: int = 5) -> list[Any]:
        """Search remembered values by semantic similarity to the query.

        Returns a list of the top-k most similar values.
        """
        if not self._semantic:
            return []
        query_embedding = mock_embed(query)
        scored: list[tuple[float, Any]] = []
        for entry in self._semantic:
            similarity = _cosine_similarity(query_embedding, entry["embedding"])
            scored.append((similarity, entry["value"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [value for _score, value in scored[:top_k]]

    def forget(self, key: str) -> bool:
        """Remove a remembered entry by key. Returns True if removed."""
        original_len = len(self._semantic)
        self._semantic = [e for e in self._semantic if e["key"] != key]
        return len(self._semantic) < original_len

    def list_semantic_keys(self) -> list[str]:
        """Return all semantic memory keys."""
        return [e["key"] for e in self._semantic]

    # -- Persistence -----------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a deep snapshot of all memory sections and semantic entries."""
        data = {k: dict(v) for k, v in self._data.items()}
        if self._semantic:
            data["__semantic__"] = {
                "entries": [
                    {
                        "key": e["key"],
                        "value": e["value"],
                        "embedding": e["embedding"],
                        "timestamp": e["timestamp"],
                    }
                    for e in self._semantic
                ]
            }
        return data

    def load(self, data: dict[str, Any]) -> None:
        """Load memory sections and semantic entries from a snapshot dict."""
        self._data = {}
        self._semantic = []
        for section, contents in data.items():
            if section == "__semantic__":
                semantic_data = contents if isinstance(contents, dict) else {}
                entries = semantic_data.get("entries", [])
                if isinstance(entries, list):
                    self._semantic = list(entries)
            elif isinstance(contents, dict):
                self._data[section] = dict(contents)

    def to_json(self) -> str:
        """Serialize memory to a JSON string."""
        import json

        return json.dumps(self.snapshot(), indent=2)

    def from_json(self, json_str: str) -> None:
        """Load memory from a JSON string."""
        import json

        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Memory JSON must be a dict")
        self.load(data)

    def save_to_file(self, path: Path) -> None:
        """Persist memory to a JSON file."""
        path.write_text(self.to_json(), encoding="utf-8")

    def load_from_file(self, path: Path) -> None:
        """Restore memory from a JSON file."""
        self.from_json(path.read_text(encoding="utf-8"))
