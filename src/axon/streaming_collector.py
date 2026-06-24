"""Streaming output collector for AXON runtime.

Buffers response chunks from a streaming provider call and optionally
emits trace events for real-time observability.
"""

from __future__ import annotations

import threading
from typing import Any

from axon.trace_emitter import TraceEmitter


class StreamingCollector:
    """Buffers streaming chunks and provides formatted output.

    Thread-safe for use from background agent threads.
    """

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        self._chunks: list[str] = []
        self._emitter = emitter
        self._lock = threading.Lock()
        self._started = False
        self._finished = False
        self._result_type = "ok"

    def start(self, method_name: str = "", model_reference: str = "", prompt_summary: str = "") -> None:
        """Signal the start of a stream."""
        with self._lock:
            self._started = True
        if self._emitter is not None:
            self._emitter.model_stream_start(
                method_name=method_name,
                model_reference=model_reference,
                prompt_summary=prompt_summary,
            )

    def collect(self, chunk: str) -> None:
        """Buffer a chunk and optionally emit a trace event."""
        with self._lock:
            self._chunks.append(chunk)
        if self._emitter is not None:
            self._emitter.model_stream_chunk(
                method_name="run",
                chunk_summary=chunk[:50],
            )

    def finish(self, result_type: str = "ok", result_summary: str = "") -> None:
        """Signal the end of a stream."""
        with self._lock:
            self._finished = True
            self._result_type = result_type
        if self._emitter is not None:
            self._emitter.model_stream_end(
                method_name="run",
                result_type=result_type,
                result_summary=result_summary,
            )

    def to_text(self) -> str:
        """Return the concatenated output of all chunks."""
        with self._lock:
            return "".join(self._chunks)

    def to_list(self) -> list[str]:
        """Return a copy of the chunk list."""
        with self._lock:
            return list(self._chunks)

    def is_started(self) -> bool:
        with self._lock:
            return self._started

    def is_finished(self) -> bool:
        with self._lock:
            return self._finished

    def to_dict(self) -> dict[str, Any]:
        """Return a snapshot for serialization."""
        with self._lock:
            return {
                "started": self._started,
                "finished": self._finished,
                "result_type": self._result_type,
                "chunk_count": len(self._chunks),
                "output": "".join(self._chunks),
            }
