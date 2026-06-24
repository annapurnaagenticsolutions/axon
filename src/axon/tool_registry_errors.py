"""Error types for the AXON mock tool registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ToolErrorKind(Enum):
    """Kinds of tool dispatch errors."""

    NOT_FOUND = auto()
    MISSING_ARGUMENT = auto()
    TYPE_MISMATCH = auto()
    EVALUATION_FAILED = auto()
    NOT_IMPLEMENTED = auto()
    ARITY_MISMATCH = auto()
    SANDBOX_VIOLATION = auto()
    TIMEOUT = auto()


@dataclass(frozen=True)
class ToolError:
    """An error produced during tool dispatch."""

    kind: ToolErrorKind
    message: str
    line: int = 0

    def __repr__(self) -> str:
        return f"ToolError({self.kind.name}: {self.message})"
