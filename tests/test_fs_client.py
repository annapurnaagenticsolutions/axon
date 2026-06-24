"""Tests for AXON filesystem client builtins."""

import tempfile
from pathlib import Path

from axon.fs_client import FileSystem, fs_builtins


def test_fs_builtins_returns_dict():
    builtins = fs_builtins()
    assert "fs" in builtins
    assert isinstance(builtins["fs"], FileSystem)


def test_fs_read_write(tmp_path: Path) -> None:
    fs = FileSystem(base_dir=tmp_path)
    fs.write("hello.txt", "world")
    assert fs.read("hello.txt") == "world"


def test_fs_exists(tmp_path: Path) -> None:
    fs = FileSystem(base_dir=tmp_path)
    fs.write("a.txt", "")
    assert fs.exists("a.txt")
    assert not fs.exists("b.txt")


def test_fs_list(tmp_path: Path) -> None:
    fs = FileSystem(base_dir=tmp_path)
    fs.write("dir/a.txt", "a")
    fs.write("dir/b.txt", "b")
    entries = fs.list("dir")
    assert sorted(entries) == ["a.txt", "b.txt"]


def test_fs_is_file_and_is_dir(tmp_path: Path) -> None:
    fs = FileSystem(base_dir=tmp_path)
    fs.write("file.txt", "")
    assert fs.is_file("file.txt")
    assert not fs.is_dir("file.txt")
    assert fs.is_dir(".")
    assert not fs.is_file(".")


def test_fs_sandbox_escape_rejected(tmp_path: Path) -> None:
    fs = FileSystem(base_dir=tmp_path)
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        outside = f.name
    try:
        # Path outside base_dir should be rejected
        raised = False
        try:
            fs.read("../outside.txt")
        except PermissionError:
            raised = True
        assert raised
    finally:
        Path(outside).unlink(missing_ok=True)


def test_fs_write_creates_parents(tmp_path: Path) -> None:
    fs = FileSystem(base_dir=tmp_path)
    fs.write("deep/nested/file.txt", "content")
    assert fs.read("deep/nested/file.txt") == "content"
