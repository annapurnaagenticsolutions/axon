"""Expression evaluator for AXON.

Evaluates parsed AXON expression AST nodes into Python values.
Operates with a mutable scope chain and optional tool dispatch.
"""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable, Optional

from result import Result, Ok, Err

from axon.expression_ast import (
    ActExpr,
    AssignExpr,
    AwaitExpr,
    BinaryOpExpr,
    BlockExpr,
    CallExpr,
    ChanExpr,
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
    DelegateExpr,
)
from axon.evaluator_errors import EvalError, EvalErrorKind
from axon.memory_store import MemoryStore
from axon.worker_pool import WorkerPool

# Optional dispatch function signatures:
DispatchFn = Callable[[str, list[Any]], Result[Any, EvalError]]
KwargsDispatchFn = Callable[[str, dict[str, Any]], Result[Any, EvalError]]
ModelCallFn = Callable[[str], Result[Any, EvalError]]
DelegateFn = Callable[[str, dict[str, Any]], Result[Any, EvalError]]


class Scope:
    """Mutable scope chain for variable lookups."""

    def __init__(self, parent: Optional[Scope] = None) -> None:
        self._bindings: dict[str, Any] = {}
        self._parent = parent

    def set(self, name: str, value: Any) -> None:
        """Bind a name to a value in the current scope."""
        self._bindings[name] = value

    def get(self, name: str) -> Any:
        """Look up a name, traversing parent scopes."""
        if name in self._bindings:
            return self._bindings[name]
        if self._parent is not None:
            return self._parent.get(name)
        raise KeyError(name)

    def child(self) -> Scope:
        """Create a child scope that inherits from this one."""
        return Scope(parent=self)

    def __contains__(self, name: str) -> bool:
        try:
            self.get(name)
            return True
        except KeyError:
            return False


TraceFn = Callable[[str, dict[str, Any]], None]

# Thread-local context for tracking per-call evaluation depth
_eval_context = threading.local()


