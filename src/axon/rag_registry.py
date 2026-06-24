"""RAG registry for AXON.

Registers RagDecl objects and dispatches rag method calls by evaluating
the method's parsed body expression with a scoped argument map that
includes a VectorStore instance and an embed function.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from result import Result, Ok, Err

from axon.ast_nodes import MethodDecl, RagDecl
from axon.evaluator import Scope, evaluate
from axon.rag_embedder import mock_embed
from axon.rag_indexer import index_rag
from axon.tool_registry import _infer_body_expr, _parse_default
from axon.tool_registry_errors import ToolError, ToolErrorKind
from axon.type_checker import validate_runtime_type
from axon.vector_store import VectorStore


class RagRegistry:
    """Registry that stores RagDecl definitions and evaluates their methods on dispatch."""

    def __init__(self, default_dimension: int = 128, source_base: Path | None = None) -> None:
        self._rags: dict[str, RagDecl] = {}
        self._stores: dict[str, VectorStore] = {}
        self._indexed: set[str] = set()
        self._default_dimension = default_dimension
        self._source_base = source_base

    def register(self, rag: RagDecl) -> None:
        """Register a RAG declaration."""
        self._rags[rag.name] = rag
        self._stores[rag.name] = VectorStore(dimension=self._default_dimension)

    def register_all(self, declarations: list) -> None:
        """Register every RagDecl found in a list of parsed declarations."""
        from axon.ast_nodes import RagDecl

        for decl in declarations:
            if isinstance(decl, RagDecl):
                self.register(decl)

    def get_store(self, rag_name: str) -> VectorStore | None:
        """Get the vector store for a registered RAG."""
        return self._stores.get(rag_name)

    def dispatch(
        self,
        full_name: str,
        kwargs: dict[str, Any],
        emitter: Any | None = None,
    ) -> Result[Any, ToolError]:
        """Dispatch a RAG method call.

        The `full_name` must be in the form ``RagName.methodName``.
        Auto-indexes the RAG on first dispatch if the store is empty.
        """
        if "." not in full_name:
            return Err(
                ToolError(
                    kind=ToolErrorKind.NOT_FOUND,
                    message=f"RAG method '{full_name}' must be in form 'RagName.methodName'",
                    line=0,
                )
            )

        rag_name, method_name = full_name.split(".", 1)
        rag = self._rags.get(rag_name)
        if rag is None:
            return Err(
                ToolError(
                    kind=ToolErrorKind.NOT_FOUND,
                    message=f"RAG '{rag_name}' is not defined",
                    line=0,
                )
            )

        # Find the method
        method: MethodDecl | None = None
        for m in rag.methods:
            if m.name == method_name:
                method = m
                break

        if method is None:
            return Err(
                ToolError(
                    kind=ToolErrorKind.NOT_FOUND,
                    message=f"RAG '{rag_name}' has no method '{method_name}'",
                    line=0,
                )
            )

        # Validate required arguments
        provided = set(kwargs.keys())
        for param in method.params:
            if param.default is None and param.name not in provided:
                return Err(
                    ToolError(
                        kind=ToolErrorKind.MISSING_ARGUMENT,
                        message=(
                            f"RAG '{rag_name}.{method_name}' missing required argument: "
                            f"{param.name}: {param.type_str}"
                        ),
                        line=rag.line,
                    )
                )

        # Validate argument types at runtime
        for param in method.params:
            if param.name in kwargs:
                err = validate_runtime_type(kwargs[param.name], param.type_str)
                if err:
                    return Err(
                        ToolError(
                            kind=ToolErrorKind.TYPE_MISMATCH,
                            message=f"RAG '{rag_name}.{method_name}' argument '{param.name}': {err} (expected {param.type_str})",
                            line=rag.line,
                        )
                    )

        store = self._stores[rag_name]

        # Auto-index on first dispatch if store is empty
        if rag_name not in self._indexed and store.count() == 0:
            self._indexed.add(rag_name)
            if emitter is not None:
                emitter.rag_index_start(rag_name=rag_name, source_pattern=rag.source)
            stats = index_rag(rag, store, source_base=self._source_base)
            if emitter is not None:
                emitter.rag_index_end(
                    rag_name=rag_name,
                    documents_indexed=stats["documents_indexed"],
                    chunks_indexed=stats["chunks_indexed"],
                    duration_ms=stats["duration_ms"],
                )

        # Emit retrieve start trace
        query_summary = ""
        if "query" in kwargs:
            query_summary = str(kwargs["query"])[:50]
        if emitter is not None:
            emitter.rag_retrieve_start(
                rag_name=rag_name, method_name=method_name, query_summary=query_summary
            )
        retrieve_start = time.time()

        # Build evaluation scope
        scope = Scope()
        for param in method.params:
            if param.name in kwargs:
                scope.set(param.name, kwargs[param.name])
            elif param.default is not None:
                scope.set(param.name, _parse_default(param.default))

        # Inject the vector store and embed function
        scope.set("store", store)
        scope.set("embed", mock_embed)

        # Evaluate method body
        body_expr = method.parsed_body
        if body_expr is None:
            body_expr = _infer_body_expr(method.body)

        if body_expr is None:
            return Err(
                ToolError(
                    kind=ToolErrorKind.NOT_IMPLEMENTED,
                    message=(
                        f"RAG '{rag_name}.{method_name}' has no parsed body and its raw body "
                        f"cannot be evaluated: {method.body[:60]!r}"
                    ),
                    line=rag.line,
                )
            )

        eval_result = evaluate(body_expr, scope)

        # Emit retrieve end trace
        duration_ms = int((time.time() - retrieve_start) * 1000)
        result_count = 0
        if isinstance(eval_result, Ok):
            val = eval_result.ok_value
            if isinstance(val, list):
                result_count = len(val)
        if emitter is not None:
            emitter.rag_retrieve_end(
                rag_name=rag_name,
                method_name=method_name,
                result_count=result_count,
                duration_ms=duration_ms,
            )

        if isinstance(eval_result, Err):
            return Err(
                ToolError(
                    kind=ToolErrorKind.EVALUATION_FAILED,
                    message=f"RAG '{rag_name}.{method_name}' body evaluation failed: {eval_result.err_value}",
                    line=rag.line,
                )
            )

        return Ok(eval_result.ok_value)
