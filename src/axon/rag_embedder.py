"""Embedder module for AXON RAG.

Supports real embedding APIs (OpenAI, Ollama) and a deterministic mock
fallback. The embedder reference format is ``@provider/model``, e.g.:
  - ``@openai/text-embedding-3-small``
  - ``@ollama/nomic-embed-text``
  - ``@mock/embed`` (deterministic hash-based, no network)

When the requested provider's API key is not available or the SDK is not
installed, the module falls back to ``mock_embed`` so that RAG remains
functional in offline/test environments.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Optional


def mock_embed(text: str, dimension: int = 128) -> list[float]:
    """Create a deterministic mock embedding vector for text.

    Uses a simple hash-chain to produce dimension floats in [-1, 1].
    Identical text always produces identical vectors.
    """
    seed = hash(text) & 0xFFFFFFFF

    vector: list[float] = []
    state = seed
    for _ in range(dimension):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        value = (state / 0x3FFFFFFF) - 1.0
        vector.append(float(value))

    return vector


_OPENAI_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def _openai_embed(text: str, model: str) -> Optional[list[float]]:
    """Call OpenAI embeddings API. Returns None on failure."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    url = f"{base_url}/embeddings"

    payload = json.dumps({"input": text, "model": model}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return list(body["data"][0]["embedding"])
    except Exception:
        return None


def _ollama_embed(text: str, model: str) -> Optional[list[float]]:
    """Call Ollama embeddings API. Returns None on failure."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url}/api/embeddings"

    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return list(body["embedding"])
    except Exception:
        return None


def _sentence_transformers_embed(text: str, model_name: str) -> Optional[list[float]]:
    """Call SentenceTransformers local embedding. Returns None on failure."""
    try:
        from sentence_transformers import SentenceTransformer
        if not hasattr(_sentence_transformers_embed, '_models'):
            _sentence_transformers_embed._models = {}
        if model_name not in _sentence_transformers_embed._models:
            _sentence_transformers_embed._models[model_name] = SentenceTransformer(model_name)
        model = _sentence_transformers_embed._models[model_name]
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception:
        return None


_SENTENCE_TRANSFORMERS_DIMS: dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
    "bge-small-en-v1.5": 384,
    "bge-base-en-v1.5": 768,
    "nomic-embed-text-v1.5": 768,
}


def parse_embedder_ref(ref: str) -> tuple[str, str]:
    """Parse an embedder reference like ``@openai/text-embedding-3-small``.

    Returns ``(provider, model)``. Falls back to ``("mock", "embed")``.
    """
    ref = ref.strip()
    if ref.startswith("@"):
        ref = ref[1:]
    if "/" in ref:
        provider, model = ref.split("/", 1)
        return provider.strip(), model.strip()
    return "mock", "embed"


def get_embedder_dimension(ref: str) -> int:
    """Return the embedding dimension for a given embedder reference.

    For mock embedder, returns the default 128.
    For OpenAI models, returns the known dimension.
    For Ollama models, returns 768 as a common default (actual dimension
    varies by model and is auto-detected on first call).
    """
    provider, model = parse_embedder_ref(ref)
    if provider == "openai":
        return _OPENAI_DIMS.get(model, 1536)
    if provider == "ollama":
        return 768
    if provider in ("local", "sentence-transformers", "st"):
        return _SENTENCE_TRANSFORMERS_DIMS.get(model, 384)
    return 128


def create_embed_fn(ref: str):
    """Create an embed function based on an embedder reference string.

    The returned function has signature ``fn(text: str) -> list[float]``.
    It tries the real API first, falling back to ``mock_embed`` on any
    failure (no API key, network error, etc.).
    """
    provider, model = parse_embedder_ref(ref)

    if provider == "mock":
        return lambda text: mock_embed(text)

    if provider == "openai":
        def _embed(text: str) -> list[float]:
            result = _openai_embed(text, model)
            if result is not None:
                return result
            return mock_embed(text)
        return _embed

    if provider == "ollama":
        def _embed(text: str) -> list[float]:
            result = _ollama_embed(text, model)
            if result is not None:
                return result
            return mock_embed(text)
        return _embed

    if provider in ("local", "sentence-transformers", "st"):
        def _embed(text: str) -> list[float]:
            result = _sentence_transformers_embed(text, model)
            if result is not None:
                return result
            return mock_embed(text)
        return _embed

    # Unknown provider — fall back to mock
    return lambda text: mock_embed(text)
