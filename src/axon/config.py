"""AXON project configuration loader.

This module reads ``axon.toml`` without requiring any third-party packages.
It deliberately keeps API keys out of ``.ax`` files: provider credentials live
in environment variables referenced from ``axon.toml`` using ``${VAR}`` syntax.

The loader is conservative by default: it preserves placeholders instead of
resolving secrets, and all public display helpers redact secret-looking fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import json
import os
import re
import tomllib


CONFIG_FILENAME = "axon.toml"
_ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SECRET_KEYWORDS = ("api_key", "apikey", "access_token", "refresh_token", "token", "secret", "password")


class ConfigError(Exception):
    """Raised when ``axon.toml`` cannot be loaded or interpreted."""


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for one model/tool provider such as Anthropic or Ollama."""

    name: str
    settings: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.settings.get(key, default)

    def safe_settings(self) -> dict[str, str]:
        """Return provider settings with credentials redacted."""
        return {key: _redacted_value(key, value) for key, value in self.settings.items()}


@dataclass(frozen=True)
class SandboxConfigSection:
    """Sandbox configuration from axon.toml."""

    timeout_ms: str | None = None
    max_depth: str | None = None
    denied_tools: str | None = None


@dataclass(frozen=True)
class AxonConfig:
    """Loaded AXON project configuration."""

    path: Path | None = None
    defaults: dict[str, str] = field(default_factory=dict)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    sandbox: SandboxConfigSection = field(default_factory=SandboxConfigSection)

    @property
    def exists(self) -> bool:
        return self.path is not None

    def default(self, key: str, default: str | None = None) -> str | None:
        return self.defaults.get(key, default)

    def provider(self, name: str) -> ProviderConfig | None:
        return self.providers.get(name)

    def default_model(self) -> str | None:
        return self.default("model")

    def safe_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation with secrets redacted."""
        return {
            "path": str(self.path) if self.path else None,
            "defaults": dict(self.defaults),
            "providers": {
                name: provider.safe_settings()
                for name, provider in sorted(self.providers.items())
            },
            "sandbox": {
                "timeout_ms": self.sandbox.timeout_ms,
                "max_depth": self.sandbox.max_depth,
                "denied_tools": self.sandbox.denied_tools,
            },
        }


@dataclass(frozen=True)
class ModelRef:
    """Parsed ``@provider/model`` reference."""

    provider: str
    model: str


def find_config_path(start: str | Path | None = None) -> Path | None:
    """Find ``axon.toml`` by walking upward from ``start``.

    If ``start`` is a file, its parent directory is used. Returns ``None`` when
    no config file is found.
    """
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def load_config(
    path: str | Path | None = None,
    *,
    start: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    resolve_env: bool = False,
    allow_missing_env: bool = False,
) -> AxonConfig:
    """Load ``axon.toml``.

    Args:
        path: Explicit config file path. When omitted, ``find_config_path`` is
            used from ``start``. If no config is found, an empty config is
            returned.
        start: Starting path for config discovery.
        env: Environment mapping used when resolving ``${VAR}`` placeholders.
        resolve_env: If true, replace environment placeholders with values.
        allow_missing_env: If true, unresolved placeholders are preserved.

    Returns:
        ``AxonConfig``. Missing implicit config returns an empty object.

    Raises:
        ConfigError: for explicit missing paths, invalid TOML, or invalid shapes.
    """
    config_path: Path | None
    if path is not None:
        config_path = Path(path).expanduser().resolve()
        if not config_path.exists():
            raise ConfigError(f"config file not found: {config_path}")
        if not config_path.is_file():
            raise ConfigError(f"config path is not a file: {config_path}")
    else:
        config_path = find_config_path(start)
        if config_path is None:
            return AxonConfig()

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"could not read config file {config_path}: {exc}") from exc

    defaults = _read_string_table(raw.get("defaults", {}), table_name="defaults")
    provider_table = raw.get("providers", {})
    if provider_table is None:
        provider_table = {}
    if not isinstance(provider_table, dict):
        raise ConfigError("[providers] must be a TOML table")

    sandbox_table = raw.get("sandbox", {})
    if sandbox_table is None:
        sandbox_table = {}
    if not isinstance(sandbox_table, dict):
        raise ConfigError("[sandbox] must be a TOML table")
    sandbox = SandboxConfigSection(
        timeout_ms=_stringify_config_value(sandbox_table.get("timeout_ms", None), "sandbox.timeout_ms") if "timeout_ms" in sandbox_table else None,
        max_depth=_stringify_config_value(sandbox_table.get("max_depth", None), "sandbox.max_depth") if "max_depth" in sandbox_table else None,
        denied_tools=_stringify_config_value(sandbox_table.get("denied_tools", None), "sandbox.denied_tools") if "denied_tools" in sandbox_table else None,
    )

    # Backward-compatible convenience: scalar entries under [providers] are
    # treated as defaults only when [defaults] does not already define them.
    for key, value in provider_table.items():
        if not isinstance(value, dict) and key not in defaults:
            defaults[key] = _stringify_config_value(value, f"providers.{key}")

    providers: dict[str, ProviderConfig] = {}
    for name, value in provider_table.items():
        if not isinstance(value, dict):
            continue
        settings = _read_string_table(value, table_name=f"providers.{name}")
        providers[name] = ProviderConfig(name=name, settings=settings)

    if resolve_env:
        env_map = env if env is not None else os.environ
        defaults = {
            key: resolve_env_placeholders(value, env_map, allow_missing=allow_missing_env)
            for key, value in defaults.items()
        }
        providers = {
            name: ProviderConfig(
                name=name,
                settings={
                    key: resolve_env_placeholders(value, env_map, allow_missing=allow_missing_env)
                    for key, value in provider.settings.items()
                },
            )
            for name, provider in providers.items()
        }

    return AxonConfig(path=config_path, defaults=defaults, providers=providers, sandbox=sandbox)


def parse_model_ref(value: str) -> ModelRef | None:
    """Parse ``@provider/model`` into a ``ModelRef``.

    Returns ``None`` for env references or other non-provider strings.
    """
    text = value.strip()
    if not text.startswith("@") or "/" not in text:
        return None
    provider, model = text[1:].split("/", 1)
    if not provider or not model:
        return None
    return ModelRef(provider=provider, model=model)


def resolve_env_placeholders(
    value: str,
    env: Mapping[str, str] | None = None,
    *,
    allow_missing: bool = False,
) -> str:
    """Resolve ``${VAR}`` placeholders in a config string."""
    env_map = env if env is not None else os.environ

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in env_map:
            return env_map[name]
        if allow_missing:
            return match.group(0)
        raise ConfigError(f"missing environment variable: {name}")

    return _ENV_REF_RE.sub(replace, value)


def extract_env_refs(value: str) -> list[str]:
    """Return environment variable names referenced by one config value."""
    return _ENV_REF_RE.findall(value)


def config_to_json(config: AxonConfig) -> str:
    """Serialise safe config information as stable, pretty JSON."""
    return json.dumps(config.safe_dict(), indent=2, sort_keys=True)


def _read_string_table(value: Any, *, table_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"[{table_name}] must be a TOML table")
    return {
        str(key): _stringify_config_value(item, f"{table_name}.{key}")
        for key, item in value.items()
    }


def _stringify_config_value(value: Any, key_path: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raise ConfigError(f"{key_path} must be a string, number, or boolean")


def _redacted_value(key: str, value: str) -> str:
    lower = key.lower()
    if any(token in lower for token in _SECRET_KEYWORDS):
        return "<redacted>"
    return value
