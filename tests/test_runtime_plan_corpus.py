from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from axon.runtime_plan import build_runtime_plan_from_file
from axon.runtime_plan_corpus import (
    EXECUTION_CAPABILITY_NAMES,
    check_runtime_plan_corpus,
    discover_runtime_plan_sources,
    expected_runtime_plan_snapshot_path,
    format_runtime_plan_corpus_report,
    runtime_plan_corpus_report_to_json,
    runtime_plan_execution_boundary_errors,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
SNAPSHOT_DIR = ROOT / "tests" / "snapshots" / "runtime_plan" / "examples"


def test_discover_runtime_plan_sources_returns_sorted_ax_files():
    sources = discover_runtime_plan_sources(EXAMPLES_DIR)
    assert sources
    assert sources == sorted(sources)
    assert all(source.suffix == ".ax" for source in sources)
    assert EXAMPLES_DIR / "hello.ax" in sources


def test_expected_runtime_plan_snapshot_path_uses_source_stem():
    source = EXAMPLES_DIR / "hello.ax"
    expected = expected_runtime_plan_snapshot_path(source, SNAPSHOT_DIR)
    assert expected == SNAPSHOT_DIR / "hello.runtime-plan.json"


def test_runtime_plan_execution_boundary_errors_allows_current_plan():
    plan = build_runtime_plan_from_file(EXAMPLES_DIR / "github_triage.ax")
    assert runtime_plan_execution_boundary_errors(plan) == []


def test_runtime_plan_execution_boundary_errors_detects_modified_enabled_capability():
    plan = build_runtime_plan_from_file(EXAMPLES_DIR / "hello.ax")
    capabilities = list(plan.capabilities)
    # dataclasses are frozen, so create a tiny fake plan-like object by using
    # object construction is not necessary: mutate the local list via replace.
    from dataclasses import replace

    altered = replace(plan, capabilities=[replace(capabilities[0], enabled=False), *capabilities[1:]])
    errors = runtime_plan_execution_boundary_errors(altered)
    assert "capability should be enabled" in errors[0]


def test_runtime_plan_corpus_report_passes_for_repository_examples():
    report = check_runtime_plan_corpus(ROOT)
    assert report.passed, "\n".join(report.errors)
    assert report.total_sources >= 10
    assert report.total_sources == len(report.items)
    assert report.total_snapshots == report.total_sources
    assert report.orphan_snapshots == []
    assert all(item.snapshot_matched for item in report.items)
    assert all(item.execution_boundary_ok for item in report.items)


def test_runtime_plan_corpus_report_json_is_stable_and_safe():
    report = check_runtime_plan_corpus(ROOT)
    text = runtime_plan_corpus_report_to_json(report)
    data = json.loads(text)
    assert data["passed"] is True
    assert data["examples_dir"] == "examples"
    assert data["snapshot_dir"] == "tests/snapshots/runtime_plan/examples"
    assert "api_key" not in text.lower()
    assert text.endswith("\n")


def test_runtime_plan_corpus_human_report_mentions_boundary_and_snapshots():
    report = check_runtime_plan_corpus(ROOT)
    text = format_runtime_plan_corpus_report(report)
    assert "AXON runtime-plan corpus check: passed" in text
    assert "snapshot: matched" in text
    assert "execution boundary: ok" in text


def test_runtime_plan_corpus_detects_missing_snapshot_when_required(tmp_path: Path):
    examples = tmp_path / "examples"
    snapshots = tmp_path / "snapshots"
    examples.mkdir()
    snapshots.mkdir()
    (examples / "hello.ax").write_text((EXAMPLES_DIR / "hello.ax").read_text(encoding="utf-8"), encoding="utf-8")

    report = check_runtime_plan_corpus(tmp_path, examples_dir="examples", snapshot_dir="snapshots")
    assert report.passed is False
    assert any("snapshot missing" in error.lower() for error in report.errors)


def test_runtime_plan_corpus_can_allow_missing_snapshots(tmp_path: Path):
    examples = tmp_path / "examples"
    snapshots = tmp_path / "snapshots"
    examples.mkdir()
    snapshots.mkdir()
    (examples / "hello.ax").write_text((EXAMPLES_DIR / "hello.ax").read_text(encoding="utf-8"), encoding="utf-8")

    report = check_runtime_plan_corpus(
        tmp_path,
        examples_dir="examples",
        snapshot_dir="snapshots",
        require_snapshots=False,
    )
    assert report.passed is True
    assert report.warnings


def test_runtime_plan_corpus_detects_orphan_snapshot(tmp_path: Path):
    examples = tmp_path / "examples"
    snapshots = tmp_path / "snapshots"
    examples.mkdir()
    snapshots.mkdir()
    (examples / "hello.ax").write_text((EXAMPLES_DIR / "hello.ax").read_text(encoding="utf-8"), encoding="utf-8")
    # Allow the missing hello snapshot so this test focuses on orphan detection.
    (snapshots / "orphan.runtime-plan.json").write_text("{}\n", encoding="utf-8")

    report = check_runtime_plan_corpus(
        tmp_path,
        examples_dir="examples",
        snapshot_dir="snapshots",
        require_snapshots=False,
    )
    assert report.passed is False
    assert report.orphan_snapshots == ["orphan.runtime-plan.json"]


def test_all_corpus_runtime_plans_keep_execution_capabilities_disabled():
    report = check_runtime_plan_corpus(ROOT)
    assert report.passed
    for item in report.items:
        snapshot = ROOT / item.snapshot_path
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        capabilities = {capability["name"]: capability["enabled"] for capability in data["capabilities"]}
        for name in EXECUTION_CAPABILITY_NAMES:
            assert capabilities[name] is False, f"{item.source_path}: {name} should remain disabled"


def test_runtime_plan_corpus_cli_human_output():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "runtime-plan-corpus", "."],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "AXON runtime-plan corpus check: passed" in completed.stdout


def test_runtime_plan_corpus_cli_json_output():
    completed = subprocess.run(
        [sys.executable, "-m", "axon", "runtime-plan-corpus", ".", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data["passed"] is True
    assert data["total_sources"] >= 10
