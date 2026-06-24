"""Text chunker for AXON RAG.

Splits source text into overlapping chunks using a sliding window.
"""

from __future__ import annotations

from typing import Any


def sliding_window_chunks(
    text: str,
    *,
    size: int = 512,
    overlap: int = 64,
) -> list[tuple[str, dict[str, Any]]]:
    """Split text into overlapping chunks.

    Args:
        text: Source text to chunk.
        size: Target chunk size in characters.
        overlap: Number of characters to overlap between chunks.

    Returns:
        List of (chunk_text, metadata) tuples.
    """
    if not text:
        return []

    if overlap >= size:
        overlap = size // 4

    step = size - overlap
    chunks: list[tuple[str, dict[str, Any]]] = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + size

        # Try not to split mid-word
        if end < len(text):
            # Look for a space or newline near the boundary
            search_start = max(start + step, end - 20)
            search_end = min(end + 20, len(text))
            boundary = text.rfind(" ", search_start, search_end)
            if boundary == -1:
                boundary = text.rfind("\n", search_start, search_end)
            if boundary != -1:
                end = boundary

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                (
                    chunk_text,
                    {
                        "chunk_index": idx,
                        "char_start": start,
                        "char_end": end,
                    },
                )
            )
            idx += 1

        start = end
        if start >= len(text):
            break
        # Move back for overlap
        start = max(start - overlap, start + 1)

    return chunks
