"""Mock embedder for AXON RAG.

Produces deterministic fixed-dimension float vectors from text using
hash-based pseudo-random values. No API keys, no network calls.
"""

from __future__ import annotations

import struct


def mock_embed(text: str, dimension: int = 128) -> list[float]:
    """Create a deterministic mock embedding vector for text.

    Uses a simple hash-chain to produce dimension floats in [-1, 1].
    Identical text always produces identical vectors.
    """
    # Seed from the text hash
    seed = hash(text) & 0xFFFFFFFF

    vector: list[float] = []
    state = seed
    for _ in range(dimension):
        # Linear congruential generator step
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        # Normalise to [-1, 1]
        value = (state / 0x3FFFFFFF) - 1.0
        vector.append(float(value))

    return vector
