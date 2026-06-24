"""Trace replay runtime for AXON.

Reads an AEL trace JSONL file and replays recorded tool dispatches,
model calls, and RAG retrievals as deterministic mock responses.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from result import Result, Ok, Err


class TraceReplayer:
    """Replayer that reads a trace JSONL and returns recorded results."""

    def __init__(self, trace_path: Path) -> None:
        self.trace_path = trace_path
        self.events: list[dict[str, Any]] = []
        self._tool_events: deque[dict[str, Any]] = deque()
        self._model_events: deque[dict[str, Any]] = deque()
        self._rag_events: deque[dict[str, Any]] = deque()
        self._delegate_events: deque[dict[str, Any]] = deque()

        self._load_trace()

    def _load_trace(self) -> None:
        text = self.trace_path.read_text(encoding="utf-8")
        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            event = json.loads(line)
            self.events.append(event)
            if event.get("event_type") == "tool_return":
                self._tool_events.append(event)
            elif event.get("event_type") == "model_return":
                self._model_events.append(event)
            elif event.get("event_type") == "rag_retrieve_end":
                self._rag_events.append(event)
            elif event.get("event_type") == "delegate_return":
                self._delegate_events.append(event)

    # ------------------------------------------------------------------
    # Replay helpers
    # ------------------------------------------------------------------

    def _next_tool_result(self, tool_name: str) -> Result[Any, str]:
        """Return the next recorded tool result for *tool_name*."""
        for i, ev in enumerate(self._tool_events):
            # The preceding tool_dispatch event carries the tool_name
            dispatch_ev = self._find_preceding_dispatch(ev, "tool_dispatch")
            if dispatch_ev and dispatch_ev.get("tool_name") == tool_name:
                # Remove this and any skipped events up to it
                for _ in range(i + 1):
                    self._tool_events.popleft()
                return self._extract_result(ev)
        return Err(
            f"Replay mismatch: no recorded tool_return for '{tool_name}' "
            f"(remaining events: {len(self._tool_events)})"
        )

    def _next_model_result(self) -> Result[Any, str]:
        """Return the next recorded model result."""
        if not self._model_events:
            return Err("Replay mismatch: no recorded model_return events remaining")
        ev = self._model_events.popleft()
        return self._extract_result(ev)

    def _next_rag_result(self, rag_name: str, method_name: str) -> Result[Any, str]:
        """Return the next recorded RAG retrieval result."""
        for i, ev in enumerate(self._rag_events):
            if ev.get("rag_name") == rag_name and ev.get("method_name") == method_name:
                for _ in range(i + 1):
                    self._rag_events.popleft()
                return self._extract_result(ev)
        return Err(
            f"Replay mismatch: no recorded rag_retrieve_end for "
            f"'{rag_name}.{method_name}'"
        )

    def _next_delegate_result(self, agent_name: str) -> Result[Any, str]:
        """Return the next recorded delegate result."""
        for i, ev in enumerate(self._delegate_events):
            if ev.get("agent_name") == agent_name:
                for _ in range(i + 1):
                    self._delegate_events.popleft()
                return self._extract_result(ev)
        return Err(
            f"Replay mismatch: no recorded delegate_return for '{agent_name}'"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_preceding_dispatch(
        self, return_event: dict[str, Any], dispatch_type: str
    ) -> dict[str, Any] | None:
        """Find the dispatch event that immediately precedes a return event."""
        return_idx = self.events.index(return_event)
        for i in range(return_idx - 1, -1, -1):
            ev = self.events[i]
            if ev.get("event_type") == dispatch_type:
                return ev
        return None

    @staticmethod
    def _extract_result(event: dict[str, Any]) -> Result[Any, str]:
        """Turn a trace return event back into a runtime result."""
        result_type = event.get("result_type", "ok")
        summary = event.get("result_summary", "")
        if result_type == "error":
            return Err(summary)
        # For short strings the summary IS the full value
        if summary.startswith("<") and "len=" in summary:
            # Synthesise a list of placeholder strings for list summaries
            try:
                count = int(summary.split("len=")[1].rstrip(">"))
                return Ok([{"text": f"chunk_{i}"} for i in range(count)])
            except (ValueError, IndexError):
                pass
        return Ok(summary)

    # ------------------------------------------------------------------
    # Public interceptors (used by RuntimeExecutor)
    # ------------------------------------------------------------------

    def replay_tool_dispatch(self, name: str, kwargs: dict[str, Any]) -> Result[Any, str]:
        """Interceptor for tool dispatch during replay."""
        return self._next_tool_result(name)

    def replay_model_call(self, prompt: str) -> Result[Any, str]:
        """Interceptor for model calls during replay."""
        return self._next_model_result()

    def replay_rag_dispatch(self, name: str, kwargs: dict[str, Any]) -> Result[Any, str]:
        """Interceptor for RAG dispatch during replay."""
        if "." not in name:
            return Err(f"Invalid RAG method name: {name}")
        rag_name, method_name = name.split(".", 1)
        return self._next_rag_result(rag_name, method_name)

    def replay_delegate(self, name: str, kwargs: dict[str, Any]) -> Result[Any, str]:
        """Interceptor for delegate calls during replay."""
        return self._next_delegate_result(name)
