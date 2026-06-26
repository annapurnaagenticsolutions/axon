from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_documents_all_cli_commands():
    readme = _read("README.md")
    commands = [
        "axon version",
        "axon info",
        "axon project-info",
        "axon foundation-audit",
        "axon handoff",
        "axon task-template",
        "axon runtime-rfc-template",
        "axon runtime-plan",
        "axon runtime-plan-corpus",
        "axon runtime-plan-review",
        "axon runtime-plan-review-check",
        "axon runtime-governance",
        "axon runtime-governance-evidence",
        "axon runtime-governance-gate",
        "axon release-notes",
        "axon changelog",
        "axon release-bundle-manifest",
        "axon release-artifacts",
        "axon new",
        "axon init",
        "axon deps",
        "axon dependency-audit",
        "axon hygiene",
        "axon repo-hygiene",
        "axon precommit",
        "axon config",
        "axon syntax",
        "axon validate",
        "axon ast",
        "axon format",
        "axon check-project",
        "axon doctor",
        "axon build",
        "axon serve",
        "axon smoke",
        "axon trace-preview",
        "axon trace-read",
        "axon trace-log",
    ]

    for command in commands:
        assert command in readme


def test_readme_documents_supported_declarations():
    readme = _read("README.md")
    declarations = [
        "type aliases",
        "Prompt declarations",
        "Tool declarations",
        "Agent declarations",
        "RAG declarations",
        "Flow declarations",
    ]

    for declaration in declarations:
        assert declaration in readme


def test_readme_documents_current_limitations():
    readme = _read("README.md")
    limitations = [
        "LSP / IDE integration",
        "Multi-agent distributed mesh networking",
    ]

    for limitation in limitations:
        assert limitation in readme


def test_cli_reference_documents_same_command_surface():
    cli_reference = _read("docs/CLI_REFERENCE.md")
    for command in [
        "axon version",
        "axon info",
        "axon project-info",
        "axon foundation-audit",
        "axon handoff",
        "axon task-template",
        "axon runtime-rfc-template",
        "axon runtime-plan",
        "axon runtime-plan-corpus",
        "axon runtime-plan-review",
        "axon runtime-plan-review-check",
        "axon runtime-governance",
        "axon runtime-governance-evidence",
        "axon runtime-governance-gate",
        "axon release-notes",
        "axon changelog",
        "axon release-bundle-manifest",
        "axon release-artifacts",
        "axon new",
        "axon init",
        "axon deps",
        "axon dependency-audit",
        "axon hygiene",
        "axon repo-hygiene",
        "axon precommit",
        "axon config",
        "axon syntax",
        "axon validate",
        "axon ast",
        "axon format",
        "axon check-project",
        "axon doctor",
        "axon build",
        "axon serve",
        "axon smoke",
        "axon trace-preview",
        "axon trace-read",
        "axon trace-log",
        "axon dashboard",
        "axon playground",
    ]:
        assert command in cli_reference


def test_roadmap_exists_and_keeps_runtime_boundary_clear():
    roadmap = _read("docs/ROADMAP.md")
    assert "RFC-gated" in roadmap
    assert "provider-agnostic" in roadmap
    assert "never put API keys in `.ax` files" in roadmap


def test_handoff_documentation_exists():
    handoff = _read("docs/HANDOFF.md")
    for phrase in [
        "axon handoff",
        "axon version",
        "axon info",
        "axon project-info",
        "axon foundation-audit",
        "axon deps",
        "axon hygiene",
        "axon check-project",
        "axon release-notes",
        "axon release-artifacts",
        "docs/RELEASE_ARTIFACTS.md",
        "No provider API keys",
    ]:
        assert phrase in handoff


def test_contributor_documentation_exists():
    contributing = _read("docs/CONTRIBUTING.md")
    template = _read("docs/TASK_TICKET_TEMPLATE.md")
    for phrase in [
        "axon task-template",
        "Task-ticket workflow",
        "Do not call model providers",
        "validation evidence",
    ]:
        assert phrase in contributing
    for phrase in [
        "AXON Task",
        "BACKGROUND",
        "WHAT TO BUILD",
        "VALIDATION COMMANDS",
        "REVIEW NOTES",
    ]:
        assert phrase in template


def test_runtime_rfc_documentation_exists():
    readme = _read("README.md")
    cli_reference = _read("docs/CLI_REFERENCE.md")
    runtime_doc = _read("docs/RUNTIME_RFC_TEMPLATE.md")
    for phrase in [
        "axon runtime-rfc-template",
        "Runtime RFC",
        "docs/RUNTIME_BOUNDARY.md",
        "provider",
        "tool dispatch",
        "secret",
    ]:
        assert phrase in readme or phrase in cli_reference or phrase in runtime_doc
    for phrase in [
        "CURRENT BOUNDARY CHECK",
        "PROPOSED RUNTIME SCOPE",
        "SECURITY AND SECRET HANDLING",
        "TESTING STRATEGY",
    ]:
        assert phrase in runtime_doc
