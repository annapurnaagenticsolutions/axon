from __future__ import annotations

import json
from pathlib import Path

from axon.check_project import check_project, find_axon_files
from axon.cli import check_project_command, main


VALID_SOURCE = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}
agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]
    fn run(q: Str) -> Str { q }
}
'''


def test_find_axon_files_skips_hidden_and_vendor_dirs(tmp_path: Path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "hello.ax").write_text(VALID_SOURCE, encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.ax").write_text(VALID_SOURCE, encoding="utf-8")

    files = find_axon_files(tmp_path)

    assert files == [tmp_path / "examples" / "hello.ax"]


def test_check_project_passes_valid_minimal_project_without_snapshots(tmp_path: Path):
    (tmp_path / "axon.toml").write_text('[defaults]\nmodel = "@anthropic/claude-4"\n', encoding="utf-8")
    (tmp_path / "hello.ax").write_text(VALID_SOURCE, encoding="utf-8")

    report = check_project(tmp_path, no_smoke=True)

    assert report.passed
    assert report.counts()["fail"] == 0
    assert any(item.name == "config" and item.status == "pass" for item in report.items)
    assert any(item.name == "ast-snapshot" and item.status == "skip" for item in report.items)
    assert any(item.name == "smoke" and item.status == "skip" for item in report.items)


def test_check_project_fails_invalid_project(tmp_path: Path):
    (tmp_path / "bad.ax").write_text('agnt Bot { }', encoding="utf-8")

    report = check_project(tmp_path, no_smoke=True)

    assert not report.passed
    assert any(item.name == "syntax" and item.status == "fail" for item in report.items)


def test_check_project_warnings_as_errors_fails_missing_config(tmp_path: Path):
    (tmp_path / "hello.ax").write_text(VALID_SOURCE, encoding="utf-8")

    report = check_project(tmp_path, no_smoke=True, warnings_as_errors=True)

    assert not report.passed
    assert any(item.name == "config" and item.status == "warn" for item in report.items)


def test_check_project_json_is_stable(tmp_path: Path):
    (tmp_path / "hello.ax").write_text(VALID_SOURCE, encoding="utf-8")

    code, output = check_project_command(tmp_path, json_output=True, no_smoke=True)
    payload = json.loads(output)

    assert code == 0
    assert payload["passed"] is True
    assert payload["files_checked"]
    assert "counts" in payload


def test_main_check_project_command(tmp_path: Path, capsys):
    (tmp_path / "hello.ax").write_text(VALID_SOURCE, encoding="utf-8")

    exit_code = main(["check-project", str(tmp_path), "--no-smoke"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "AXON project check passed" in captured.out
    assert "Files checked: 1" in captured.out


def test_main_doctor_alias(tmp_path: Path, capsys):
    (tmp_path / "hello.ax").write_text(VALID_SOURCE, encoding="utf-8")

    exit_code = main(["doctor", str(tmp_path), "--no-smoke", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"passed": true' in captured.out


def test_check_project_full_example_corpus_passes_without_smoke_skip():
    root = Path(__file__).resolve().parents[1]

    report = check_project(root)

    assert report.passed, report.format()
    assert any(item.name == "ast-snapshot" and item.status == "pass" for item in report.items)
    assert any(item.name == "smoke" and item.status == "pass" for item in report.items)
