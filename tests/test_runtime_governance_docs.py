from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_governance_doc_mentions_boundary_and_commands():
    text = read("docs/RUNTIME_GOVERNANCE.md")
    for phrase in [
        "axon runtime-governance",
        "axon runtime-plan-review",
        "axon runtime-plan-review-check .",
        "axon runtime-plan-corpus .",
        "axon deps .",
        "axon hygiene .",
        "does not execute AXON agents",
        "call providers",
        "dispatch tools",
        "resolve secrets",
    ]:
        assert phrase in text


def test_readme_and_cli_reference_document_runtime_governance():
    readme = read("README.md")
    cli_reference = read("docs/CLI_REFERENCE.md")
    for command in ["axon runtime-governance", "axon runtime-governance-gate"]:
        assert command in readme
        assert command in cli_reference


def test_handoff_and_roadmap_reference_runtime_governance():
    assert "axon runtime-governance" in read("docs/HANDOFF.md")
    assert "axon runtime-governance" in read("docs/ROADMAP.md")
