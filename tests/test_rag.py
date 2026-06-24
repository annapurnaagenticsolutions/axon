"""Tests for AXON RAG / vector ops."""

import math

from result import Ok, Err

from axon.vector_store import VectorStore
from axon.rag_registry import RagRegistry
from axon.ast_nodes import RagDecl, MethodDecl, Param
from axon.tool_registry_errors import ToolErrorKind


# -- VectorStore tests --------------------------------------------

def test_vector_store_add_and_count():
    store = VectorStore(dimension=4)
    store.add("hello", [1.0, 0.0, 0.0, 0.0])
    store.add("world", [0.0, 1.0, 0.0, 0.0])
    assert store.count() == 2


def test_vector_store_search():
    store = VectorStore(dimension=4)
    store.add("hello", [1.0, 0.0, 0.0, 0.0])
    store.add("world", [0.0, 1.0, 0.0, 0.0])
    store.add("test", [0.0, 0.0, 1.0, 0.0])

    results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0]["text"] == "hello"
    assert results[0]["score"] == 1.0


def test_vector_store_search_returns_metadata():
    store = VectorStore(dimension=3)
    store.add("doc1", [1.0, 0.0, 0.0], {"source": "a.md"})
    results = store.search([1.0, 0.0, 0.0], top_k=1)
    assert results[0]["metadata"]["source"] == "a.md"


def test_vector_store_dimension_mismatch():
    store = VectorStore(dimension=3)
    try:
        store.add("doc", [1.0, 0.0])
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "dimension mismatch" in str(e)


def test_vector_store_empty_search():
    store = VectorStore(dimension=3)
    results = store.search([1.0, 0.0, 0.0], top_k=5)
    assert results == []


def test_vector_store_clear():
    store = VectorStore(dimension=3)
    store.add("doc", [1.0, 0.0, 0.0])
    store.clear()
    assert store.count() == 0


# -- RagRegistry tests --------------------------------------------

def _make_rag_decl(body: str) -> RagDecl:
    """Helper to create a minimal RagDecl with a retrieve method."""
    from axon.expression_parser import parse_expression
    return RagDecl(
        name="ProductDocs",
        source="./docs/**/*.md",
        chunker="sliding",
        embedder="@mock/embed",
        store="memory",
        methods=[
            MethodDecl(
                name="retrieve",
                params=[
                    Param(name="query", type_str="Str"),
                    Param(name="top_k", type_str="Int", default="3"),
                ],
                return_type="List<Str>",
                annotations=[],
                body=body,
                parsed_body=parse_expression(body) if body else None,
            )
        ],
    )


def test_rag_registry_register_and_dispatch():
    registry = RagRegistry()
    rag = _make_rag_decl('"hello"')
    registry.register(rag)

    res = registry.dispatch("ProductDocs.retrieve", {"query": "test"})
    assert isinstance(res, Ok)
    assert res.ok_value == "hello"


def test_rag_registry_store_injected():
    registry = RagRegistry(default_dimension=4)
    rag = _make_rag_decl('store.search([1.0, 0.0, 0.0, 0.0], 2)')
    registry.register(rag)

    store = registry.get_store("ProductDocs")
    store.add("doc1", [1.0, 0.0, 0.0, 0.0])
    store.add("doc2", [0.0, 1.0, 0.0, 0.0])

    res = registry.dispatch("ProductDocs.retrieve", {"query": "test"})
    assert isinstance(res, Ok)
    results = res.ok_value
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["text"] == "doc1"


def test_rag_registry_missing_method():
    registry = RagRegistry()
    rag = _make_rag_decl('"hello"')
    registry.register(rag)

    res = registry.dispatch("ProductDocs.nonexistent", {"query": "test"})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.NOT_FOUND


def test_rag_registry_missing_rag():
    registry = RagRegistry()
    res = registry.dispatch("Missing.retrieve", {"query": "test"})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.NOT_FOUND


def test_rag_registry_missing_argument():
    registry = RagRegistry()
    rag = _make_rag_decl('"hello"')
    registry.register(rag)

    res = registry.dispatch("ProductDocs.retrieve", {})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.MISSING_ARGUMENT


def test_rag_registry_type_mismatch():
    registry = RagRegistry()
    rag = _make_rag_decl('"hello"')
    registry.register(rag)

    res = registry.dispatch("ProductDocs.retrieve", {"query": 123})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.TYPE_MISMATCH


def test_rag_registry_default_argument():
    registry = RagRegistry()
    rag = _make_rag_decl('"hello"')
    registry.register(rag)

    # top_k has default=3, so only query is required
    res = registry.dispatch("ProductDocs.retrieve", {"query": "test"})
    assert isinstance(res, Ok)


def test_rag_registry_bad_name_format():
    registry = RagRegistry()
    res = registry.dispatch("retrieve", {"query": "test"})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.NOT_FOUND
    assert "must be in form" in res.err_value.message


# -- RagRegistry with parsed body (real expression) ---------------

def test_rag_registry_parsed_body_with_store():
    from axon.expression_parser import parse_expression
    registry = RagRegistry(default_dimension=3)
    body_expr = parse_expression('store.search([1.0, 0.0, 0.0], 1)')
    rag = RagDecl(
        name="Docs",
        source=".",
        chunker="sliding",
        embedder="@mock",
        store="memory",
        methods=[
            MethodDecl(
                name="find",
                params=[Param(name="q", type_str="Str")],
                return_type="List<Str>",
                annotations=[],
                body='store.search([1.0, 0.0, 0.0], 1)',
                parsed_body=body_expr,
            )
        ],
    )
    registry.register(rag)
    store = registry.get_store("Docs")
    store.add("match", [1.0, 0.0, 0.0])

    res = registry.dispatch("Docs.find", {"q": "test"})
    assert isinstance(res, Ok)
    assert len(res.ok_value) == 1
    assert res.ok_value[0]["text"] == "match"
