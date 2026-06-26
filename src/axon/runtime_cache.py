"""Prompt and tool result caching for AXON runtime.

Provides disk-backed and in-memory caching for:
- Model/prompt calls (think, model.complete) keyed on (prompt, model, temperature)
- Tool dispatch results keyed on (tool_name, sorted_args)

Caching is opt-in via RuntimeConfig.cache_enabled (default: True when not
streaming or replaying). The --no-cache CLI flag disables caching entirely.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _stable_hash(*parts: Any) -> str:
    """Produce a stable SHA-256 hex digest from arbitrary serializable parts."""
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, str):
            h.update(part.encode("utf-8"))
        else:
            h.update(json.dumps(part, sort_keys=True, default=str).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


@dataclass
class CacheEntry:
    """A single cache entry with optional TTL."""
    value: Any
    created_at: float
    ttl_seconds: Optional[float] = None

    def is_expired(self, now: float) -> bool:
        if self.ttl_seconds is None:
            return False
        return (now - self.created_at) > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        return cls(
            value=data["value"],
            created_at=data["created_at"],
            ttl_seconds=data.get("ttl_seconds"),
        )


class Cache:
    """In-memory + optional disk-backed cache.

    When ``cache_dir`` is set, entries are persisted to disk as JSON files
    named by their hash. When ``cache_dir`` is None, only in-memory storage
    is used.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        default_ttl: Optional[float] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.default_ttl = default_ttl
        self._memory: dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _disk_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[Any]:
        """Look up a cached value by key. Returns None on miss or expiry."""
        now = time.time()

        # Check memory first
        entry = self._memory.get(key)
        if entry is not None and not entry.is_expired(now):
            self.hits += 1
            return entry.value
        elif entry is not None and entry.is_expired(now):
            del self._memory[key]

        # Check disk
        if self.cache_dir is not None:
            disk_path = self._disk_path(key)
            if disk_path.exists():
                try:
                    data = json.loads(disk_path.read_text(encoding="utf-8"))
                    entry = CacheEntry.from_dict(data)
                    if not entry.is_expired(now):
                        self._memory[key] = entry
                        self.hits += 1
                        return entry.value
                    else:
                        disk_path.unlink(missing_ok=True)
                except (OSError, json.JSONDecodeError, KeyError):
                    pass

        self.misses += 1
        return None

    def put(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Store a value in the cache."""
        effective_ttl = ttl if ttl is not None else self.default_ttl
        entry = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl_seconds=effective_ttl,
        )
        self._memory[key] = entry

        if self.cache_dir is not None:
            try:
                self._disk_path(key).write_text(
                    json.dumps(entry.to_dict(), default=str),
                    encoding="utf-8",
                )
            except OSError:
                pass

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._memory.pop(key, None)
        if self.cache_dir is not None:
            self._disk_path(key).unlink(missing_ok=True)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._memory.clear()
        if self.cache_dir is not None:
            for f in self.cache_dir.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    pass

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._memory),
        }


class PromptCache:
    """Cache for model/prompt call results.

    Keys on (prompt_text, model, temperature) to avoid redundant LLM calls.
    """

    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    def _key(self, prompt: str, model: str, temperature: float) -> str:
        return _stable_hash("prompt", prompt, model, temperature)

    def get(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
    ) -> Optional[Any]:
        return self._cache.get(self._key(prompt, model, temperature))

    def put(
        self,
        prompt: str,
        model: str,
        temperature: float,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        self._cache.put(self._key(prompt, model, temperature), value, ttl=ttl)


class ToolResultCache:
    """Cache for tool dispatch results.

    Keys on (tool_name, sorted_args) to avoid redundant tool executions.
    """

    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    def _key(self, tool_name: str, kwargs: dict[str, Any]) -> str:
        sorted_args = json.dumps(kwargs, sort_keys=True, default=str)
        return _stable_hash("tool", tool_name, sorted_args)

    def get(self, tool_name: str, kwargs: dict[str, Any]) -> Optional[Any]:
        return self._cache.get(self._key(tool_name, kwargs))

    def put(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        self._cache.put(self._key(tool_name, kwargs), value, ttl=ttl)
