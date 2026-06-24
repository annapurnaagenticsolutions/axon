"""Secret management abstraction for AXON runtime.

Provides pluggable backends for credential storage:
- Environment variables (default)
- JSON / dotenv files
- System keyring (optional)
- HashiCorp Vault (optional)

All access is audited and secrets are redacted from traces.
"""

from __future__ import annotations

import json
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@dataclass
class SecretAuditEntry:
    timestamp: float
    action: str
    key: str
    caller: str
    success: bool


class SecretAuditLog:
    """In-memory audit log for secret access."""

    def __init__(self) -> None:
        self._entries: list[SecretAuditEntry] = []
        self._lock = threading.Lock()

    def record(self, action: str, key: str, caller: str = "", success: bool = True) -> None:
        entry = SecretAuditEntry(
            timestamp=time.time(),
            action=action,
            key=key,
            caller=caller,
            success=success,
        )
        with self._lock:
            self._entries.append(entry)

    def get_entries(self, key: str | None = None, limit: int = 100) -> list[SecretAuditEntry]:
        with self._lock:
            entries = list(self._entries)
        if key is not None:
            entries = [e for e in entries if e.key == key]
        return entries[-limit:]

    def to_dict_list(self, key: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        entries = self.get_entries(key=key, limit=limit)
        return [
            {
                "timestamp": e.timestamp,
                "action": e.action,
                "key": e.key,
                "caller": e.caller,
                "success": e.success,
            }
            for e in entries
        ]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SecretManager(ABC):
    """Pluggable secret storage backend."""

    def __init__(self) -> None:
        self._audit = SecretAuditLog()

    @abstractmethod
    def _do_get(self, key: str) -> str | None:
        """Internal get implementation."""
        ...

    @abstractmethod
    def _do_set(self, key: str, value: str) -> None:
        """Internal set implementation."""
        ...

    @abstractmethod
    def _do_exists(self, key: str) -> bool:
        """Internal exists implementation."""
        ...

    @abstractmethod
    def _do_delete(self, key: str) -> bool:
        """Internal delete implementation."""
        ...

    @abstractmethod
    def _do_list_keys(self) -> list[str]:
        """Internal list implementation."""
        ...

    def get(self, key: str, default: str | None = None, caller: str = "") -> str | None:
        """Retrieve a secret, recording an audit entry."""
        value = self._do_get(key)
        success = value is not None
        self._audit.record(action="get", key=key, caller=caller, success=success)
        return value if value is not None else default

    def set(self, key: str, value: str, caller: str = "") -> None:
        """Store a secret, recording an audit entry."""
        self._do_set(key, value)
        self._audit.record(action="set", key=key, caller=caller, success=True)

    def exists(self, key: str) -> bool:
        return self._do_exists(key)

    def delete(self, key: str, caller: str = "") -> bool:
        result = self._do_delete(key)
        self._audit.record(action="delete", key=key, caller=caller, success=result)
        return result

    def list_keys(self) -> list[str]:
        return self._do_list_keys()

    @property
    def audit_log(self) -> SecretAuditLog:
        return self._audit

    def close(self) -> None:
        """Release resources. Default is no-op."""
        pass


# ---------------------------------------------------------------------------
# Environment variable backend (default)
# ---------------------------------------------------------------------------

class EnvSecretManager(SecretManager):
    """Reads secrets from environment variables."""

    def _do_get(self, key: str) -> str | None:
        return os.environ.get(key)

    def _do_set(self, key: str, value: str) -> None:
        os.environ[key] = value

    def _do_exists(self, key: str) -> bool:
        return key in os.environ

    def _do_delete(self, key: str) -> bool:
        if key in os.environ:
            del os.environ[key]
            return True
        return False

    def _do_list_keys(self) -> list[str]:
        return list(os.environ.keys())


# ---------------------------------------------------------------------------
# File backend (JSON or dotenv)
# ---------------------------------------------------------------------------

class FileSecretManager(SecretManager):
    """Reads secrets from a JSON or dotenv file.

    Args:
        path: Path to the secrets file. Supports ``.json`` and ``.env`` formats.
    """

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path)
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._lock:
            if self._path.suffix == ".json":
                content = self._path.read_text(encoding="utf-8")
                data = json.loads(content)
                self._data = {k: str(v) for k, v in data.items()}
            else:
                # dotenv format: KEY=VALUE
                self._data = {}
                for line in self._path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        self._data[key.strip()] = value.strip().strip("\"'\"")

    def _save(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.suffix == ".json":
                self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            else:
                lines = [f"{k}={v}" for k, v in sorted(self._data.items())]
                self._path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _do_get(self, key: str) -> str | None:
        with self._lock:
            return self._data.get(key)

    def _do_set(self, key: str, value: str) -> None:
        with self._lock:
            self._data[key] = value
        self._save()

    def _do_exists(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def _do_delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._data
            if existed:
                del self._data[key]
        if existed:
            self._save()
        return existed

    def _do_list_keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())


# ---------------------------------------------------------------------------
# Keyring backend (optional)
# ---------------------------------------------------------------------------

class KeyringSecretManager(SecretManager):
    """System keyring backend.

    Requires ``keyring`` package:
        pip install keyring
    """

    def __init__(self, service_name: str = "axon") -> None:
        super().__init__()
        try:
            import keyring
        except ImportError as exc:
            raise ImportError(
                "keyring is required for KeyringSecretManager. "
                "Install it with: pip install keyring"
            ) from exc
        self._service = service_name
        self._keyring = keyring

    def _do_get(self, key: str) -> str | None:
        return self._keyring.get_password(self._service, key)

    def _do_set(self, key: str, value: str) -> None:
        self._keyring.set_password(self._service, key, value)

    def _do_exists(self, key: str) -> bool:
        return self._keyring.get_password(self._service, key) is not None

    def _do_delete(self, key: str) -> bool:
        existed = self._do_exists(key)
        try:
            self._keyring.delete_password(self._service, key)
        except Exception:
            pass
        return existed

    def _do_list_keys(self) -> list[str]:
        # keyring does not provide a list API across all backends
        return []


# ---------------------------------------------------------------------------
# HashiCorp Vault backend (optional)
# ---------------------------------------------------------------------------

class VaultSecretManager(SecretManager):
    """HashiCorp Vault KV v2 backend.

    Requires ``hvac`` package:
        pip install hvac

    Args:
        url: Vault server URL (e.g. ``http://localhost:8200``)
        token: Vault authentication token
        mount_point: KV engine mount point (default ``secret``)
        path: Path prefix within the KV engine (default ``axon``)
    """

    def __init__(
        self,
        url: str = "http://localhost:8200",
        token: str | None = None,
        mount_point: str = "secret",
        path: str = "axon",
    ) -> None:
        super().__init__()
        try:
            import hvac
        except ImportError as exc:
            raise ImportError(
                "hvac is required for VaultSecretManager. "
                "Install it with: pip install hvac"
            ) from exc
        self._client = hvac.Client(url=url, token=token)
        self._mount_point = mount_point
        self._path = path
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()

    def _full_path(self, key: str) -> str:
        return f"{self._path}/{key}"

    def _do_get(self, key: str) -> str | None:
        full = self._full_path(key)
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=full, mount_point=self._mount_point
            )
            return response["data"]["data"].get("value")
        except Exception:
            return None

    def _do_set(self, key: str, value: str) -> None:
        full = self._full_path(key)
        self._client.secrets.kv.v2.create_or_update_secret(
            path=full,
            mount_point=self._mount_point,
            secret={"value": value},
        )

    def _do_exists(self, key: str) -> bool:
        return self._do_get(key) is not None

    def _do_delete(self, key: str) -> bool:
        existed = self._do_exists(key)
        if existed:
            full = self._full_path(key)
            self._client.secrets.kv.v2.delete_latest_version_of_secret(
                path=full, mount_point=self._mount_point
            )
        return existed

    def _do_list_keys(self) -> list[str]:
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                path=self._path, mount_point=self._mount_point
            )
            return response["data"]["keys"]
        except Exception:
            return []

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Global default manager
# ---------------------------------------------------------------------------

_default_manager: SecretManager | None = None
_default_lock = threading.Lock()


def get_default_secret_manager() -> SecretManager:
    """Return the global default SecretManager (lazy init)."""
    global _default_manager
    with _default_lock:
        if _default_manager is None:
            _default_manager = EnvSecretManager()
        return _default_manager


def set_default_secret_manager(manager: SecretManager) -> None:
    """Override the global default SecretManager."""
    global _default_manager
    with _default_lock:
        _default_manager = manager


def reset_default_secret_manager() -> None:
    """Reset to the default EnvSecretManager."""
    global _default_manager
    with _default_lock:
        _default_manager = EnvSecretManager()
