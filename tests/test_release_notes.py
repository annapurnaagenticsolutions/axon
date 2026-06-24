from __future__ import annotations

import json
from pathlib import Path

from axon.release_notes import (
    ReleaseNotes,
    build_release_notes,
    discover_ax_files,
    format_release_notes,
    normalize_items,
    release_notes_to_json,
    write_release_notes,
)
from axon.cli import main, release_notes_command


def test_normalize_items_strips_empty_and_bullet_markers():
    assert normalize_items(["", " - added parser", "* fixed docs", " plain "]) == [
        "added parser",
        "fixed docs",
        "plain",
    ]


def test_discover_ax_files_returns_project_relative_paths(tmp_path: Path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "hello.ax").write_text("", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.ax").write_text("", encoding="utf-8")

    assert discover_ax_files(tmp_path) == ["examples/hello.ax"]


def test_build_release_notes_collects_safe_metadata(tmp_path: Path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "hello.ax").write_text("", encoding="utf-8")

    notes = build_release_notes(
        version="1.2.3",
        release_date="2026-05-31",
        project_path=tmp_path,
        commands=["build", "validate"],
        changes=["added release notes"],
        tests=["240 passed"],
    )

    assert isinstance(notes, ReleaseNotes)
    assert notes.version == "1.2.3"
    assert notes.date == "2026-05-31"
    assert notes.commands == ["build", "validate"]
    assert notes.changes == ["added release notes"]
    assert notes.tests == ["240 passed"]
    assert notes.ax_files == ["examples/hello.ax"]
    assert "release-notes-generator" in notes.capabilities


def test_format_release_notes_contains_changes_commands_tests_and_corpus(tmp_path: Path):
    (tmp_path / "hello.ax").write_text("", encoding="utf-8")
    notes = build_release_notes(
        version="1.2.3",
        release_date="2026-05-31",
        project_path=tmp_path,
        commands=["release-notes", "build"],
        changes=["added changelog generator"],
        tests=["241 passed"],
    )

    text = format_release_notes(notes)

    assert "# AXON Release Notes — 1.2.3" in text
    assert "Date: 2026-05-31" in text
    assert "- added changelog generator" in text
    assert "- 241 passed" in text
    assert "- axon build" in text
    assert "- axon release-notes" in text
    assert "1 `.ax` file(s)" in text
    assert "Provider secrets and API keys are not resolved or printed." in text


def test_release_notes_json_is_stable_and_safe(tmp_path: Path):
    notes = build_release_notes(
        version="1.2.3",
        release_date="2026-05-31",
        project_path=tmp_path,
        commands=["version"],
        changes=["no secrets"],
    )

    payload = json.loads(release_notes_to_json(notes))

    assert payload["version"] == "1.2.3"
    assert payload["commands"] == ["version"]
    assert payload["changes"] == ["no secrets"]
    assert "api_key" not in json.dumps(payload).lower()


def test_write_release_notes_markdown_and_json(tmp_path: Path):
    notes = build_release_notes(
        version="1.2.3",
        release_date="2026-05-31",
        project_path=tmp_path,
        changes=["wrote file"],
    )
    md = tmp_path / "RELEASE_NOTES.md"
    js = tmp_path / "release.json"

    assert write_release_notes(md, notes) == md
    assert "wrote file" in md.read_text(encoding="utf-8")

    assert write_release_notes(js, notes, json_output=True) == js
    assert json.loads(js.read_text(encoding="utf-8"))["version"] == "1.2.3"


def test_release_notes_command_returns_markdown(tmp_path: Path):
    code, output = release_notes_command(
        version="1.2.3",
        release_date="2026-05-31",
        project_path=tmp_path,
        changes=["added command"],
        tests=["241 passed"],
    )

    assert code == 0
    assert "# AXON Release Notes — 1.2.3" in output
    assert "- added command" in output
    assert "- 241 passed" in output
    assert "axon release-notes" in output


def test_release_notes_command_writes_output_file(tmp_path: Path):
    destination = tmp_path / "notes.md"

    code, output = release_notes_command(
        version="1.2.3",
        release_date="2026-05-31",
        project_path=tmp_path,
        changes=["write output"],
        output_path=destination,
    )

    assert code == 0
    assert output == f"Wrote release notes: {destination}"
    assert "write output" in destination.read_text(encoding="utf-8")


def test_main_release_notes_markdown(capsys):
    exit_code = main([
        "release-notes",
        "--version",
        "1.2.3",
        "--date",
        "2026-05-31",
        "--change",
        "added release command",
        "--tests",
        "241 passed",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "AXON Release Notes — 1.2.3" in captured.out
    assert "added release command" in captured.out
    assert "241 passed" in captured.out


def test_main_changelog_alias_json(capsys):
    exit_code = main([
        "changelog",
        "--version",
        "1.2.3",
        "--date",
        "2026-05-31",
        "--change",
        "alias works",
        "--json",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["version"] == "1.2.3"
    assert payload["changes"] == ["alias works"]
