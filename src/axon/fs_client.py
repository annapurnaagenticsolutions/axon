"""Filesystem client for AXON tool dispatch.

Provides ``fs.read``, ``fs.write``, ``fs.exists``, ``fs.list``,
``fs.is_file``, and ``fs.is_dir`` builtins that AXON ``tool`` bodies can
call directly.  All paths are resolved relative to a ``base_dir`` and
``..`` traversal is rejected for sandbox safety.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FileSystem:
    """Sandboxed filesystem operations for AXON tool bodies.

    Every path is resolved relative to ``base_dir``.  Attempts to escape
    the base directory via ``..`` or absolute paths are rejected with
    ``PermissionError``.
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self._base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()

    def _resolve(self, path: str) -> Path:
        target = (self._base / path).resolve()
        # Prevent directory traversal outside base_dir
        try:
            target.relative_to(self._base)
        except ValueError:
            raise PermissionError(
                f"Path '{path}' escapes sandbox base directory: {self._base}"
            )
        return target

    def read(self, path: str) -> str:
        """Read a text file and return its contents."""
        target = self._resolve(path)
        return target.read_text(encoding="utf-8")

    def write(self, path: str, content: str) -> None:
        """Write a text file, creating parent directories if necessary."""
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def exists(self, path: str) -> bool:
        """Return whether a file or directory exists."""
        return self._resolve(path).exists()

    def list(self, path: str = ".") -> list[str]:
        """List entries in a directory relative to base_dir."""
        target = self._resolve(path)
        if not target.is_dir():
            return []
        return [str(p.relative_to(target)) for p in target.iterdir()]

    def is_file(self, path: str) -> bool:
        """Return whether the path is a file."""
        return self._resolve(path).is_file()

    def is_dir(self, path: str) -> bool:
        """Return whether the path is a directory."""
        return self._resolve(path).is_dir()


def fs_builtins(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Return the ``fs`` builtin to inject into tool scopes."""
    return {"fs": FileSystem(base_dir=base_dir)}