def reset_eval_depth() -> None:
    """Reset the per-thread evaluation depth counter to zero.

    Call this before a fresh top-level ``evaluate()`` invocation to ensure
    depth-limit checks are accurate across independent evaluations.
    """
    _eval_context.depth = 0
    _eval_context.max_depth = None


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
    """Evaluate an AXON expression AST to a Python value.

    Args:
        expr: The expression AST to evaluate.
        scope: Mutable scope for variable lookups.
        dispatch_fn: Optional callback for CallExpr dispatch.
        kwargs_dispatch_fn: Optional callback for ActExpr dispatch.
        memory_store: Optional MemoryStore for store mutations.
        model_call_fn: Optional callback for ModelCallExpr dispatch.
        delegate_fn: Optional callback for DelegateExpr dispatch.
        trace_fn: Optional callback for trace events (think, observe).
        max_depth: Optional maximum recursion depth for evaluation.

    Returns:
        Ok(value) on success, Err(EvalError) on failure.
    """
    if not hasattr(_eval_context, "depth"):
        _eval_context.depth = 0
    if not hasattr(_eval_context, "max_depth"):
        _eval_context.max_depth = None
    if max_depth is not None:
        _eval_context.max_depth = max_depth
    _eval_context.depth += 1
    effective_max = _eval_context.max_depth
    if effective_max is not None and _eval_context.depth > effective_max:
        _eval_context.depth -= 1
        return Err(
            EvalError(
                kind=EvalErrorKind.SANDBOX_VIOLATION,
                message=f"Evaluation depth exceeded sandbox limit of {effective_max}",
                line=getattr(expr, "line", 0),
            )
        )
    try:
        if isinstance(expr, LiteralExpr):
            return Ok(expr.value)

        if isinstance(expr, VariableExpr):
            try:
                return Ok(scope.get(expr.name))
            except KeyError:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.UNKNOWN_VARIABLE,
                        message=f"Unknown variable: {expr.name}",
                        line=expr.line,
                    )
                )

        if isinstance(expr, ActExpr):
            # Evaluate keyword arguments
            kwargs: dict[str, Any] = {}
            for key, arg_expr in expr.args:
                arg_res = evaluate(arg_expr, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(arg_res, Err):
                    return arg_res
                kwargs[key] = arg_res.ok_value

            if kwargs_dispatch_fn is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.NOT_IMPLEMENTED,
                        message=f"No kwargs dispatch function for act: {expr.tool_name}",
                        line=expr.line,
                    )
                )

            return kwargs_dispatch_fn(expr.tool_name, kwargs)

        if isinstance(expr, DelegateExpr):
            # Evaluate keyword arguments
            kwargs: dict[str, Any] = {}
            for key, arg_expr in expr.args:
                arg_res = evaluate(arg_expr, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(arg_res, Err):
                    return arg_res
                kwargs[key] = arg_res.ok_value

            if delegate_fn is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.NOT_IMPLEMENTED,
                        message=f"No delegate function for agent: {expr.agent_name}",
                        line=expr.line,
                    )
                )

            return delegate_fn(expr.agent_name, kwargs)

        if isinstance(expr, ModelCallExpr):
            # Evaluate prompt expression
            prompt_res = evaluate(expr.prompt, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(prompt_res, Err):
                return prompt_res
            prompt = str(prompt_res.ok_value)

            if model_call_fn is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.NOT_IMPLEMENTED,
                        message="No model call function provided for model.complete()",
                        line=expr.line,
                    )
                )

            return model_call_fn(prompt)

        if isinstance(expr, StringInterpolationExpr):
            parts: list[str] = []
            for part in expr.parts:
                if isinstance(part, LiteralExpr):
                    parts.append(str(part.value))
                elif isinstance(part, VariableExpr):
                    try:
                        parts.append(str(scope.get(part.name)))
                    except KeyError:
                        return Err(
                            EvalError(
                                kind=EvalErrorKind.UNKNOWN_VARIABLE,
                                message=f"Unknown variable in interpolation: {part.name}",
                                line=part.line,
                            )
                        )
                else:
                    # Evaluate arbitrary expressions inside interpolation
                    res = evaluate(part, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                    if isinstance(res, Err):
                        return res
                    parts.append(str(res.ok_value))
            return Ok("".join(parts))

        if isinstance(expr, BinaryOpExpr):
            left_res = evaluate(expr.left, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(left_res, Err):
                return left_res
            right_res = evaluate(expr.right, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(right_res, Err):
                return right_res

            l = left_res.ok_value
            r = right_res.ok_value

            try:
                result = _apply_binary_op(expr.op, l, r)
            except ZeroDivisionError:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.DIVISION_BY_ZERO,
                        message="Division by zero",
                        line=expr.line,
                    )
                )
            except TypeError as e:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.TYPE_MISMATCH,
                        message=str(e),
                        line=expr.line,
                    )
                )

            return Ok(result)

        if isinstance(expr, UnaryOpExpr):
            operand_res = evaluate(expr.operand, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(operand_res, Err):
                return operand_res

            val = operand_res.ok_value
            try:
                result = _apply_unary_op(expr.op, val)
            except TypeError as e:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.TYPE_MISMATCH,
                        message=str(e),
                        line=expr.line,
                    )
                )

            return Ok(result)

        if isinstance(expr, CallExpr):
            # Evaluate arguments first (common path)
            args: list[Any] = []
            for arg_expr in expr.args:
                arg_res = evaluate(arg_expr, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(arg_res, Err):
                    return arg_res
                args.append(arg_res.ok_value)

            # Resolve callee
            if isinstance(expr.callee, VariableExpr):
                name = expr.callee.name
            elif isinstance(expr.callee, MemberAccessExpr):
                # Method call on an object: obj.method(...)
                obj_res = evaluate(expr.callee.object, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(obj_res, Err):
                    return obj_res
                obj = obj_res.ok_value
                if obj is None:
                    return Err(
                        EvalError(
                            kind=EvalErrorKind.INVALID_OPERATION,
                            message="Cannot call method on None",
                            line=expr.line,
                        )
                    )
                try:
                    method = getattr(obj, expr.callee.member)
                except AttributeError:
                    return Err(
                        EvalError(
                            kind=EvalErrorKind.UNKNOWN_VARIABLE,
                            message=f"Object has no method: {expr.callee.member}",
                            line=expr.line,
                        )
                    )
                try:
                    return Ok(method(*args))
                except Exception as e:
                    return Err(
                        EvalError(
                            kind=EvalErrorKind.INVALID_OPERATION,
                            message=str(e),
                            line=expr.line,
                        )
                    )
            else:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.NOT_IMPLEMENTED,
                        message="Complex callee expressions not yet supported",
                        line=expr.line,
                    )
                )

            # Check if the name is a callable value in scope (e.g. embed function)
            try:
                scope_value = scope.get(name)
                if callable(scope_value):
                    try:
                        return Ok(scope_value(*args))
                    except Exception as e:
                        return Err(
                            EvalError(
                                kind=EvalErrorKind.INVALID_OPERATION,
                                message=str(e),
                                line=expr.line,
                            )
                        )
            except KeyError:
                pass

            if dispatch_fn is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.NOT_IMPLEMENTED,
                        message=f"No dispatch function provided for call: {name}",
                        line=expr.line,
                    )
                )

            return dispatch_fn(name, args)

        if isinstance(expr, BlockExpr):
            if not expr.statements:
                return Ok(None)
            result: Any = None
            for stmt in expr.statements:
                stmt_res = evaluate(stmt, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(stmt_res, Err):
                    return stmt_res
                result = stmt_res.ok_value
            return Ok(result)

        if isinstance(expr, OkExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            return Ok({"ok": val_res.ok_value})

        if isinstance(expr, ErrorExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            return Ok({"err": val_res.ok_value})

        if isinstance(expr, SomeExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            return Ok(val_res.ok_value)

        if isinstance(expr, NoneExpr):
            return Ok(None)

        if isinstance(expr, TryExpr):
            inner_res = evaluate(expr.operand, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(inner_res, Err):
                return inner_res
            value = inner_res.ok_value

            # Unwrap Ok/Err dicts produced by OkExpr/ErrorExpr
            if isinstance(value, dict):
                if "err" in value:
                    return Err(
                        EvalError(
                            kind=EvalErrorKind.TOOL_DISPATCH_FAILED,
                            message=str(value["err"]),
                            line=expr.line,
                        )
                    )
                if "ok" in value:
                    return Ok(value["ok"])

            # Unwrap Some values
            if value is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.INVALID_OPERATION,
                        message="Tried to unwrap None",
                        line=expr.line,
                    )
                )

            return Ok(value)

        if isinstance(expr, ListExpr):
            elements: list[Any] = []
            for el in expr.elements:
                el_res = evaluate(el, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(el_res, Err):
                    return el_res
                elements.append(el_res.ok_value)
            return Ok(elements)

        if isinstance(expr, MapExpr):
            pairs: dict[Any, Any] = {}
            for k_expr, v_expr in expr.pairs:
                k_res = evaluate(k_expr, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(k_res, Err):
                    return k_res
                v_res = evaluate(v_expr, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(v_res, Err):
                    return v_res
                pairs[k_res.ok_value] = v_res.ok_value
            return Ok(pairs)

        if isinstance(expr, MemberAccessExpr):
            obj_res = evaluate(expr.object, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(obj_res, Err):
                return obj_res
            obj = obj_res.ok_value
            if obj is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.INVALID_OPERATION,
                        message="Cannot access member of None",
                        line=expr.line,
                    )
                )
            try:
                return Ok(getattr(obj, expr.member))
            except AttributeError:
                # Fallback: dict key access for dict-like objects
                if isinstance(obj, dict) and expr.member in obj:
                    return Ok(obj[expr.member])
                return Err(
                    EvalError(
                        kind=EvalErrorKind.UNKNOWN_VARIABLE,
                        message=f"Object has no member: {expr.member}",
                        line=expr.line,
                    )
                )

        if isinstance(expr, IndexExpr):
            obj_res = evaluate(expr.object, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(obj_res, Err):
                return obj_res
            idx_res = evaluate(expr.index, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(idx_res, Err):
                return idx_res
            obj = obj_res.ok_value
            idx = idx_res.ok_value
            try:
                return Ok(obj[idx])
            except (IndexError, KeyError, TypeError):
                return Err(
                    EvalError(
                        kind=EvalErrorKind.INVALID_INDEX,
                        message=f"Invalid index: {idx}",
                        line=expr.line,
                    )
                )

        if isinstance(expr, LetExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            if isinstance(expr.body, NoneExpr):
                # Standalone let without 'in': bind in current scope
                scope.set(expr.name, val_res.ok_value)
                return Ok(None)
            child = scope.child()
            child.set(expr.name, val_res.ok_value)
            return evaluate(expr.body, child, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)

        if isinstance(expr, AssignExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            scope.set(expr.name, val_res.ok_value)
            return Ok(val_res.ok_value)

        if isinstance(expr, StoreExpr):
            if memory_store is None:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.NOT_IMPLEMENTED,
                        message="No memory store provided for store operation",
                        line=expr.line,
                    )
                )

            # Evaluate value
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            value = val_res.ok_value

            # Extract section and key from target expression
            # Expected: IndexExpr(MemberAccessExpr(Variable("memory"), section), key_expr)
            target = expr.target
            if (
                isinstance(target, IndexExpr)
                and isinstance(target.object, MemberAccessExpr)
                and isinstance(target.object.object, VariableExpr)
                and target.object.object.name == "memory"
            ):
                section = target.object.member
            else:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.INVALID_OPERATION,
                        message="Store target must be memory.section[key]",
                        line=expr.line,
                    )
                )

            # Evaluate key expression
            key_res = evaluate(target.index, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(key_res, Err):
                return key_res
            key = key_res.ok_value

            memory_store.set(section, str(key), value)
            return Ok(value)

        if isinstance(expr, ReturnExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            # In a standalone evaluator, return just means "yield this value"
            return Ok(val_res.ok_value)

        if isinstance(expr, IfExpr):
            cond_res = evaluate(expr.condition, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(cond_res, Err):
                return cond_res
            if _is_truthy(cond_res.ok_value):
                return evaluate(expr.then_branch, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            elif expr.else_branch is not None:
                return evaluate(expr.else_branch, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            return Ok(None)

        if isinstance(expr, ForExpr):
            # Evaluate iterable
            iter_res = evaluate(expr.iterable, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(iter_res, Err):
                return iter_res
            iterable = iter_res.ok_value

            if not hasattr(iterable, "__iter__"):
                return Err(
                    EvalError(
                        kind=EvalErrorKind.TYPE_MISMATCH,
                        message=f"Cannot iterate over {type(iterable).__name__}",
                        line=expr.line,
                    )
                )

            result: Any = None
            for item in iterable:
                child = scope.child()
                child.set(expr.var_name, item)
                body_res = evaluate(expr.body, child, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(body_res, Err):
                    return body_res
                result = body_res.ok_value

            return Ok(result)

        if isinstance(expr, MatchExpr):
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(val_res, Err):
                return val_res
            value = val_res.ok_value

            # Exhaustiveness check: warn/error if no wildcard arm and value not covered
            has_wildcard = any(
                isinstance(arm.pattern, VariableExpr) or
                (isinstance(arm.pattern, LiteralExpr) and arm.pattern.value == "_")
                for arm in expr.arms
            )
            if not has_wildcard and not _is_exhaustive(value, expr.arms):
                return Err(
                    EvalError(
                        kind=EvalErrorKind.INVALID_OPERATION,
                        message=f"Non-exhaustive match for value {value!r}",
                        line=expr.line,
                    )
                )

            for arm in expr.arms:
                match_result = _match_pattern(
                    arm.pattern, value, scope,
                    dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn,
                    memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn,
                )
                if not match_result:
                    continue
                # If pattern returned bindings (dict), inject into child scope
                child = scope.child()
                if isinstance(match_result, dict):
                    for name, bound_value in match_result.items():
                        child.set(name, bound_value)

                # Evaluate guard if present
                if arm.guard is not None:
                    guard_res = evaluate(arm.guard, child, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                    if isinstance(guard_res, Err):
                        return guard_res
                    if not _is_truthy(guard_res.ok_value):
                        continue  # guard failed, try next arm

                return evaluate(arm.body, child, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)

            return Err(
                EvalError(
                    kind=EvalErrorKind.INVALID_OPERATION,
                    message=f"No match arm matched value: {value!r}",
                    line=expr.line,
                )
            )

        if isinstance(expr, ThinkExpr):
            # Evaluate message for side-effects (e.g. string interpolation) and
            # emit trace event if a trace_fn is provided.
            msg_res = evaluate(expr.message, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if trace_fn is not None and isinstance(msg_res, Ok):
                trace_fn("think", {"message": str(msg_res.ok_value)})
            return Ok(None)

        if isinstance(expr, ObserveExpr):
            # Evaluate value for side-effects and emit trace event if a trace_fn
            # is provided.
            val_res = evaluate(expr.value, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if trace_fn is not None and isinstance(val_res, Ok):
                trace_fn("observe", {"name": expr.name, "value_summary": str(val_res.ok_value)[:100]})
            return Ok(None)

        if isinstance(expr, GoExpr):
            # Spawn the inner expression in a background thread and return a Future
            fut: Future = Future()

            def _run() -> None:
                try:
                    result = evaluate(expr.call, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                    if isinstance(result, Ok):
                        fut.set_result(result.ok_value)
                    else:
                        fut.set_exception(RuntimeError(str(result.err_value)))
                except Exception as exc:
                    fut.set_exception(exc)

            threading.Thread(target=_run, daemon=True).start()
            return Ok(fut)

        if isinstance(expr, AwaitExpr):
            fut_res = evaluate(expr.future, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(fut_res, Err):
                return fut_res
            fut = fut_res.ok_value
            if not isinstance(fut, Future):
                return Err(
                    EvalError(
                        kind=EvalErrorKind.TYPE_MISMATCH,
                        message=f"await requires a Future, got {type(fut).__name__}",
                        line=expr.line,
                    )
                )
            try:
                return Ok(fut.result(timeout=30.0))
            except Exception as exc:
                return Err(
                    EvalError(
                        kind=EvalErrorKind.INVALID_OPERATION,
                        message=f"await failed: {exc}",
                        line=expr.line,
                    )
                )

        if isinstance(expr, ChanExpr):
            if expr.capacity is not None:
                cap_res = evaluate(expr.capacity, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(cap_res, Err):
                    return cap_res
                cap = cap_res.ok_value
                if not isinstance(cap, int):
                    return Err(
                        EvalError(
                            kind=EvalErrorKind.TYPE_MISMATCH,
                            message=f"chan capacity must be an integer, got {type(cap).__name__}",
                            line=expr.line,
                        )
                    )
                return Ok(queue.Queue(maxsize=cap))
            return Ok(queue.Queue())

        if isinstance(expr, SelectExpr):
            # Try non-blocking get on each channel arm
            for arm in expr.arms:
                if arm.is_default:
                    continue
                ch_res = evaluate(arm.channel, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(ch_res, Err):
                    return ch_res
                ch = ch_res.ok_value
                if not isinstance(ch, queue.Queue):
                    return Err(
                        EvalError(
                            kind=EvalErrorKind.TYPE_MISMATCH,
                            message=f"select arm requires a channel (Queue), got {type(ch).__name__}",
                            line=expr.line,
                        )
                    )
                try:
                    value = ch.get_nowait()
                except queue.Empty:
                    continue
                child = scope.child()
                child.set(arm.var_name, value)
                return evaluate(arm.body, child, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)

            # No channel had data — check default arm
            for arm in expr.arms:
                if arm.is_default:
                    return evaluate(arm.body, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)

            return Err(
                EvalError(
                    kind=EvalErrorKind.INVALID_OPERATION,
                    message="select: no channel has data and no default arm",
                    line=expr.line,
                )
            )

        if isinstance(expr, PoolExpr):
            size_res = evaluate(expr.size, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(size_res, Err):
                return size_res
            size = size_res.ok_value
            if not isinstance(size, int):
                return Err(
                    EvalError(
                        kind=EvalErrorKind.TYPE_MISMATCH,
                        message=f"pool size must be an integer, got {type(size).__name__}",
                        line=expr.line,
                    )
                )
            target_res = evaluate(expr.target, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(target_res, Err):
                return target_res
            target = target_res.ok_value
            pool = WorkerPool(size=size, target=target)
            return Ok(pool)

        if isinstance(expr, SendExpr):
            recipient_res = evaluate(expr.recipient, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(recipient_res, Err):
                return recipient_res
            recipient = recipient_res.ok_value
            message_res = evaluate(expr.message, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(message_res, Err):
                return message_res
            message = message_res.ok_value
            # Use distributed bus from scope if available, else fallback to message_bus
            if "__distributed_bus__" in scope:
                bus = scope.get("__distributed_bus__")
                from axon.distributed_bus import DistributedBus
                if isinstance(bus, DistributedBus):
                    bus.send(str(recipient), message)
                    return Ok(None)
            # Fallback: in-memory message bus
            if "__message_bus__" in scope:
                mb = scope.get("__message_bus__")
                mb.send(str(recipient), message)
                return Ok(None)
            return Err(
                EvalError(
                    kind=EvalErrorKind.INVALID_OPERATION,
                    message="send: no message bus available in scope",
                    line=expr.line,
                )
            )

        if isinstance(expr, ReceiveExpr):
            timeout_ms = 0
            if expr.timeout_ms is not None:
                t_res = evaluate(expr.timeout_ms, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(t_res, Err):
                    return t_res
                timeout_ms = t_res.ok_value
                if not isinstance(timeout_ms, int):
                    timeout_ms = int(timeout_ms)
            if "__distributed_bus__" in scope:
                bus = scope.get("__distributed_bus__")
                from axon.distributed_bus import DistributedBus
                if isinstance(bus, DistributedBus):
                    return Ok(bus.receive(timeout_ms=timeout_ms))
            if "__message_bus__" in scope:
                mb = scope.get("__message_bus__")
                return Ok(mb.receive(timeout_ms=timeout_ms))
            return Err(
                EvalError(
                    kind=EvalErrorKind.INVALID_OPERATION,
                    message="receive: no message bus available in scope",
                    line=expr.line,
                )
            )

        if isinstance(expr, BroadcastExpr):
            channel_res = evaluate(expr.channel, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(channel_res, Err):
                return channel_res
            channel = channel_res.ok_value
            message_res = evaluate(expr.message, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(message_res, Err):
                return message_res
            message = message_res.ok_value
            if "__distributed_bus__" in scope:
                bus = scope.get("__distributed_bus__")
                from axon.distributed_bus import DistributedBus
                if isinstance(bus, DistributedBus):
                    bus.broadcast(str(channel), message)
                    return Ok(None)
            if "__message_bus__" in scope:
                mb = scope.get("__message_bus__")
                mb.broadcast(str(channel), message)
                return Ok(None)
            return Err(
                EvalError(
                    kind=EvalErrorKind.INVALID_OPERATION,
                    message="broadcast: no message bus available in scope",
                    line=expr.line,
                )
            )

        if isinstance(expr, DiscoverExpr):
            pattern_res = evaluate(expr.pattern, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(pattern_res, Err):
                return pattern_res
            pattern = pattern_res.ok_value
            if "__service_registry__" in scope:
                registry = scope.get("__service_registry__")
                from axon.service_registry import ServiceRegistry
                if isinstance(registry, ServiceRegistry):
                    services = registry.discover(str(pattern))
                    return Ok([s.name for s in services])
            return Err(
                EvalError(
                    kind=EvalErrorKind.INVALID_OPERATION,
                    message="discover: no service registry available in scope",
                    line=expr.line,
                )
            )

        if isinstance(expr, SpawnExpr):
            source_res = evaluate(expr.source, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(source_res, Err):
                return source_res
            source = str(source_res.ok_value)
            name_res = evaluate(expr.name, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(name_res, Err):
                return name_res
            name = str(name_res.ok_value)
            kwargs: dict[str, Any] = {}
            for k, v_expr in expr.args:
                v_res = evaluate(v_expr, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(v_res, Err):
                    return v_res
                kwargs[k] = v_res.ok_value
            if "__lifecycle_manager__" in scope:
                manager = scope.get("__lifecycle_manager__")
                from axon.agent_lifecycle import AgentLifecycleManager
                if isinstance(manager, AgentLifecycleManager):
                    from pathlib import Path
                    result = manager.spawn(source_path=Path(source), name=name, args=kwargs)
                    if isinstance(result, Ok):
                        return Ok(result.ok_value)
                    return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message=result.err_value, line=expr.line))
            return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message="spawn: no lifecycle manager in scope", line=expr.line))

        if isinstance(expr, PauseExpr):
            name_res = evaluate(expr.agent_name, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(name_res, Err):
                return name_res
            if "__lifecycle_manager__" in scope:
                manager = scope.get("__lifecycle_manager__")
                from axon.agent_lifecycle import AgentLifecycleManager
                if isinstance(manager, AgentLifecycleManager):
                    result = manager.pause(str(name_res.ok_value))
                    if isinstance(result, Ok):
                        return Ok(None)
                    return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message=result.err_value, line=expr.line))
            return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message="pause: no lifecycle manager in scope", line=expr.line))

        if isinstance(expr, ResumeExpr):
            name_res = evaluate(expr.agent_name, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(name_res, Err):
                return name_res
            if "__lifecycle_manager__" in scope:
                manager = scope.get("__lifecycle_manager__")
                from axon.agent_lifecycle import AgentLifecycleManager
                if isinstance(manager, AgentLifecycleManager):
                    result = manager.resume(str(name_res.ok_value))
                    if isinstance(result, Ok):
                        return Ok(None)
                    return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message=result.err_value, line=expr.line))
            return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message="resume: no lifecycle manager in scope", line=expr.line))

        if isinstance(expr, TerminateExpr):
            name_res = evaluate(expr.agent_name, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
            if isinstance(name_res, Err):
                return name_res
            reason = "user_request"
            if expr.reason is not None:
                r_res = evaluate(expr.reason, scope, dispatch_fn=dispatch_fn, kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store, model_call_fn=model_call_fn, delegate_fn=delegate_fn, trace_fn=trace_fn)
                if isinstance(r_res, Err):
                    return r_res
                reason = str(r_res.ok_value)
            if "__lifecycle_manager__" in scope:
                manager = scope.get("__lifecycle_manager__")
                from axon.agent_lifecycle import AgentLifecycleManager
                if isinstance(manager, AgentLifecycleManager):
                    result = manager.terminate(str(name_res.ok_value), reason=reason)
                    if isinstance(result, Ok):
                        return Ok(None)
                    return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message=result.err_value, line=expr.line))
            return Err(EvalError(kind=EvalErrorKind.INVALID_OPERATION, message="terminate: no lifecycle manager in scope", line=expr.line))

        return Err(
            EvalError(
                kind=EvalErrorKind.NOT_IMPLEMENTED,
                message=f"Unsupported expression type: {type(expr).__name__}",
                line=getattr(expr, "line", 0),
            )
        )

    finally:
        _eval_context.depth -= 1


def _apply_binary_op(op: str, left: Any, right: Any) -> Any:
    """Apply a binary operator to two Python values."""
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right
    if op == "%":
        return left % right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    if op == "&&":
        return bool(left) and bool(right)
    if op == "||":
        return bool(left) or bool(right)
    raise TypeError(f"Unknown binary operator: {op}")


def _apply_unary_op(op: str, operand: Any) -> Any:
    """Apply a unary operator to a Python value."""
    if op == "-":
        return -operand
    if op == "!":
        return not operand
    if op == "not":
        return not operand
    raise TypeError(f"Unknown unary operator: {op}")


def _is_truthy(value: Any) -> bool:
    """Determine if a value is truthy in AXON semantics."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) > 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return bool(value)


def _match_pattern(
    pattern: Expr,
    value: Any,
    scope: Scope,
    dispatch_fn: Optional[DispatchFn],
    kwargs_dispatch_fn: Optional[KwargsDispatchFn] = None,
    memory_store: Optional[MemoryStore] = None,
    model_call_fn: Optional[ModelCallFn] = None,
    delegate_fn: Optional[DelegateFn] = None,
) -> bool | dict[str, Any]:
    """Check if a value matches a match-arm pattern.

    Returns:
        - False: pattern does not match
        - True: pattern matches with no bindings
        - dict: pattern matches with variable bindings

    Supports literal, wildcard, None, Some, tuple/list destructuring.
    """
    from axon.expression_ast import LiteralExpr, VariableExpr, NoneExpr, SomeExpr, ListExpr

    if isinstance(pattern, LiteralExpr):
        if pattern.value == "_":
            return True
        return pattern.value == value
    if isinstance(pattern, VariableExpr):
        if pattern.name == "_":
            return True
        # Variable binding pattern: bind the variable name to the value
        return {pattern.name: value}
    if isinstance(pattern, NoneExpr):
        return value is None
    if isinstance(pattern, SomeExpr):
        if value is None:
            return False
        # Some with inner pattern
        if pattern.value is None:
            return True
        return _match_pattern(
            pattern.value, value, scope, dispatch_fn,
            kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store,
            model_call_fn=model_call_fn, delegate_fn=delegate_fn,
        )
    if isinstance(pattern, ListExpr):
        if not isinstance(value, (list, tuple)):
            return False
        if len(pattern.elements) != len(value):
            return False
        bindings: dict[str, Any] = {}
        for i, elem in enumerate(pattern.elements):
            res = _match_pattern(
                elem, value[i], scope, dispatch_fn,
                kwargs_dispatch_fn=kwargs_dispatch_fn, memory_store=memory_store,
                model_call_fn=model_call_fn, delegate_fn=delegate_fn,
            )
            if res is False:
                return False
            if isinstance(res, dict):
                bindings.update(res)
        return bindings if bindings else True
    return False


def _is_exhaustive(value: Any, arms: list[MatchArm]) -> bool:
    """Best-effort exhaustive match check."""
    from axon.expression_ast import LiteralExpr, VariableExpr, NoneExpr, SomeExpr, ListExpr

    for arm in arms:
        if isinstance(arm.pattern, LiteralExpr) and arm.pattern.value == value:
            return True
        if isinstance(arm.pattern, LiteralExpr) and arm.pattern.value == "_":
            return True
        if isinstance(arm.pattern, VariableExpr):
            return True
        if value is None and isinstance(arm.pattern, NoneExpr):
            return True
        if value is not None and isinstance(arm.pattern, SomeExpr):
            return True
        if isinstance(value, (list, tuple)) and isinstance(arm.pattern, ListExpr):
            if len(arm.pattern.elements) == len(value):
                return True
    return False
