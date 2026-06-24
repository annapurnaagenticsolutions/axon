from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_boundary_document_exists_and_states_current_posture():
    doc = _read("docs/RUNTIME_BOUNDARY.md")
    assert "AXON Runtime Boundary" in doc
    assert "currently non-executing" in doc or "intentionally non-executing" in doc
    for phrase in [
        "parse `.ax` source files into AST dataclasses",
        "validate declaration-level semantics",
        "generate FastMCP Python server stubs",
        "preview AEL-looking trace events",
        "read existing JSONL trace logs",
    ]:
        assert phrase in doc


def test_runtime_boundary_document_forbids_accidental_runtime_behavior():
    doc = _read("docs/RUNTIME_BOUNDARY.md")
    for phrase in [
        "dispatch `act` calls to real tools",
        "call model providers",
        "resolve or print API keys",
        "run RAG indexing",
        "execute flow DAGs",
        "replay traces as actions",
        "import provider SDKs in compiler-core modules",
        "require FastMCP for compiler tests",
    ]:
        assert phrase in doc


def test_runtime_boundary_document_defines_future_runtime_gate():
    doc = _read("docs/RUNTIME_BOUNDARY.md")
    for phrase in [
        "provider plugin protocol",
        "tool dispatch interface",
        "memory backend contracts",
        "trace emission guarantees",
        "sandboxing and permissions model",
        "secret loading and redaction rules",
        "deterministic replay boundaries",
        "which AXON syntax it executes",
        "how provider calls are mocked in tests",
        "which tests prove no accidental provider calls occur",
    ]:
        assert phrase in doc


def test_readme_links_runtime_boundary():
    readme = _read("README.md")
    assert "docs/RUNTIME_BOUNDARY.md" in readme
    assert "runtime-boundary" in readme or "runtime boundary" in readme


def test_roadmap_links_runtime_boundary():
    roadmap = _read("docs/ROADMAP.md")
    assert "docs/RUNTIME_BOUNDARY.md" in roadmap
    assert "non-executing" in roadmap
    assert "provider calls" in roadmap
    assert "tool dispatch" in roadmap


def test_contributing_links_runtime_boundary():
    contributing = _read("docs/CONTRIBUTING.md")
    assert "docs/RUNTIME_BOUNDARY.md" in contributing
    assert "Current compiler-core work must remain non-executing" in contributing


def test_handoff_links_runtime_boundary():
    handoff = _read("docs/HANDOFF.md")
    assert "docs/RUNTIME_BOUNDARY.md" in handoff
    assert "compiler-core commands remain non-executing" in handoff
    assert "secret-safe" in handoff
