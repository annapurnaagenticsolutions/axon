"""Trace emitter for AXON runtime execution.

Emits AEL trace events during agent execution as JSONL records.
These events model the runtime flow: agent start/end, method
entry/exit, and tool dispatch/return.

This module intentionally does not execute code — it only records
events produced by the runtime executor.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from axon.trace_context import get_current_trace


@dataclass
class TraceEmitter:
    """Collects and serialises AEL runtime trace events."""

    agent_name: str = ""
    source_file: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    _start_time: float = field(default_factory=time.time)

    # Redaction patterns for sensitive values in trace args
    _SECRET_PATTERNS: tuple[str, ...] = (
        "api_key",
        "secret",
        "token",
        "password",
        "auth",
    )

    def _append_event(self, event_type: str, **kwargs: Any) -> None:
        """Append an event with trace context automatically injected."""
        ctx = get_current_trace()
        event: dict[str, Any] = {"event_type": event_type, "timestamp": self._iso_now()}
        if ctx is not None:
            event["trace_id"] = ctx.trace_id
            event["span_id"] = ctx.span_id
            if ctx.parent_span_id is not None:
                event["parent_span_id"] = ctx.parent_span_id
        event.update(kwargs)
        self.events.append(event)

    def replay_start(self, *, trace_file: str, source_file: str) -> None:
        """Record the start of a trace replay."""
        self.events.append(
            {
                "event_type": "replay_start",
                "trace_file": trace_file,
                "source_file": source_file,
                "timestamp": self._iso_now(),
            }
        )

    def replay_end(self, *, result_type: str, result_summary: str, duration_ms: int = 0) -> None:
        """Record the end of a trace replay."""
        self.events.append(
            {
                "event_type": "replay_end",
                "result_type": result_type,
                "result_summary": result_summary,
                "duration_ms": duration_ms,
                "timestamp": self._iso_now(),
            }
        )

    def message_sent(self, *, from_agent: str, to_agent: str, message_summary: str = "") -> None:
        """Record a message sent between agents."""
        self._append_event(
            "message_sent",
            from_agent=from_agent,
            to_agent=to_agent,
            message_summary=message_summary[:50],
        )

    def message_received(self, *, agent_name: str, message_summary: str = "") -> None:
        """Record a message received by an agent."""
        self.events.append(
            {
                "event_type": "message_received",
                "agent_name": agent_name,
                "message_summary": message_summary[:50],
                "timestamp": self._iso_now(),
            }
        )

    def memory_remember(self, *, key: str, value_summary: str = "") -> None:
        """Record a semantic memory remember operation."""
        self.events.append(
            {
                "event_type": "memory_remember",
                "key": key,
                "value_summary": value_summary[:50],
                "timestamp": self._iso_now(),
            }
        )

    def memory_recall(self, *, query_summary: str = "", result_count: int = 0, top_keys: list[str] | None = None) -> None:
        """Record a semantic memory recall operation."""
        self.events.append(
            {
                "event_type": "memory_recall",
                "query_summary": query_summary[:50],
                "result_count": result_count,
                "top_keys": top_keys or [],
                "timestamp": self._iso_now(),
            }
        )

    def memory_forget(self, *, key: str, existed: bool = False) -> None:
        """Record a semantic memory forget operation."""
        self.events.append(
            {
                "event_type": "memory_forget",
                "key": key,
                "existed": existed,
                "timestamp": self._iso_now(),
            }
        )

    def agent_start(self, *, agent_name: str, source_file: str) -> None:
        """Record the beginning of agent execution."""
        self.agent_name = agent_name
        self.source_file = source_file
        self._start_time = time.time()
        self._append_event(
            "agent_start",
            agent_name=agent_name,
            source_file=source_file,
        )

    def method_start(
        self,
        *,
        method_name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record entry into an agent method."""
        self._append_event(
            "method_start",
            agent_name=self.agent_name,
            method_name=method_name,
            arguments=self._redact_args(arguments or {}),
        )

    def tool_dispatch(
        self,
        *,
        method_name: str,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a tool call being dispatched."""
        self._append_event(
            "tool_dispatch",
            agent_name=self.agent_name,
            method_name=method_name,
            tool_name=tool_name,
            arguments=self._redact_args(arguments or {}),
        )

    def tool_return(
        self,
        *,
        method_name: str,
        tool_name: str,
        result_type: str,
        result_summary: str,
    ) -> None:
        """Record a tool call returning a value or error."""
        self.events.append(
            {
                "event_type": "tool_return",
                "agent_name": self.agent_name,
                "method_name": method_name,
                "tool_name": tool_name,
                "result_type": result_type,
                "result_summary": result_summary,
                "timestamp": self._iso_now(),
            }
        )

    def model_call(
        self,
        *,
        method_name: str,
        model_reference: str,
        prompt_summary: str,
    ) -> None:
        """Record a model completion call."""
        self._append_event(
            "model_call",
            agent_name=self.agent_name,
            method_name=method_name,
            model_reference=model_reference,
            prompt_summary=prompt_summary,
        )

    def model_return(
        self,
        *,
        method_name: str,
        result_type: str,
        result_summary: str,
    ) -> None:
        """Record a model completion returning a value or error."""
        self.events.append(
            {
                "event_type": "model_return",
                "agent_name": self.agent_name,
                "method_name": method_name,
                "result_type": result_type,
                "result_summary": result_summary,
                "timestamp": self._iso_now(),
            }
        )

    def model_stream_start(
        self,
        *,
        method_name: str,
        model_reference: str,
        prompt_summary: str,
    ) -> None:
        """Record the start of a streaming model call."""
        self.events.append(
            {
                "event_type": "model_stream_start",
                "agent_name": self.agent_name,
                "method_name": method_name,
                "model_reference": model_reference,
                "prompt_summary": prompt_summary,
                "timestamp": self._iso_now(),
            }
        )

    def model_stream_chunk(
        self,
        *,
        method_name: str,
        chunk_summary: str,
    ) -> None:
        """Record a chunk from a streaming model call."""
        self.events.append(
            {
                "event_type": "model_stream_chunk",
                "agent_name": self.agent_name,
                "method_name": method_name,
                "chunk_summary": chunk_summary,
                "timestamp": self._iso_now(),
            }
        )

    def model_stream_end(
        self,
        *,
        method_name: str,
        result_type: str,
        result_summary: str,
    ) -> None:
        """Record the end of a streaming model call."""
        self.events.append(
            {
                "event_type": "model_stream_end",
                "agent_name": self.agent_name,
                "method_name": method_name,
                "result_type": result_type,
                "result_summary": result_summary,
                "timestamp": self._iso_now(),
            }
        )

    def delegate_call(
        self,
        *,
        method_name: str,
        agent_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Record an agent delegation call."""
        self._append_event(
            "delegate_call",
            caller_agent=self.agent_name,
            agent_name=agent_name,
            method_name=method_name,
            arguments=self._redact_args(arguments),
        )

    def delegate_return(
        self,
        *,
        method_name: str,
        agent_name: str,
        result_type: str,
        result_summary: str,
    ) -> None:
        """Record an agent delegation returning a value or error."""
        self.events.append(
            {
                "event_type": "delegate_return",
                "caller_agent": self.agent_name,
                "agent_name": agent_name,
                "method_name": method_name,
                "result_type": result_type,
                "result_summary": result_summary,
                "timestamp": self._iso_now(),
            }
        )

    def method_return(
        self,
        *,
        method_name: str,
        result_type: str,
        result_summary: str,
    ) -> None:
        """Record a method returning a value or error."""
        self.events.append(
            {
                "event_type": "method_return",
                "agent_name": self.agent_name,
                "method_name": method_name,
                "result_type": result_type,
                "result_summary": result_summary,
                "timestamp": self._iso_now(),
            }
        )

    def flow_start(self, *, flow_name: str, args: dict[str, Any]) -> None:
        """Record the start of a flow execution."""
        self.events.append(
            {
                "event_type": "flow_start",
                "flow_name": flow_name,
                "args": {k: self._redact_value("", v) for k, v in args.items()},
                "timestamp": self._iso_now(),
            }
        )

    def flow_end(self, *, result_type: str, result_summary: str, duration_ms: int = 0) -> None:
        """Record the end of a flow execution."""
        self.events.append(
            {
                "event_type": "flow_end",
                "result_type": result_type,
                "result_summary": result_summary,
                "duration_ms": duration_ms,
                "timestamp": self._iso_now(),
            }
        )

    def stage_start(self, *, stage_name: str, input_keys: list[str]) -> None:
        """Record the start of a flow stage."""
        self.events.append(
            {
                "event_type": "stage_start",
                "stage_name": stage_name,
                "input_keys": input_keys,
                "timestamp": self._iso_now(),
            }
        )

    def stage_end(self, *, stage_name: str, result_type: str, result_summary: str) -> None:
        """Record the end of a flow stage."""
        self.events.append(
            {
                "event_type": "stage_end",
                "stage_name": stage_name,
                "result_type": result_type,
                "result_summary": result_summary,
                "timestamp": self._iso_now(),
            }
        )

    def rag_index_start(self, *, rag_name: str, source_pattern: str) -> None:
        """Record the start of a RAG indexing operation."""
        self.events.append(
            {
                "event_type": "rag_index_start",
                "rag_name": rag_name,
                "source_pattern": source_pattern,
                "timestamp": self._iso_now(),
            }
        )

    def rag_index_end(
        self,
        *,
        rag_name: str,
        documents_indexed: int,
        chunks_indexed: int,
        duration_ms: int,
    ) -> None:
        """Record the end of a RAG indexing operation."""
        self.events.append(
            {
                "event_type": "rag_index_end",
                "rag_name": rag_name,
                "documents_indexed": documents_indexed,
                "chunks_indexed": chunks_indexed,
                "duration_ms": duration_ms,
                "timestamp": self._iso_now(),
            }
        )

    def rag_retrieve_start(
        self, *, rag_name: str, method_name: str, query_summary: str = ""
    ) -> None:
        """Record the start of a RAG retrieval operation."""
        self.events.append(
            {
                "event_type": "rag_retrieve_start",
                "rag_name": rag_name,
                "method_name": method_name,
                "query_summary": query_summary[:50],
                "timestamp": self._iso_now(),
            }
        )

    def rag_retrieve_end(
        self, *, rag_name: str, method_name: str, result_count: int, duration_ms: int = 0
    ) -> None:
        """Record the end of a RAG retrieval operation."""
        self.events.append(
            {
                "event_type": "rag_retrieve_end",
                "rag_name": rag_name,
                "method_name": method_name,
                "result_count": result_count,
                "duration_ms": duration_ms,
                "timestamp": self._iso_now(),
            }
        )

    def think(self, *, message: str) -> None:
        """Record a think event."""
        self.events.append(
            {
                "event_type": "think",
                "agent_name": self.agent_name,
                "message": message[:200],
                "timestamp": self._iso_now(),
            }
        )

    def observe(self, *, name: str, value_summary: str = "") -> None:
        """Record an observe event."""
        self.events.append(
            {
                "event_type": "observe",
                "agent_name": self.agent_name,
                "name": name,
                "value_summary": value_summary[:200],
                "timestamp": self._iso_now(),
            }
        )

    def store(self, *, key: str, value: Any = None) -> None:
        """Record a memory store event."""
        self.events.append(
            {
                "event_type": "store",
                "agent_name": self.agent_name,
                "key": key,
                "value": self._redact_value("", value),
                "timestamp": self._iso_now(),
            }
        )

    def agent_end(self, *, result_type: str = "ok", result_summary: str = "") -> None:
        """Record the end of agent execution."""
        duration_ms = int((time.time() - self._start_time) * 1000)
        self._append_event(
            "agent_end",
            agent_name=self.agent_name,
            result_type=result_type,
            result_summary=result_summary,
            duration_ms=duration_ms,
        )

    def agent_pause(self, *, agent_name: str) -> None:
        """Record an agent pause event."""
        self.events.append(
            {
                "event_type": "agent_pause",
                "agent_name": agent_name,
                "timestamp": self._iso_now(),
            }
        )

    def agent_resume(self, *, agent_name: str) -> None:
        """Record an agent resume event."""
        self.events.append(
            {
                "event_type": "agent_resume",
                "agent_name": agent_name,
                "timestamp": self._iso_now(),
            }
        )

    def agent_terminate(self, *, agent_name: str, reason: str = "user_request") -> None:
        """Record an agent terminate event."""
        self.events.append(
            {
                "event_type": "agent_terminate",
                "agent_name": agent_name,
                "reason": reason,
                "timestamp": self._iso_now(),
            }
        )

    def supervisor_start(self, *, name: str, strategy: str, child_count: int) -> None:
        """Record a supervisor start event."""
        self.events.append(
            {
                "event_type": "supervisor_start",
                "agent_name": self.agent_name,
                "supervisor_name": name,
                "strategy": strategy,
                "child_count": child_count,
                "timestamp": self._iso_now(),
            }
        )

    def supervisor_child_start(self, *, name: str, child_name: str) -> None:
        """Record a supervisor child start event."""
        self.events.append(
            {
                "event_type": "supervisor_child_start",
                "agent_name": self.agent_name,
                "supervisor_name": name,
                "child_name": child_name,
                "timestamp": self._iso_now(),
            }
        )

    def supervisor_child_restart(self, *, name: str, child_name: str, reason: str) -> None:
        """Record a supervisor child restart event."""
        self.events.append(
            {
                "event_type": "supervisor_child_restart",
                "agent_name": self.agent_name,
                "supervisor_name": name,
                "child_name": child_name,
                "reason": reason,
                "timestamp": self._iso_now(),
            }
        )

    def supervisor_shutdown(self, *, name: str, reason: str) -> None:
        """Record a supervisor shutdown event."""
        self.events.append(
            {
                "event_type": "supervisor_shutdown",
                "agent_name": self.agent_name,
                "supervisor_name": name,
                "reason": reason,
                "timestamp": self._iso_now(),
            }
        )

    def source_reload_start(self, *, agent_name: str, source_path: str) -> None:
        """Record a source reload start event."""
        self.events.append(
            {
                "event_type": "source_reload_start",
                "agent_name": agent_name,
                "source_path": source_path,
                "timestamp": self._iso_now(),
            }
        )

    def source_reload_end(self, *, agent_name: str, new_id: str) -> None:
        """Record a successful source reload event."""
        self.events.append(
            {
                "event_type": "source_reload_end",
                "agent_name": agent_name,
                "new_id": new_id,
                "timestamp": self._iso_now(),
            }
        )

    def source_reload_error(self, *, agent_name: str, error: str) -> None:
        """Record a failed source reload event."""
        self.events.append(
            {
                "event_type": "source_reload_error",
                "agent_name": agent_name,
                "error": error,
                "timestamp": self._iso_now(),
            }
        )

    def checkpoint(self, *, path: str, sections: int, keys: int) -> None:
        """Record a persistence checkpoint event."""
        self.events.append(
            {
                "event_type": "checkpoint",
                "agent_name": self.agent_name,
                "path": path,
                "sections": sections,
                "keys": keys,
                "timestamp": self._iso_now(),
            }
        )

    def checkpoint_save(self, *, agent_name: str, path: str, sections: int, keys: int) -> None:
        """Record an explicit checkpoint save event."""
        self.events.append(
            {
                "event_type": "checkpoint_save",
                "agent_name": agent_name,
                "path": path,
                "sections": sections,
                "keys": keys,
                "timestamp": self._iso_now(),
            }
        )

    def checkpoint_restore(self, *, agent_name: str, path: str, new_id: str) -> None:
        """Record a checkpoint restore event."""
        self.events.append(
            {
                "event_type": "checkpoint_restore",
                "agent_name": agent_name,
                "path": path,
                "new_id": new_id,
                "timestamp": self._iso_now(),
            }
        )

    def metrics_export(self, *, path: str, format: str) -> None:
        """Record a metrics export event."""
        self.events.append(
            {
                "event_type": "metrics_export",
                "agent_name": self.agent_name,
                "path": path,
                "format": format,
                "timestamp": self._iso_now(),
            }
        )

    def to_jsonl(self) -> str:
        """Return all events as a JSONL string (one JSON object per line)."""
        lines = [json.dumps(e, ensure_ascii=False) for e in self.events]
        return "\n".join(lines)

    def write(self, path: Path | str) -> None:
        """Write events to a JSONL file."""
        Path(path).write_text(self.to_jsonl() + "\n", encoding="utf-8")

    def _iso_now(self) -> str:
        """Current UTC time as ISO 8601 string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _redact_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Truncate long strings and redact secret-like values."""
        redacted: dict[str, Any] = {}
        for key, value in args.items():
            redacted[key] = self._redact_value(key, value)
        return redacted

    def _redact_value(self, key: str, value: Any) -> Any:
        """Redact or truncate a single value for trace safety."""
        key_lower = key.lower()

        # Redact values for secret-like keys
        for pattern in self._SECRET_PATTERNS:
            if pattern in key_lower:
                return "[REDACTED]"

        # Truncate long strings
        if isinstance(value, str):
            if len(value) > 100:
                return value[:97] + "..."
            return value

        # Scalar types pass through
        if isinstance(value, (int, float, bool)):
            return value

        if value is None:
            return None

        # Collections: show length, not contents
        if isinstance(value, list):
            return f"<list[{len(value)}]>"
        if isinstance(value, dict):
            return f"<dict[{len(value)}]>"

        # Fallback: type name
        return f"<{type(value).__name__}>"
