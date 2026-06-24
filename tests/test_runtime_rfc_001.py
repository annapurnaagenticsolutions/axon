from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RFC_PATH = ROOT / "docs" / "runtime-rfcs" / "0001-minimal-non-executing-runtime.md"
INDEX_PATH = ROOT / "docs" / "runtime-rfcs" / "README.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_rfc_001_exists_and_has_required_sections():
    text = _read(RFC_PATH)
    for phrase in [
        "# AXON Runtime RFC #001 — Minimal Non-Executing Runtime Plan",
        "**Status:** Draft",
        "## SUMMARY",
        "## PROBLEM / MOTIVATION",
        "## CURRENT BOUNDARY CHECK",
        "## PROPOSED RUNTIME SCOPE",
        "## NON-GOALS",
        "## AXON SYNTAX EXECUTED",
        "## PROVIDER PLUGIN IMPACT",
        "## TOOL DISPATCH IMPACT",
        "## MEMORY / RAG / FLOW IMPACT",
        "## TRACE AND OBSERVABILITY GUARANTEES",
        "## SECURITY AND SECRET HANDLING",
        "## TESTING STRATEGY",
        "## ROLLBACK PLAN",
        "## ACCEPTANCE CRITERIA",
        "## OPEN QUESTIONS",
    ]:
        assert phrase in text


def test_runtime_rfc_001_preserves_non_executing_boundary():
    text = _read(RFC_PATH)
    required = [
        "does **not** permit live AXON agent execution",
        "No AXON syntax is executed by this RFC.",
        "Do not execute `fn` method bodies.",
        "Do not call `@plan`",
        "Do not dispatch `act ToolName(...)` to real tools.",
        "Do not mutate `Memory<ShortTerm>`",
        "Do not build or query vector indexes.",
        "Do not execute `flow` DAGs.",
        "Do not replay trace logs.",
    ]
    for phrase in required:
        assert phrase in text


def test_runtime_rfc_001_is_secret_safe_and_dependency_safe():
    text = _read(RFC_PATH)
    for phrase in [
        "Do not resolve environment placeholders",
        "Do not print provider API keys.",
        "Do not include secrets in snapshots.",
        "Do not make network calls.",
        "Do not import provider SDKs.",
        "Do not import FastMCP in compiler-core runtime planning code.",
        "stdlib-only in compiler core",
    ]:
        assert phrase in text
    assert "sk-" not in text


def test_runtime_rfc_index_links_rfc_001():
    index = _read(INDEX_PATH)
    assert "0001-minimal-non-executing-runtime.md" in index
    assert "Minimal Non-Executing Runtime Plan" in index
    assert "Use `axon runtime-rfc-template`" in index


def test_runtime_docs_reference_rfc_001():
    readme = _read(ROOT / "README.md")
    roadmap = _read(ROOT / "docs" / "ROADMAP.md")
    boundary = _read(ROOT / "docs" / "RUNTIME_BOUNDARY.md")
    for text in [readme, roadmap, boundary]:
        assert "0001-minimal-non-executing-runtime.md" in text
    assert "does not permit live execution" in boundary
