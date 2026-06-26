"""Native evaluator bridge — uses Rust evaluator via PyO3 when available.

Falls back to Python evaluator for expressions containing side effects.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from result import Result, Ok, Err

from axon.evaluator import (
    Scope,
    evaluate as py_evaluate,
    reset_eval_depth,
    DispatchFn,
    KwargsDispatchFn,
    ModelCallFn,
    DelegateFn,
    TraceFn,
)
from axon.evaluator_errors import EvalError, EvalErrorKind
from axon.expression_ast import (
    ActExpr,
    AssignExpr,
    AwaitExpr,
    BinaryOpExpr,
    BlockExpr,
    CallExpr,
    ChanExpr,
    DelegateExpr,
    ErrorExpr,
    Expr,
    ForExpr,
    GoExpr,
    IfExpr,
    IndexExpr,
    LetExpr,
    LiteralExpr,
    ListExpr,
    MapExpr,
    MatchArm,
    MatchExpr,
    MemberAccessExpr,
    NoneExpr,
    OkExpr,
    PoolExpr,
    ReceiveExpr,
    SendExpr,
    BroadcastExpr,
    DiscoverExpr,
    SpawnExpr,
    PauseExpr,
    ResumeExpr,
    TerminateExpr,
    ReturnExpr,
    SelectExpr,
    SomeExpr,
    StoreExpr,
    StringInterpolationExpr,
    ThinkExpr,
    ObserveExpr,
    TryExpr,
    UnaryOpExpr,
    VariableExpr,
    ModelCallExpr,
)
from axon.memory_store import MemoryStore


def _is_pure(expr: Expr) -> bool:
    """Check if an expression tree contains no side-effectful nodes."""
    if isinstance(expr, (ActExpr, ThinkExpr, ModelCallExpr, DelegateExpr,
                         ObserveExpr, StoreExpr, CallExpr, GoExpr, AwaitExpr,
                         ChanExpr, SelectExpr, PoolExpr, SendExpr, ReceiveExpr,
                         BroadcastExpr, DiscoverExpr, SpawnExpr, PauseExpr,
                         ResumeExpr, TerminateExpr)):
        return False
    if isinstance(expr, BinaryOpExpr):
        return _is_pure(expr.left) and _is_pure(expr.right)
    if isinstance(expr, UnaryOpExpr):
        return _is_pure(expr.operand)
    if isinstance(expr, IfExpr):
        return (_is_pure(expr.condition) and _is_pure(expr.then_branch)
                and (expr.else_branch is None or _is_pure(expr.else_branch)))
    if isinstance(expr, BlockExpr):
        return all(_is_pure(s) for s in expr.statements)
    if isinstance(expr, LetExpr):
        return _is_pure(expr.value) and _is_pure(expr.body)
    if isinstance(expr, ForExpr):
        return _is_pure(expr.iterable) and _is_pure(expr.body)
    if isinstance(expr, MatchExpr):
        if not _is_pure(expr.value):
            return False
        for arm in expr.arms:
            if arm.guard is not None and not _is_pure(arm.guard):
                return False
            if not _is_pure(arm.expr):
                return False
        return True
    if isinstance(expr, ListExpr):
        return all(_is_pure(e) for e in expr.elements)
    if isinstance(expr, MapExpr):
        return all(_is_pure(k) and _is_pure(v) for k, v in expr.pairs)
    if isinstance(expr, IndexExpr):
        return _is_pure(expr.object) and _is_pure(expr.index)
    if isinstance(expr, MemberAccessExpr):
        return _is_pure(expr.object)
    if isinstance(expr, StringInterpolationExpr):
        return all(_is_pure(p) for p in expr.parts)
    if isinstance(expr, TryExpr):
        return _is_pure(expr.operand)
    if isinstance(expr, OkExpr):
        return _is_pure(expr.value)
    if isinstance(expr, ErrorExpr):
        return _is_pure(expr.value)
    if isinstance(expr, SomeExpr):
        return _is_pure(expr.value)
    if isinstance(expr, ReturnExpr):
        return _is_pure(expr.value)
    if isinstance(expr, AssignExpr):
        return _is_pure(expr.value)
    # LiteralExpr, VariableExpr, NoneExpr are pure
    return True


def _expr_to_json(expr: Expr) -> dict[str, Any]:
    """Convert a Python Expr AST node to the JSON dict expected by Rust."""
    if isinstance(expr, LiteralExpr):
        return {"kind": "literal", "value": _literal_to_json(expr.value)}
    if isinstance(expr, VariableExpr):
        return {"kind": "variable", "name": expr.name}
    if isinstance(expr, BinaryOpExpr):
        return {"kind": "binary_op", "op": expr.op,
                "left": _expr_to_json(expr.left), "right": _expr_to_json(expr.right)}
    if isinstance(expr, UnaryOpExpr):
        return {"kind": "unary_op", "op": expr.op, "operand": _expr_to_json(expr.operand)}
    if isinstance(expr, IfExpr):
        d: dict[str, Any] = {"kind": "if", "condition": _expr_to_json(expr.condition),
                             "then_branch": _expr_to_json(expr.then_branch)}
        if expr.else_branch is not None:
            d["else_branch"] = _expr_to_json(expr.else_branch)
        return d
    if isinstance(expr, BlockExpr):
        return {"kind": "block", "statements": [_expr_to_json(s) for s in expr.statements]}
    if isinstance(expr, LetExpr):
        return {"kind": "let", "name": expr.name,
                "value": _expr_to_json(expr.value), "body": _expr_to_json(expr.body)}
    if isinstance(expr, AssignExpr):
        return {"kind": "assign", "name": expr.name, "value": _expr_to_json(expr.value)}
    if isinstance(expr, ForExpr):
        return {"kind": "for", "var_name": expr.var_name,
                "iterable": _expr_to_json(expr.iterable), "body": _expr_to_json(expr.body)}
    if isinstance(expr, MatchExpr):
        arms = []
        for arm in expr.arms:
            a: dict[str, Any] = {"pattern": arm.pattern, "expr": _expr_to_json(arm.expr)}
            if arm.guard is not None:
                a["guard"] = _expr_to_json(arm.guard)
            arms.append(a)
        return {"kind": "match", "value": _expr_to_json(expr.value), "arms": arms}
    if isinstance(expr, ListExpr):
        return {"kind": "list", "elements": [_expr_to_json(e) for e in expr.elements]}
    if isinstance(expr, MapExpr):
        return {"kind": "map", "pairs": [[_expr_to_json(k), _expr_to_json(v)] for k, v in expr.pairs]}
    if isinstance(expr, MemberAccessExpr):
        return {"kind": "member_access", "object": _expr_to_json(expr.object), "member": expr.member}
    if isinstance(expr, IndexExpr):
        return {"kind": "index", "object": _expr_to_json(expr.object), "index": _expr_to_json(expr.index)}
    if isinstance(expr, StringInterpolationExpr):
        return {"kind": "string_interpolation", "parts": [_expr_to_json(p) for p in expr.parts]}
    if isinstance(expr, TryExpr):
        return {"kind": "try", "operand": _expr_to_json(expr.operand)}
    if isinstance(expr, OkExpr):
        return {"kind": "ok", "value": _expr_to_json(expr.value)}
    if isinstance(expr, ErrorExpr):
        return {"kind": "error", "value": _expr_to_json(expr.value)}
    if isinstance(expr, SomeExpr):
        return {"kind": "some", "value": _expr_to_json(expr.value)}
    if isinstance(expr, NoneExpr):
        return {"kind": "none"}
    if isinstance(expr, ReturnExpr):
        return {"kind": "return", "value": _expr_to_json(expr.value)}
    # Side-effectful nodes — should not be reached if _is_pure was checked
    if isinstance(expr, ActExpr):
        return {"kind": "act", "tool_name": expr.tool_name,
                "args": [[k, _expr_to_json(v)] for k, v in expr.args]}
    if isinstance(expr, ModelCallExpr):
        return {"kind": "model_call", "prompt": _expr_to_json(expr.prompt)}
    if isinstance(expr, ThinkExpr):
        return {"kind": "think", "message": _expr_to_json(expr.message)}
    raise ValueError(f"Cannot convert {type(expr).__name__} to JSON")


def _literal_to_json(value: Any) -> Any:
    """Convert a Python literal value to the JSON format expected by Rust LiteralValue."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return {"bool": value}
    if isinstance(value, int):
        return {"int": value}
    if isinstance(value, float):
        return {"float": value}
    if isinstance(value, str):
        return {"string": value}
    # Fallback: serialize as string
    return {"string": str(value)}


