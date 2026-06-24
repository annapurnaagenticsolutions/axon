"""Sandboxed tool execution for AXON runtime.

Provides time-bounded, depth-limited, and operation-restricted tool dispatch
wrappers around the standard MockToolRegistry.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Any

from result import Err, Ok, Result

from axon.tool_registry import MockToolRegistry, ToolError, ToolErrorKind


@dataclass
class SandboxConfig:
    """Configuration for sandboxed tool execution.

    Attributes:
        timeout_ms: Maximum time (in milliseconds) a single tool dispatch
            may run before being forcibly terminated. ``None`` means no limit.
        max_eval_depth: Maximum expression evaluation nesting depth.
            ``None`` means no limit.
        denied_tools: Tool names that are blocked in this sandbox.
        denied_operations: Operation kinds that are blocked (e.g. "file_read",
            "network", "subprocess"). Currently informational for Phase 1.
    """

    timeout_ms: int | None = 5000
    max_eval_depth: int | None = 100
    denied_tools: set[str] = field(default_factory=set)
    denied_operations: set[str] = field(default_factory=set)


class SandboxViolationError(Exception):
    """Raised when a sandboxed operation violates configured limits."""


class SandboxedToolRegistry:
    """Wrapper around MockToolRegistry that enforces sandbox limits.

    Example::

        inner = MockToolRegistry()
        inner.register(tool)
        sandbox = SandboxedToolRegistry(inner, SandboxConfig(timeout_ms=1000))
        result = sandbox.dispatch("Greet", {"name": "World"})
    """

    def __init__(self, registry: MockToolRegistry | None = None, config: SandboxConfig | None = None, builtins: dict[str, Any] | None = None) -> None:
        self._config = config or SandboxConfig()
        self._registry = registry or MockToolRegistry(max_depth=self._config.max_eval_depth, builtins=builtins)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="axon-sandbox-")

    def dispatch(self, name: str, kwargs: dict[str, Any]) -> Result[Any, ToolError]:
        """Dispatch a tool call with sandbox restrictions enforced.

        Denied tools are rejected immediately.  All other dispatches are run in
        a background thread with an optional timeout.
        """
        if name in self._config.denied_tools:
            return Err(
                ToolError(
                    kind=ToolErrorKind.SANDBOX_VIOLATION,
                    message=f"Tool '{name}' is denied by sandbox policy",
                    line=0,
                )
            )

        timeout = (
            self._config.timeout_ms / 1000.0
            if self._config.timeout_ms is not None
            else None
        )

        future = self._executor.submit(
            self._registry.dispatch, name, kwargs,
            max_depth=self._config.max_eval_depth,
        )
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            return Err(
                ToolError(
                    kind=ToolErrorKind.TIMEOUT,
                    message=f"Tool '{name}' exceeded sandbox timeout of {self._config.timeout_ms}ms",
                    line=0,
                )
            )
        except Exception as exc:
            return Err(
                ToolError(
                    kind=ToolErrorKind.EVALUATION_FAILED,
                    message=f"Tool '{name}' raised {type(exc).__name__}: {exc}",
                    line=0,
                )
            )

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def list_tools(self) -> list[str]:
        return self._registry.list_tools()

    def shutdown(self) -> None:
        """Clean up the internal thread pool."""
        self._executor.shutdown(wait=False)
