from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_workflow_exists():
    assert WORKFLOW.exists()


def test_ci_workflow_has_safe_triggers_and_permissions():
    text = _workflow_text()
    assert "pull_request:" in text
    assert "push:" in text
    assert "workflow_dispatch:" in text
    assert "contents: read" in text


def test_ci_workflow_uses_supported_python_matrix():
    text = _workflow_text()
    assert 'python-version: ["3.11", "3.12"]' in text
    assert "actions/setup-python@v5" in text
    assert "actions/checkout@v4" in text


def test_ci_workflow_installs_dev_extra_but_not_serve_extra():
    text = _workflow_text()
    assert 'python -m pip install -e ".[dev]"' in text
    assert '.[serve]' not in text
    assert "fastmcp" not in text.lower()


def test_ci_workflow_runs_core_quality_gates():
    text = _workflow_text()
    required_commands = [
        "python -m compileall -q src tests",
        "axon deps .",
        "axon hygiene .",
        "axon check-project examples --snapshot-dir tests/snapshots/examples --require-snapshots",
        "axon format examples/hello.ax > /tmp/axon_hello_formatted.ax",
        "axon format /tmp/axon_hello_formatted.ax --check",
        "axon smoke examples/hello.ax",
        "python -m pytest",
    ]
    for command in required_commands:
        assert command in text


def test_ci_docs_describe_runtime_boundary():
    docs = (ROOT / "docs" / "CI.md").read_text(encoding="utf-8")
    assert "does **not** install the `serve` extra" in docs
    assert "call provider APIs" in docs
    assert "execute AXON agent method bodies" in docs
    assert "fake\nFastMCP harness" in docs


def test_readme_links_ci_documentation():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".github/workflows/ci.yml" in readme
    assert "docs/CI.md" in readme
