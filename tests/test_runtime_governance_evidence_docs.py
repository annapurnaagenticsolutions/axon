from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_governance_evidence_documented():
    readme = _read("README.md")
    cli_ref = _read("docs/CLI_REFERENCE.md")
    governance = _read("docs/RUNTIME_GOVERNANCE.md")

    for text in (readme, cli_ref, governance):
        assert "axon runtime-governance-evidence" in text
        assert "runtime-governance.json" in text
        assert "does not execute AXON agents" in text


def test_runtime_governance_evidence_docs_keep_non_execution_boundary():
    combined = "\n".join([
        _read("README.md"),
        _read("docs/CLI_REFERENCE.md"),
        _read("docs/RUNTIME_GOVERNANCE.md"),
    ])
    for phrase in [
        "does not execute AXON agents",
        "call providers",
        "dispatch tools",
        "resolve secrets",
        "import FastMCP",
        "mutate memory",
        "index RAG data",
        "execute flows",
        "replay traces",
    ]:
        assert phrase in combined
