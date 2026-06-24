from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from axon.runtime_plan_snapshot import (
    check_runtime_plan_snapshot_file,
    source_file_to_runtime_plan_snapshot_json,
    write_runtime_plan_snapshot_file,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "examples").glob("*.ax"))
SNAPSHOT_DIR = ROOT / "tests" / "snapshots" / "runtime_plan" / "examples"


def _snapshot_path(source: Path) -> Path:
    return SNAPSHOT_DIR / f"{source.stem}.runtime-plan.json"


def test_runtime_plan_snapshot_json_is_stable_and_normalizes_source_path():
    source = ROOT / "examples" / "hello.ax"
    text = source_file_to_runtime_plan_snapshot_json(source, root=ROOT)
    data = json.loads(text)

    assert data["source_path"] == "examples/hello.ax"
    assert data["counts"]["agents"] == 1
    assert any(cap["name"] == "declaration_inspection" and cap["enabled"] is True for cap in data["capabilities"])
    assert any(cap["name"] == "provider_calls" and cap["enabled"] is False for cap in data["capabilities"])
    assert text.endswith("\n")


def test_write_runtime_plan_snapshot_file_round_trips(tmp_path: Path):
    source = ROOT / "examples" / "github_triage.ax"
    destination = tmp_path / "github_triage.runtime-plan.json"

    written = write_runtime_plan_snapshot_file(source, destination, root=ROOT)
    assert written == destination
    assert destination.exists()

    result = check_runtime_plan_snapshot_file(source, destination, root=ROOT)
    assert result.matched, result.message
    assert "github_triage.ax" in result.actual


def test_runtime_plan_snapshot_detects_mismatch(tmp_path: Path):
    source = ROOT / "examples" / "hello.ax"
    destination = tmp_path / "hello.runtime-plan.json"
    destination.write_text('{"wrong": true}\n', encoding="utf-8")

    result = check_runtime_plan_snapshot_file(source, destination, root=ROOT)
    assert result.matched is False
    assert "mismatch" in result.message.lower()
    assert result.expected == '{"wrong": true}\n'
    assert "counts" in result.actual


def test_all_examples_have_runtime_plan_snapshots():
    missing = [source.name for source in EXAMPLES if not _snapshot_path(source).exists()]
    assert missing == []


def test_no_orphan_runtime_plan_snapshots():
    expected = {f"{source.stem}.runtime-plan.json" for source in EXAMPLES}
    actual = {path.name for path in SNAPSHOT_DIR.glob("*.runtime-plan.json")}
    assert actual == expected


def test_all_example_runtime_plan_snapshots_match_current_output():
    for source in EXAMPLES:
        result = check_runtime_plan_snapshot_file(source, _snapshot_path(source), root=ROOT)
        assert result.matched, result.message


def test_runtime_plan_snapshots_keep_execution_disabled():
    for snapshot in sorted(SNAPSHOT_DIR.glob("*.runtime-plan.json")):
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        capabilities = {item["name"]: item["enabled"] for item in data["capabilities"]}
        assert capabilities["declaration_inspection"] is True
        for capability in [
            "method_execution",
            "provider_calls",
            "tool_dispatch",
            "memory_mutation",
            "rag_indexing",
            "rag_retrieval",
            "flow_execution",
            "trace_replay",
            "secret_resolution",
            "fastmcp_runtime_import",
        ]:
            assert capabilities[capability] is False, f"{snapshot}: {capability} unexpectedly enabled"


def test_runtime_plan_cli_write_and_check_snapshot(tmp_path: Path):
    source = ROOT / "examples" / "hello.ax"
    snapshot = tmp_path / "hello.runtime-plan.json"

    write_completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "axon",
            "runtime-plan",
            str(source),
            "--write",
            str(snapshot),
            "--root",
            str(ROOT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert write_completed.returncode == 0, write_completed.stderr
    assert snapshot.exists()
    assert "Wrote runtime-plan snapshot" in write_completed.stdout

    check_completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "axon",
            "runtime-plan",
            str(source),
            "--check",
            str(snapshot),
            "--root",
            str(ROOT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert check_completed.returncode == 0, check_completed.stderr
    assert "matches" in check_completed.stdout
