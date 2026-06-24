from __future__ import annotations

import json
import tomllib
from pathlib import Path

from axon.dependency_audit import (
    DependencyAuditReport,
    audit_dependencies,
    dependency_audit_to_json,
    format_dependency_audit,
)


ROOT = Path(__file__).resolve().parents[1]


def test_current_project_dependency_audit_passes():
    report = audit_dependencies(ROOT)
    assert isinstance(report, DependencyAuditReport)
    assert report.passed, format_dependency_audit(report)
    assert report.error_count == 0
    assert "serve" in report.optional_dependencies
    assert "dev" in report.optional_dependencies
    assert report.core_dependencies == []
    assert any(path.endswith("cli.py") for path in report.scanned_source_files)


def test_pyproject_keeps_core_dependencies_empty_and_runtime_deps_optional():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []
    optional = data["project"]["optional-dependencies"]
    assert any(dep.lower().startswith("fastmcp") for dep in optional["serve"])
    assert any(dep.lower().startswith("pytest") for dep in optional["dev"])


def test_dependency_audit_json_is_stable_and_secret_safe():
    report = audit_dependencies(ROOT)
    payload = json.loads(dependency_audit_to_json(report))
    assert payload["passed"] is True
    assert payload["core_dependencies"] == []
    rendered = dependency_audit_to_json(report).lower()
    assert "anthropic_api_key" not in rendered
    assert "openai_api_key" not in rendered


def test_dependency_audit_detects_core_dependency(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "bad-axon"
version = "0.1.0"
dependencies = ["fastmcp>=0.4.0"]

[project.optional-dependencies]
serve = ["fastmcp>=0.4.0"]
dev = ["pytest>=8.0"]
""".strip(),
        encoding="utf-8",
    )
    src = tmp_path / "src" / "axon"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        'python -m pip install -e ".[dev]"\n'
        'python -m pip install -e ".[serve]"\n'
        "The compiler itself does not require FastMCP\n",
        encoding="utf-8",
    )

    report = audit_dependencies(tmp_path)
    assert not report.passed
    codes = {finding.code for finding in report.findings}
    assert "core-dependencies-not-empty" in codes
    assert "disallowed-core-dependency" in codes


def test_dependency_audit_detects_external_source_import(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "bad-axon"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
serve = ["fastmcp>=0.4.0"]
dev = ["pytest>=8.0"]
""".strip(),
        encoding="utf-8",
    )
    src = tmp_path / "src" / "axon"
    src.mkdir(parents=True)
    (src / "bad.py").write_text("import requests\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        'python -m pip install -e ".[dev]"\n'
        'python -m pip install -e ".[serve]"\n'
        "The compiler itself does not require FastMCP\n",
        encoding="utf-8",
    )

    report = audit_dependencies(tmp_path)
    assert not report.passed
    assert any(finding.code == "external-source-import" and finding.detail == "requests" for finding in report.findings)


def test_dependency_audit_detects_provider_sdk_import(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "bad-axon"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
serve = ["fastmcp>=0.4.0"]
dev = ["pytest>=8.0"]
""".strip(),
        encoding="utf-8",
    )
    src = tmp_path / "src" / "axon"
    src.mkdir(parents=True)
    (src / "provider.py").write_text("import openai\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        'python -m pip install -e ".[dev]"\n'
        'python -m pip install -e ".[serve]"\n'
        "The compiler itself does not require FastMCP\n",
        encoding="utf-8",
    )

    report = audit_dependencies(tmp_path)
    assert not report.passed
    assert any(finding.code == "provider-sdk-import-in-core" and finding.detail == "openai" for finding in report.findings)


def test_dependency_audit_cli_human_and_json(capsys):
    from axon.cli import main

    assert main(["deps", str(ROOT)]) == 0
    human = capsys.readouterr()
    assert "AXON dependency audit: PASS" in human.out

    assert main(["deps", str(ROOT), "--json"]) == 0
    json_result = capsys.readouterr()
    payload = json.loads(json_result.out)
    assert payload["passed"] is True
    assert payload["core_dependencies"] == []


def test_dependency_audit_alias_cli(capsys):
    from axon.cli import main

    assert main(["dependency-audit", str(ROOT)]) == 0
    result = capsys.readouterr()
    assert "AXON dependency audit: PASS" in result.out
