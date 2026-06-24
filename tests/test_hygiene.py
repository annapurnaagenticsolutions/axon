from __future__ import annotations

import json
from pathlib import Path

from axon.hygiene import (
    DEFAULT_GITIGNORE,
    HygieneReport,
    audit_hygiene,
    format_hygiene_report,
    hygiene_report_to_json,
    read_gitignore_patterns,
    write_default_gitignore,
)


ROOT = Path(__file__).resolve().parents[1]


def test_current_project_hygiene_passes_without_errors():
    report = audit_hygiene(ROOT)
    assert isinstance(report, HygieneReport)
    assert report.passed, format_hygiene_report(report)
    assert report.error_count == 0
    assert "*.py[cod]" in report.present_patterns
    assert "*_server.py" in report.present_patterns
    assert ".env" in report.present_patterns


def test_hygiene_json_is_stable_and_secret_safe():
    report = audit_hygiene(ROOT)
    payload = json.loads(hygiene_report_to_json(report))
    assert payload["passed"] is True
    rendered = hygiene_report_to_json(report).lower()
    assert "anthropic_api_key" not in rendered
    assert "openai_api_key" not in rendered


def test_read_gitignore_patterns_ignores_comments_and_blank_lines(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("""
# comment

__pycache__/
.env
""".strip(), encoding="utf-8")
    assert read_gitignore_patterns(gitignore) == ["__pycache__/", ".env"]


def test_hygiene_detects_missing_gitignore(tmp_path: Path):
    report = audit_hygiene(tmp_path)
    assert not report.passed
    codes = {finding.code for finding in report.findings}
    assert "missing-gitignore" in codes
    assert "missing-ignore-pattern" in codes


def test_hygiene_detects_missing_required_pattern(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    report = audit_hygiene(tmp_path)
    assert not report.passed
    assert any(f.code == "missing-ignore-pattern" and f.detail == "*.py[cod]" for f in report.findings)


def test_hygiene_detects_protected_path_ignored(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(DEFAULT_GITIGNORE + "\nsrc/\n", encoding="utf-8")
    report = audit_hygiene(tmp_path)
    assert not report.passed
    assert any(f.code == "protected-path-ignored" and f.detail == "src/" for f in report.findings)


def test_hygiene_detects_local_secret_file(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(DEFAULT_GITIGNORE, encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    report = audit_hygiene(tmp_path)
    assert not report.passed
    assert any(f.code == "local-secret-present" and f.path == ".env" for f in report.findings)


def test_hygiene_allows_env_example(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(DEFAULT_GITIGNORE, encoding="utf-8")
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    report = audit_hygiene(tmp_path)
    assert report.passed, format_hygiene_report(report)


def test_hygiene_warns_for_generated_output(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(DEFAULT_GITIGNORE, encoding="utf-8")
    (tmp_path / "hello_server.py").write_text("# generated\n", encoding="utf-8")
    report = audit_hygiene(tmp_path)
    assert report.passed
    assert any(f.code == "generated-output-present" for f in report.findings)


def test_write_default_gitignore(tmp_path: Path):
    destination = write_default_gitignore(tmp_path / ".gitignore")
    assert destination.exists()
    assert "*_server.py" in destination.read_text(encoding="utf-8")


def test_write_default_gitignore_refuses_overwrite_without_force(tmp_path: Path):
    target = tmp_path / ".gitignore"
    target.write_text("custom\n", encoding="utf-8")
    try:
        write_default_gitignore(target)
    except FileExistsError as exc:
        assert "refusing to overwrite" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected FileExistsError")


def test_hygiene_cli_human_and_json(capsys):
    from axon.cli import main

    assert main(["hygiene", str(ROOT)]) == 0
    human = capsys.readouterr()
    assert "AXON repository hygiene: PASS" in human.out

    assert main(["hygiene", str(ROOT), "--json"]) == 0
    json_result = capsys.readouterr()
    payload = json.loads(json_result.out)
    assert payload["passed"] is True


def test_repo_hygiene_alias_cli(capsys):
    from axon.cli import main

    assert main(["repo-hygiene", str(ROOT)]) == 0
    result = capsys.readouterr()
    assert "AXON repository hygiene: PASS" in result.out


def test_hygiene_cli_can_write_template(tmp_path: Path, capsys):
    from axon.cli import main

    assert main(["hygiene", str(tmp_path), "--write-gitignore"]) == 0
    result = capsys.readouterr()
    assert "Wrote AXON .gitignore template" in result.out
    assert (tmp_path / ".gitignore").exists()
