from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_plan_review_doc_exists_and_preserves_boundary():
    doc = _read("docs/RUNTIME_PLAN_REVIEW.md")
    for phrase in [
        "axon runtime-plan-review",
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
        "Runtime RFC",
    ]:
        assert phrase in doc


def test_runtime_plan_review_doc_includes_required_evidence_commands():
    doc = _read("docs/RUNTIME_PLAN_REVIEW.md")
    for command in [
        "python -m compileall -q src tests",
        "axon runtime-plan examples/hello.ax",
        "axon runtime-plan-corpus .",
        "axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots --no-smoke",
        "axon deps .",
        "axon hygiene .",
    ]:
        assert command in doc


def test_runtime_plan_review_doc_is_linked_from_primary_docs():
    for path in [
        "README.md",
        "docs/CLI_REFERENCE.md",
        "docs/RUNTIME_PLAN.md",
        "docs/HANDOFF.md",
    ]:
        assert "docs/RUNTIME_PLAN_REVIEW.md" in _read(path)
