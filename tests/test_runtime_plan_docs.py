from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_plan_document_exists_and_defines_boundary():
    doc = _read("docs/RUNTIME_PLAN.md")
    for phrase in [
        "non-executing runtime-plan workflow",
        "declaration_inspection",
        "method_execution",
        "provider_calls",
        "tool_dispatch",
        "memory_mutation",
        "rag_indexing",
        "rag_retrieval",
        "flow_execution",
        "trace_replay",
        "secret_resolution",
        "fastmcp_runtime_import",
        "docs/runtime-rfcs/0001-minimal-non-executing-runtime.md",
        "tests/snapshots/runtime_plan/examples/",
    ]:
        assert phrase in doc


def test_runtime_plan_document_includes_operational_commands():
    doc = _read("docs/RUNTIME_PLAN.md")
    for command in [
        "axon runtime-plan examples/hello.ax",
        "axon runtime-plan examples/hello.ax --json",
        "--write tests/snapshots/runtime_plan/examples/hello.runtime-plan.json",
        "--check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json",
        "axon runtime-plan-corpus .",
        "axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke",
    ]:
        assert command in doc


def test_runtime_plan_document_is_linked_from_primary_docs():
    for path in [
        "README.md",
        "docs/CLI_REFERENCE.md",
        "docs/ROADMAP.md",
        "docs/RUNTIME_BOUNDARY.md",
        "docs/HANDOFF.md",
        "docs/runtime-rfcs/README.md",
    ]:
        text = _read(path)
        assert "docs/RUNTIME_PLAN.md" in text


def test_runtime_plan_docs_keep_non_execution_language_consistent():
    combined = "\n".join(
        _read(path)
        for path in [
            "README.md",
            "docs/CLI_REFERENCE.md",
            "docs/RUNTIME_PLAN.md",
            "docs/RUNTIME_BOUNDARY.md",
            "docs/ROADMAP.md",
        ]
    )
    for phrase in [
        "does not execute",
        "provider calls",
        "tool dispatch",
        "memory mutation",
        "RAG indexing",
        "flow execution",
        "trace replay",
        "secret",
    ]:
        assert phrase in combined
