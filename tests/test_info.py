from __future__ import annotations

import json
import sys
from pathlib import Path

from axon.info import (
    AxonInfo,
    collect_info,
    format_info,
    format_version,
    get_version,
    info_to_json,
    version_to_json,
)


def test_get_version_returns_project_version():
    assert get_version() == "0.1.0"


def test_format_version_is_concise():
    assert format_version("9.9.9") == "AXON 9.9.9"


def test_version_to_json_contains_version_and_package_name():
    payload = json.loads(version_to_json("1.2.3"))
    assert payload == {"package_name": "axon-lang", "version": "1.2.3"}


def test_collect_info_reports_safe_metadata(tmp_path: Path):
    (tmp_path / "axon.toml").write_text('[defaults]\nmodel = "@ollama/llama3"\n', encoding="utf-8")
    info = collect_info(project_path=tmp_path)

    assert isinstance(info, AxonInfo)
    assert info.version == "0.1.0"
    assert info.package_name == "axon-lang"
    assert info.config_found is True
    assert info.config_path == str((tmp_path / "axon.toml").resolve())
    assert info.project_path == str(tmp_path.resolve())
    assert info.python_executable == sys.executable
    assert "parser" in info.capabilities
    assert "provider-config-loader" in info.capabilities


def test_collect_info_handles_missing_config(tmp_path: Path):
    info = collect_info(project_path=tmp_path)
    assert info.config_found is False
    assert info.config_path is None


def test_info_json_is_safe_and_stable(tmp_path: Path):
    info = collect_info(project_path=tmp_path)
    payload = json.loads(info_to_json(info))

    assert payload["version"] == "0.1.0"
    assert payload["config_found"] is False
    assert "capabilities" in payload
    assert "api_key" not in json.dumps(payload).lower()


def test_format_info_contains_key_fields(tmp_path: Path):
    info = collect_info(project_path=tmp_path)
    text = format_info(info)

    assert "AXON information" in text
    assert "Version: 0.1.0" in text
    assert "Package: axon-lang" in text
    assert "Capabilities:" in text
    assert "  - parser" in text
