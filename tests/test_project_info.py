from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from axon.project_info import collect_project_info, format_project_info, project_info_to_json

ROOT = Path(__file__).resolve().parents[1]


def test_collect_project_info_reports_core_project_files():
    report = collect_project_info(ROOT)

    assert report.config_found is True
    assert report.config_path and report.config_path.endswith("axon.toml")
    assert report.has_pyproject is True
    assert report.has_readme is True
    assert report.has_gitignore is True
    assert report.has_ci_workflow is True
    assert report.has_precommit_hook is True
    assert report.inventory.counts()["axon_files"] >= 1
    assert "examples/hello.ax" in report.inventory.example_files
    assert "docs/CLI_REFERENCE.md" in report.inventory.doc_files
    assert report.hygiene_passed in {True, False}
    assert report.dependency_audit_passed in {True, False}


def test_project_info_json_is_secret_safe_and_stable():
    report = collect_project_info(ROOT)
    payload = json.loads(project_info_to_json(report))

    assert payload["project_path"] == str(ROOT.resolve())
    assert payload["config_found"] is True
    assert "inventory" in payload
    assert "api_key" not in json.dumps(payload).lower()
    assert "ANTHROPIC_API_KEY" not in json.dumps(payload)


def test_format_project_info_is_human_readable():
    output = format_project_info(collect_project_info(ROOT))

    assert "AXON project information" in output
    assert "AXON sources:" in output
    assert "Audits:" in output
    assert "Hygiene:" in output
    assert "Dependencies:" in output


def test_collect_project_info_rejects_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        collect_project_info(tmp_path / "missing")


def test_cli_project_info_human_and_json_do_not_crash():
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"

    human = subprocess.run(
        [sys.executable, "-m", "axon", "project-info", str(ROOT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert human.returncode == 0
    assert "AXON project information" in human.stdout

    machine = subprocess.run(
        [sys.executable, "-m", "axon", "project-info", str(ROOT), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert machine.returncode == 0
    payload = json.loads(machine.stdout)
    assert payload["project_path"] == str(ROOT.resolve())
