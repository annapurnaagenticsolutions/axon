from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import axon


ROOT = Path(__file__).resolve().parents[1]


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not existing else f"{src}{os.pathsep}{existing}"
    return env


def test_pyproject_declares_console_script():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["name"] == "axon-lang"
    assert data["project"]["requires-python"] == ">=3.11"
    assert data["project"]["scripts"]["axon"] == "axon.cli:main"


def test_pyproject_declares_src_layout():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert data["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]


def test_package_version_export_matches_pyproject():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert axon.__version__ == data["project"]["version"]


def test_package_exports_parse_and_ast_nodes():
    assert callable(axon.parse)
    assert axon.ToolDecl.__name__ == "ToolDecl"
    assert axon.AgentDecl.__name__ == "AgentDecl"
    assert axon.PromptDecl.__name__ == "PromptDecl"
    assert axon.FlowDecl.__name__ == "FlowDecl"


def test_importlib_metadata_after_editable_install_if_available():
    # This test is intentionally tolerant: during normal pytest runs the package
    # may be imported via PYTHONPATH instead of an editable install.
    try:
        version = importlib.metadata.version("axon-lang")
    except importlib.metadata.PackageNotFoundError:
        return

    assert version == axon.__version__


def test_python_m_axon_help_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )

    assert completed.returncode == 0
    assert "AXON Phase 1 compiler CLI" in completed.stdout
    assert "build" in completed.stdout
    assert "serve" in completed.stdout