def _scope_to_json(scope: Scope) -> dict[str, Any]:
    """Flatten a Scope chain into a JSON-serializable dict."""
    result: dict[str, Any] = {}
    chain: list[Scope] = []
    s: Optional[Scope] = scope
    while s is not None:
        chain.append(s)
        s = s._parent
    for s in reversed(chain):
        for k, v in s._bindings.items():
            result[k] = v
    return result


def evaluate(
    expr: Expr,
    scope: Scope,
    *,
    dispatch_fn: Optional[DispatchFn] = None,
    kwargs_dispatch_fn: Optional[KwargsDispatchFn] = None,
    memory_store: Optional[MemoryStore] = None,
    model_call_fn: Optional[ModelCallFn] = None,
    delegate_fn: Optional[DelegateFn] = None,
    trace_fn: Optional[TraceFn] = None,
    max_depth: Optional[int] = None,
) -> Result[Any, EvalError]:
    """Evaluate an AXON expression, using the Rust native evaluator when possible.

    For pure expressions (no side-effectful nodes), delegates to the Rust
    evaluator via PyO3 for speed. For expressions containing side effects,
    falls back to the Python evaluator.
    """
    if not _is_pure(expr):
        return py_evaluate(
            expr, scope,
            dispatch_fn=dispatch_fn,
            kwargs_dispatch_fn=kwargs_dispatch_fn,
            memory_store=memory_store,
            model_call_fn=model_call_fn,
            delegate_fn=delegate_fn,
            trace_fn=trace_fn,
            max_depth=max_depth,
        )

    try:
        import axon_parser
    except ImportError:
        return py_evaluate(
            expr, scope,
            dispatch_fn=dispatch_fn,
            kwargs_dispatch_fn=kwargs_dispatch_fn,
            memory_store=memory_store,
            model_call_fn=model_call_fn,
            delegate_fn=delegate_fn,
            trace_fn=trace_fn,
            max_depth=max_depth,
        )

    try:
        expr_json = json.dumps(_expr_to_json(expr))
        scope_json = json.dumps(_scope_to_json(scope))
        depth = max_depth if max_depth is not None else 1000
        result = axon_parser.evaluate_expr(expr_json, scope_json, depth)
        return Ok(result)
    except Exception as e:
        # On any Rust evaluator error, fall back to Python
        return py_evaluate(
            expr, scope,
            dispatch_fn=dispatch_fn,
            kwargs_dispatch_fn=kwargs_dispatch_fn,
            memory_store=memory_store,
            model_call_fn=model_call_fn,
            delegate_fn=delegate_fn,
            trace_fn=trace_fn,
            max_depth=max_depth,
        )
