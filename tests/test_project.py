from __future__ import annotations

from pathlib import Path

import pytest

from axon.cli import main
from axon.project import ProjectInitError, create_project, init_project


def test_create_project_creates_skeleton(tmp_path):
    project = tmp_path / "demo"

    result = create_project(project)

    assert result.path == project.resolve()
    assert (project / "axon.toml").exists()
    assert (project / "examples" / "hello.ax").exists()
    assert (project / "README.md").exists()
    assert (project / ".gitignore").exists()
    assert (project / "traces" / ".gitkeep").exists()
    assert Path("axon.toml") in result.created
    assert Path("examples/hello.ax") in result.created
    assert "${ANTHROPIC_API_KEY}" in (project / "axon.toml").read_text(encoding="utf-8")


def test_create_project_refuses_non_empty_directory_without_force(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "existing.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ProjectInitError, match="not empty"):
        create_project(project)



def test_create_project_force_adds_starter_files_to_non_empty_directory(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "existing.txt").write_text("keep", encoding="utf-8")

    result = create_project(project, force=True)

    assert (project / "existing.txt").read_text(encoding="utf-8") == "keep"
    assert (project / "axon.toml").exists()
    assert Path("axon.toml") in result.created



def test_init_project_preserves_existing_files_without_force(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    config = project / "axon.toml"
    config.write_text("[defaults]\nmodel = \"@custom/model\"\n", encoding="utf-8")

    result = init_project(project)

    assert Path("axon.toml") in result.skipped
    assert config.read_text(encoding="utf-8") == "[defaults]\nmodel = \"@custom/model\"\n"
    assert (project / "examples" / "hello.ax").exists()



def test_init_project_force_overwrites_known_starter_files(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    config = project / "axon.toml"
    config.write_text("old", encoding="utf-8")

    result = init_project(project, force=True)

    assert Path("axon.toml") in result.overwritten
    assert "[defaults]" in config.read_text(encoding="utf-8")



def test_create_project_rejects_file_target(tmp_path):
    target = tmp_path / "not-dir"
    target.write_text("x", encoding="utf-8")

    with pytest.raises(ProjectInitError, match="not a directory"):
        create_project(target)



def test_main_new_command(tmp_path, capsys):
    project = tmp_path / "demo"

    exit_code = main(["new", str(project)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "AXON project ready" in captured.out
    assert (project / "axon.toml").exists()
    assert (project / "examples" / "hello.ax").exists()



def test_main_new_command_non_empty_returns_error(tmp_path, capsys):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "existing.txt").write_text("keep", encoding="utf-8")

    exit_code = main(["new", str(project)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "not empty" in captured.err



def test_main_init_command_existing_directory(tmp_path, capsys):
    project = tmp_path / "demo"
    project.mkdir()

    exit_code = main(["init", str(project)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "AXON project ready" in captured.out
    assert (project / "axon.toml").exists()



def test_initialized_hello_file_validates_and_smokes(tmp_path, capsys):
    project = tmp_path / "demo"
    create_project(project)
    hello = project / "examples" / "hello.ax"

    validate_code = main(["validate", str(hello)])
    validate_out = capsys.readouterr()
    smoke_code = main(["smoke", str(hello)])
    smoke_out = capsys.readouterr()

    assert validate_code == 0
    assert "passed AXON validation" in validate_out.out
    assert smoke_code == 0
    assert "passed AXON smoke test" in smoke_out.out
