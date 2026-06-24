# RFC #022 — Secret Management & Secure Configuration

**Status:** Draft  
**Phase:** 11 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Replace ad-hoc environment-variable secret loading with a unified `SecretManager` abstraction. Providers, CLI, and the API server fetch credentials through the manager, which supports multiple backends: environment variables, `.env` files, system keyring, and HashiCorp Vault. All secret access is logged and redacted from traces.

## Motivation

Current state:
- `OpenAIProvider` hardcodes `OPENAI_API_KEY` env var
- `axon.toml` supports `${VAR}` interpolation but has no secret backend abstraction
- No audit trail for secret access
- No support for secret rotation or external vaults
- Trace emitter redacts secrets but cannot prevent them from reaching logs

## Goals

- `SecretManager` abstract base class with `get(key)`, `set(key, value)`, `exists(key)`
- `EnvSecretManager` — default, reads from `os.environ`
- `FileSecretManager` — reads from `.axon_secrets` JSON or `.env` file
- `KeyringSecretManager` — system keyring (optional extra, requires `keyring` package)
- `VaultSecretManager` — HashiCorp Vault (optional extra, requires `hvac` package)
- `ProviderConfig.get_api_key()` delegates to `SecretManager`
- Audit logging: every secret read is logged with timestamp and caller
- Trace redaction: all secret values replaced with `[REDACTED]` regardless of key name
- CLI command: `axon secret list` (redacted), `axon secret set <key> <value>`

## Non-Goals

- Automatic secret rotation
- Encrypted at-rest storage (relies on OS/filesystem/Vault)
- AWS Secrets Manager / Azure Key Vault (future additions)
- Secret generation / random password creation

## Design

### SecretManager ABC

```python
class SecretManager(ABC):
    def get(self, key: str, default: str | None = None) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def list_keys(self) -> list[str]: ...
    def close(self) -> None: ...
```

### Audit Log

Every `get()` and `set()` writes to an audit log ( SQLite persistence store or in-memory):
```python
{"timestamp": "...", "action": "get", "key": "openai_api_key", "caller": "OpenAIProvider", "success": true}
```

### Provider Integration

```python
class OpenAIProvider(ProviderPlugin):
    def __init__(self, secret_manager: SecretManager | None = None) -> None:
        self._secret_manager = secret_manager or get_default_secret_manager()
        self._config = ProviderConfig(
            name="openai",
            api_key=self._secret_manager.get("OPENAI_API_KEY"),
            ...
        )
```

## Testing Strategy

- Unit test each SecretManager backend
- Unit test audit log entries
- Unit test provider integration with mock SecretManager
- Unit test CLI `secret` commands
- Verify no secrets in trace output

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `keyring` / `hvac` not installed | Optional extras; graceful fallback to env/file |
| SecretManager singleton vs. per-request | Use `contextvars` for request-scoped override |
| Performance overhead of audit logging | Async append to in-memory buffer, flush on close |
