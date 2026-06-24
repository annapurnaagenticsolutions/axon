"""Error types for the AXON expression evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class EvalErrorKind(Enum):
    """Kinds of evaluation errors."""

    UNKNOWN_VARIABLE = auto()
    TYPE_MISMATCH = auto()
    DIVISION_BY_ZERO = auto()
    NOT_IMPLEMENTED = auto()
    INVALID_OPERATION = auto()
    MISSING_ARGUMENT = auto()
    TOOL_NOT_FOUND = auto()
    TOOL_DISPATCH_FAILED = auto()
    INDEX_OUT_OF_BOUNDS = auto()
    INVALID_INDEX = auto()
    SANDBOX_VIOLATION = auto()


@dataclass(frozen=True)
class EvalError:
    """An error produced during expression evaluation."""

    kind: EvalErrorKind
    message: str
    line: int = 0

    def __repr__(self) -> str:
        return f"EvalError({self.kind.name}: {self.message})"
