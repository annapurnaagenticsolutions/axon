"""Package manager for AXON community agents and tools.

Provides ``axon add <repo>`` to fetch and install AXON packages from
GitHub or local paths into a project-local ``axon_packages`` directory.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PackageManifest:
    """Manifest for an AXON package."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    agents: list[str] = None
    tools: list[str] = None
    dependencies: list[str] = None

    def __post_init__(self) -> None:
        if self.agents is None:
            self.agents = []
        if self.tools is None:
            self.tools = []
        if self.dependencies is None:
            self.dependencies = []

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageManifest:
        return cls(
            name=data["name"],
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            dependencies=data.get("dependencies", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "agents": self.agents,
            "tools": self.tools,
            "dependencies": self.dependencies,
        }


class PackageManager:
    """Manages installation of AXON community packages."""

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root = Path(root_dir) if root_dir else Path.cwd()
        self.packages_dir = self.root / "axon_packages"
        self.packages_dir.mkdir(exist_ok=True)

    def add(self, source: str, *, branch: str | None = None) -> PackageManifest:
        """Install a package from a GitHub repo or local path."""
        if source.startswith("github.com/") or source.startswith("https://github.com/"):
            return self._add_from_github(source, branch=branch)
        src_path = Path(source)
        if src_path.exists():
            return self._add_from_local(src_path)
        raise PackageManagerError(f"Unknown package source: {source}")

    def _add_from_github(self, repo: str, branch: str | None = None) -> PackageManifest:
        """Clone a GitHub repo into the packages directory."""
        repo = repo.removeprefix("https://")
        name = repo.split("/")[-1].replace(".git", "")
        dest = self.packages_dir / name

        if dest.exists():
            shutil.rmtree(dest)

        url = f"https://{repo}.git" if not repo.endswith(".git") else f"https://{repo}"
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([url, str(dest)])

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            raise PackageManagerError("git is not installed. Install git to use 'axon add' with GitHub repos.")
        except subprocess.CalledProcessError as e:
            raise PackageManagerError(f"git clone failed: {e.stderr}")

        return self._load_manifest(dest)

    def _add_from_local(self, path: Path) -> PackageManifest:
        """Symlink or copy a local directory into the packages directory."""
        name = path.name
        dest = self.packages_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(path, dest)
        return self._load_manifest(dest)

    def _load_manifest(self, path: Path) -> PackageManifest:
        """Load or infer a package manifest."""
        manifest_path = path / "axon_package.json"
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return PackageManifest.from_dict(data)

        # Infer manifest from directory contents
        agents = [f.name for f in path.glob("*.ax") if f.is_file()]
        tools = [f.name for f in (path / "tools").glob("*.ax")] if (path / "tools").exists() else []
        return PackageManifest(
            name=path.name,
            version="0.1.0",
            agents=agents,
            tools=tools,
        )

    def list_installed(self) -> list[PackageManifest]:
        """Return all installed packages."""
        result = []
        for entry in self.packages_dir.iterdir():
            if entry.is_dir():
                try:
                    result.append(self._load_manifest(entry))
                except Exception:
                    pass
        return result

    def remove(self, name: str) -> bool:
        """Remove an installed package."""
        dest = self.packages_dir / name
        if dest.exists():
            shutil.rmtree(dest)
            return True
        return False


class PackageManagerError(Exception):
    """Error during package management."""
