"""Expression AST nodes for AXON.

This module defines AST nodes for AXON expressions within method bodies.
These are used for static analysis and type checking without requiring
runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Expr:
    """Base class for all AXON expressions."""
    line: int


@dataclass(frozen=True)
class LiteralExpr(Expr):
    """Literal value: strings, numbers, booleans."""
    line: int
    value: Any
    type_hint: Optional[str] = None  # Optional type annotation


@dataclass(frozen=True)
class VariableExpr(Expr):
    """Variable reference."""
    line: int
    name: str


@dataclass(frozen=True)
class BinaryOpExpr(Expr):
    """Binary operation: +, -, *, /, ==, !=, <, >, <=, >=, &&, ||."""
    line: int
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class UnaryOpExpr(Expr):
    """Unary operation: -, !, not."""
    line: int
    op: str
    operand: Expr


@dataclass(frozen=True)
class CallExpr(Expr):
    """Function or method call."""
    line: int
    callee: Expr
    args: list[Expr] = field(default_factory=list)


@dataclass(frozen=True)
class MemberAccessExpr(Expr):
    """Field or method access: obj.field or obj.method()."""
    line: int
    object: Expr
    member: str


@dataclass(frozen=True)
class IndexExpr(Expr):
    """Index operation: array[index] or map[key]."""
    line: int
    object: Expr
    index: Expr


@dataclass(frozen=True)
class ListExpr(Expr):
    """List literal: [1, 2, 3]."""
    line: int
    elements: list[Expr] = field(default_factory=list)


@dataclass(frozen=True)
class MapExpr(Expr):
    """Map literal: {key: value, ...}."""
    line: int
    pairs: list[tuple[Expr, Expr]] = field(default_factory=list)


@dataclass(frozen=True)
class IfExpr(Expr):
    """Conditional expression: if cond { then } else { else }."""
    line: int
    condition: Expr
    then_branch: Expr
    else_branch: Optional[Expr] = None


@dataclass(frozen=True)
class ForExpr(Expr):
    """For-in loop: for var in iterable { body }."""
    line: int
    var_name: str
    iterable: Expr
    body: Expr


@dataclass(frozen=True)
class AssignExpr(Expr):
    """Assignment: name = value."""
    line: int
    name: str
    value: Expr


@dataclass(frozen=True)
class MatchArm:
    """One arm of a match expression."""
    pattern: Expr
    body: Expr
    guard: Expr | None = None


@dataclass(frozen=True)
class MatchExpr(Expr):
    """Match expression: match value { pattern => expr, ... }."""
    line: int
    value: Expr
    arms: list[MatchArm] = field(default_factory=list)


@dataclass(frozen=True)
class BlockExpr(Expr):
    """Block of expressions: { expr1; expr2; expr3 }."""
    line: int
    statements: list[Expr] = field(default_factory=list)


@dataclass(frozen=True)
class LetExpr(Expr):
    """Variable binding: let x = expr in body."""
    line: int
    name: str
    value: Expr
    body: Expr


@dataclass(frozen=True)
class ReturnExpr(Expr):
    """Return statement: return expr or return Ok(expr)."""
    line: int
    value: Expr
    is_ok: bool = True  # True for Ok(), False for Err()


@dataclass(frozen=True)
class ActExpr(Expr):
    """Tool invocation: act ToolName(arg1: expr1, arg2: expr2)."""
    line: int
    tool_name: str
    args: list[tuple[str, Expr]] = field(default_factory=list)


@dataclass(frozen=True)
class DelegateExpr(Expr):
    """Agent delegation: delegate AgentName(arg1: expr1, arg2: expr2)."""
    line: int
    agent_name: str
    args: list[tuple[str, Expr]] = field(default_factory=list)


@dataclass(frozen=True)
class StoreExpr(Expr):
    """Memory store: store target = value."""
    line: int
    target: Expr  # e.g. IndexExpr(MemberAccessExpr(Variable("memory"), "working"), Literal("key"))
    value: Expr


@dataclass(frozen=True)
class ThinkExpr(Expr):
    """AEL trace think statement: think "message"."""
    line: int
    message: Expr


@dataclass(frozen=True)
class ObserveExpr(Expr):
    """AEL trace observe statement: observe name: value_expr."""
    line: int
    name: str
    value: Expr


@dataclass(frozen=True)
class ModelCallExpr(Expr):
    """Model completion call: model.complete(prompt_expr)."""
    line: int
    prompt: Expr


@dataclass(frozen=True)
class TryExpr(Expr):
    """Try operator: expr? — unwrap Ok/Some values, propagate Err/None."""
    line: int
    operand: Expr


@dataclass(frozen=True)
class ErrorExpr(Expr):
    """Error constructor: Err(expr)."""
    line: int
    value: Expr


@dataclass(frozen=True)
class OkExpr(Expr):
    """Ok constructor: Ok(expr)."""
    line: int
    value: Expr


@dataclass(frozen=True)
class SomeExpr(Expr):
    """Some constructor: Some(expr)."""
    line: int
    value: Expr


@dataclass(frozen=True)
class NoneExpr(Expr):
    """None literal: None."""
    line: int


@dataclass(frozen=True)
class StringInterpolationExpr(Expr):
    """String interpolation: "Hello, {name}!"."""
    line: int
    parts: list[Expr] = field(default_factory=list)  # Mix of LiteralExpr and VariableExpr


@dataclass(frozen=True)
class GoExpr(Expr):
    """Async spawn: go expr."""
    line: int
    call: Expr


@dataclass(frozen=True)
class AwaitExpr(Expr):
    """Await future: await expr."""
    line: int
    future: Expr


@dataclass(frozen=True)
class ChanExpr(Expr):
    """Channel creation: chan() or chan(capacity)."""
    line: int
    capacity: Expr | None = None


@dataclass(frozen=True)
class SelectArm:
    """One arm of a select expression."""
    channel: Expr
    var_name: str
    body: Expr
    is_default: bool = False


@dataclass(frozen=True)
class SelectExpr(Expr):
    """Channel multiplexing: select { ch as v => body, default => body }."""
    line: int
    arms: list[SelectArm] = field(default_factory=list)


@dataclass(frozen=True)
class PoolExpr(Expr):
    """Worker pool: pool(size, target)."""
    line: int
    size: Expr
    target: Expr


@dataclass(frozen=True)
class SendExpr(Expr):
    """Send message to an agent: send recipient, message."""
    line: int
    recipient: Expr
    message: Expr


@dataclass(frozen=True)
class ReceiveExpr(Expr):
    """Receive message: receive() or receive(timeout_ms)."""
    line: int
    timeout_ms: Expr | None = None


@dataclass(frozen=True)
class BroadcastExpr(Expr):
    """Broadcast to a channel: broadcast channel, message."""
    line: int
    channel: Expr
    message: Expr


@dataclass(frozen=True)
class DiscoverExpr(Expr):
    """Discover agents: discover(pattern)."""
    line: int
    pattern: Expr


@dataclass(frozen=True)
class SpawnExpr(Expr):
    """Spawn an agent: spawn source, name, args."""
    line: int
    source: Expr
    name: Expr
    args: list[tuple[str, Expr]] = field(default_factory=list)


@dataclass(frozen=True)
class PauseExpr(Expr):
    """Pause an agent: pause(agent_name)."""
    line: int
    agent_name: Expr


@dataclass(frozen=True)
class ResumeExpr(Expr):
    """Resume an agent: resume(agent_name)."""
    line: int
    agent_name: Expr


@dataclass(frozen=True)
class TerminateExpr(Expr):
    """Terminate an agent: terminate(agent_name, reason?)."""
    line: int
    agent_name: Expr
    reason: Expr | None = None
