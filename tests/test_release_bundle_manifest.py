from __future__ import annotations

import json
from pathlib import Path

from axon.release_bundle_manifest import (
    ReleaseBundleManifest,
    build_release_bundle_manifest,
    format_release_bundle_manifest,
    release_bundle_manifest_to_json,
    write_release_bundle_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_build_release_bundle_manifest_collects_core_artifacts():
    manifest = build_release_bundle_manifest(ROOT)
    assert isinstance(manifest, ReleaseBundleManifest)
    paths = {item.path for item in manifest.items}
    assert "README.md" in paths
    assert "CHANGELOG.md" in paths
    assert "pyproject.toml" in paths
    assert "docs/CLI_REFERENCE.md" in paths
    assert "examples/hello.ax" in paths
    assert "tests/snapshots/examples/hello.ast.json" in paths
    assert "tests/snapshots/runtime_plan/examples/hello.runtime-plan.json" in paths


def test_release_bundle_manifest_marks_generated_handoff_artifacts_as_optional():
    manifest = build_release_bundle_manifest(ROOT)
    generated = [item for item in manifest.items if item.category == "release_handoff_artifact"]
    assert generated
    assert any(item.path == "runtime-governance.json" for item in generated)
    assert any(item.path == "RUNTIME_GOVERNANCE_EVIDENCE.md" for item in generated)
    assert all(not item.required for item in generated)
    assert manifest.passed


def test_release_bundle_manifest_json_is_stable_and_secret_safe():
    manifest = build_release_bundle_manifest(ROOT)
    payload = json.loads(release_bundle_manifest_to_json(manifest))
    assert payload["passed"] is True
    assert payload["summary"]["total_items"] == len(payload["items"])
    text = json.dumps(payload).lower()
    assert "api_key" not in text
    assert "sk-" not in text
    assert "anthropic_api_key" not in text


def test_format_release_bundle_manifest_mentions_evidence_commands():
    manifest = build_release_bundle_manifest(ROOT)
    text = format_release_bundle_manifest(manifest)
    assert "AXON release bundle manifest" in text
    assert "axon runtime-governance-evidence" in text
    assert "axon release-bundle-manifest" in text
    assert "Missing required: 0" in text


def test_write_release_bundle_manifest_json_and_markdown(tmp_path: Path):
    manifest = build_release_bundle_manifest(ROOT)
    json_path = write_release_bundle_manifest(tmp_path / "manifest.json", manifest)
    md_path = write_release_bundle_manifest(tmp_path / "manifest.md", manifest)

    assert json.loads(json_path.read_text(encoding="utf-8"))["passed"] is True
    markdown = md_path.read_text(encoding="utf-8")
    assert markdown.startswith("# AXON Release Bundle Manifest")
    assert "| Category | Path | Required | Exists | Description |" in markdown
