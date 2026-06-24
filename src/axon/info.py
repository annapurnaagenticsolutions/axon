"""Version and environment metadata for AXON.

This module intentionally reports deterministic, non-secret project metadata. It is
used by `axon version` and `axon info` so bug reports can identify the AXON build
and local execution environment without exposing provider keys or runtime secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.metadata
import json
import platform as platform_module
import sys
from pathlib import Path
from typing import Any

from axon.config import find_config_path

PACKAGE_NAME = "axon-lang"
FALLBACK_VERSION = "0.1.0"

CAPABILITIES = [
    "parser",
    "validator",
    "syntax-diagnostics",
    "ast-snapshots",
    "golden-error-snapshots",
    "fastmcp-codegen",
    "generated-server-smoke-test",
    "provider-config-loader",
    "project-init",
    "project-info",
    "project-quality-gate",
    "release-notes-generator",
    "release-handoff-checklist",
    "contributor-task-template",
    "source-formatter",
    "formatter-golden-snapshots",
    "dependency-audit",
    "ael-trace-model",
    "ael-trace-preview",
    "ael-trace-reader",
]


@dataclass(frozen=True)
class AxonInfo:
    """Safe AXON version and runtime metadata."""

    package_name: str
    version: str
    python_version: str
    python_executable: str
    platform: str
    module_path: str
    cwd: str
    project_path: str
    config_path: str | None
    capabilities: list[str] = field(default_factory=list)

    @property
    def config_found(self) -> bool:
        """Whether an axon.toml configuration file was discovered."""
        return self.config_path is not None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "package_name": self.package_name,
            "version": self.version,
            "python_version": self.python_version,
            "python_executable": self.python_executable,
            "platform": self.platform,
            "module_path": self.module_path,
            "cwd": self.cwd,
            "project_path": self.project_path,
            "config_path": self.config_path,
            "config_found": self.config_found,
            "capabilities": list(self.capabilities),
        }


def get_version(package_name: str = PACKAGE_NAME) -> str:
    """Return the installed AXON package version.

    During editable or source-tree execution, package metadata may not be
    installed yet. In that case we return the prototype fallback version used by
    `src/axon/__init__.py` and `pyproject.toml`.
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return FALLBACK_VERSION


def collect_info(
    project_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> AxonInfo:
    """Collect safe AXON environment metadata.

    Args:
        project_path: Directory used as the project/cwd reference. Defaults to
            the current working directory.
        config_path: Optional explicit axon.toml path. If omitted, AXON searches
            upward from project_path.
    """
    project = Path(project_path or Path.cwd()).expanduser().resolve()
    config: Path | None
    if config_path is not None:
        candidate = Path(config_path).expanduser().resolve()
        config = candidate if candidate.exists() else None
    else:
        config = find_config_path(project)

    module_file = Path(__file__).resolve()
    return AxonInfo(
        package_name=PACKAGE_NAME,
        version=get_version(),
        python_version=platform_module.python_version(),
        python_executable=sys.executable,
        platform=platform_module.platform(),
        module_path=str(module_file.parent),
        cwd=str(Path.cwd().resolve()),
        project_path=str(project),
        config_path=str(config) if config is not None else None,
        capabilities=list(CAPABILITIES),
    )


def info_to_json(info: AxonInfo) -> str:
    """Render AXON info as stable JSON."""
    return json.dumps(info.to_dict(), indent=2, sort_keys=True)


def format_version(version: str | None = None, package_name: str = PACKAGE_NAME) -> str:
    """Render a concise version line for humans."""
    return f"AXON {version or get_version(package_name)}"


def version_to_json(version: str | None = None, package_name: str = PACKAGE_NAME) -> str:
    """Render version metadata as JSON."""
    payload = {
        "package_name": package_name,
        "version": version or get_version(package_name),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def format_info(info: AxonInfo) -> str:
    """Render AXON info as a human-readable report."""
    lines = [
        "AXON information",
        f"Version: {info.version}",
        f"Package: {info.package_name}",
        f"Python: {info.python_version}",
        f"Platform: {info.platform}",
        f"Executable: {info.python_executable}",
        f"Module: {info.module_path}",
        f"Current directory: {info.cwd}",
        f"Project: {info.project_path}",
        f"Config: {info.config_path if info.config_path else '<not found>'}",
        "Capabilities:",
    ]
    lines.extend(f"  - {capability}" for capability in info.capabilities)
    return "\n".join(lines)
