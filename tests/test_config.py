from __future__ import annotations

import json
from pathlib import Path

import pytest

from axon.config import (
    ConfigError,
    AxonConfig,
    config_to_json,
    extract_env_refs,
    find_config_path,
    load_config,
    parse_model_ref,
    resolve_env_placeholders,
)
from axon.codegen.mcp import generate_mcp_server
from axon.parser import parse


CONFIG_TEXT = '''
[defaults]
model = "@anthropic/claude-haiku"
embed = "@openai/text-embed-3-large"

[sandbox]
timeout_ms = 3000
max_depth = 50
denied_tools = "DangerousTool, FileDelete"

[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[providers.ollama]
base_url = "http://localhost:11434"
'''


def test_find_config_path_walks_upward(tmp_path):
    config = tmp_path / "axon.toml"
    config.write_text(CONFIG_TEXT, encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert find_config_path(nested) == config


def test_load_config_reads_defaults_and_providers(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")

    config = load_config(path=config_path)

    assert isinstance(config, AxonConfig)
    assert config.exists
    assert config.default_model() == "@anthropic/claude-haiku"
    assert config.default("embed") == "@openai/text-embed-3-large"
    assert config.provider("anthropic").settings["api_key"] == "${ANTHROPIC_API_KEY}"
    assert config.provider("ollama").settings["base_url"] == "http://localhost:11434"


def test_load_config_returns_empty_when_implicit_missing(tmp_path):
    config = load_config(start=tmp_path)

    assert not config.exists
    assert config.defaults == {}
    assert config.providers == {}


def test_explicit_missing_config_raises(tmp_path):
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(path=tmp_path / "missing.toml")


def test_invalid_toml_raises_config_error(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text("[defaults\nmodel = 'x'", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(path=config_path)


def test_resolve_env_placeholders():
    assert resolve_env_placeholders("${TOKEN}", {"TOKEN": "abc"}) == "abc"
    assert resolve_env_placeholders("prefix-${TOKEN}", {"TOKEN": "abc"}) == "prefix-abc"


def test_resolve_env_placeholders_missing_can_be_preserved():
    assert resolve_env_placeholders("${MISSING}", {}, allow_missing=True) == "${MISSING}"


def test_resolve_env_placeholders_missing_raises():
    with pytest.raises(ConfigError, match="missing environment variable"):
        resolve_env_placeholders("${MISSING}", {})


def test_load_config_resolves_env_when_requested(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")

    config = load_config(
        path=config_path,
        resolve_env=True,
        env={"ANTHROPIC_API_KEY": "sk-test"},
        allow_missing_env=True,
    )

    assert config.provider("anthropic").settings["api_key"] == "sk-test"
    assert config.provider("ollama").settings["base_url"] == "http://localhost:11434"


def test_safe_dict_redacts_secret_values(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")

    config = load_config(path=config_path, resolve_env=True, env={"ANTHROPIC_API_KEY": "sk-real"})
    safe = config.safe_dict()

    assert safe["providers"]["anthropic"]["api_key"] == "<redacted>"
    assert "sk-real" not in json.dumps(safe)
    assert safe["providers"]["ollama"]["base_url"] == "http://localhost:11434"


def test_config_to_json_redacts_secrets(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")

    config = load_config(path=config_path, resolve_env=True, env={"ANTHROPIC_API_KEY": "sk-real"})
    data = config_to_json(config)

    assert "<redacted>" in data
    assert "sk-real" not in data


def test_parse_model_ref():
    ref = parse_model_ref("@anthropic/claude-haiku")

    assert ref.provider == "anthropic"
    assert ref.model == "claude-haiku"
    assert parse_model_ref("env.DEFAULT_MODEL") is None


def test_extract_env_refs():
    assert extract_env_refs("${A}-${B}") == ["A", "B"]


def test_generate_server_uses_config_default_for_env_model(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")
    config = load_config(path=config_path)
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello"
}
agent Bot {
    model: env.DEFAULT_MODEL
    tools: [Greet]
    fn run(q: Str) -> Str { q }
}
'''

    code = generate_mcp_server(parse(source), config=config)

    assert 'AXON_PROVIDER = os.getenv("AXON_PROVIDER", "anthropic")' in code
    assert 'AXON_MODEL    = os.getenv("AXON_MODEL",    "claude-haiku-20241022")' in code


def test_load_config_reads_sandbox_section(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")
    config = load_config(path=config_path)

    assert config.sandbox.timeout_ms == "3000"
    assert config.sandbox.max_depth == "50"
    assert config.sandbox.denied_tools == "DangerousTool, FileDelete"


def test_load_config_sandbox_safe_dict(tmp_path):
    config_path = tmp_path / "axon.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")
    config = load_config(path=config_path)
    safe = config.safe_dict()

    assert safe["sandbox"]["timeout_ms"] == "3000"
    assert safe["sandbox"]["max_depth"] == "50"
    assert safe["sandbox"]["denied_tools"] == "DangerousTool, FileDelete"


def test_load_config_empty_sandbox_when_missing(tmp_path):
    text = '[defaults]\nmodel = "@mock/gpt"\n'
    config_path = tmp_path / "axon.toml"
    config_path.write_text(text, encoding="utf-8")
    config = load_config(path=config_path)

    assert config.sandbox.timeout_ms is None
    assert config.sandbox.max_depth is None
    assert config.sandbox.denied_tools is None
