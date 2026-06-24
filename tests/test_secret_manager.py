"""Tests for SecretManager implementations."""

from pathlib import Path

import pytest

from axon.secret_manager import (
    EnvSecretManager,
    FileSecretManager,
    SecretAuditLog,
    get_default_secret_manager,
    reset_default_secret_manager,
)


@pytest.fixture(autouse=True)
def reset_env() -> None:
    """Reset the default secret manager before each test."""
    reset_default_secret_manager()


class TestEnvSecretManager:
    def test_get_existing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_KEY", "test_value")
        mgr = EnvSecretManager()
        assert mgr.get("TEST_KEY") == "test_value"

    def test_get_missing(self) -> None:
        mgr = EnvSecretManager()
        assert mgr.get("NONEXISTENT_KEY") is None

    def test_get_with_default(self) -> None:
        mgr = EnvSecretManager()
        assert mgr.get("NONEXISTENT_KEY", default="fallback") == "fallback"

    def test_set_and_get(self) -> None:
        mgr = EnvSecretManager()
        mgr.set("MY_KEY", "my_value")
        assert mgr.get("MY_KEY") == "my_value"

    def test_exists(self) -> None:
        mgr = EnvSecretManager()
        assert not mgr.exists("NEW_KEY")
        mgr.set("NEW_KEY", "value")
        assert mgr.exists("NEW_KEY")

    def test_delete(self) -> None:
        mgr = EnvSecretManager()
        mgr.set("DEL_KEY", "value")
        assert mgr.delete("DEL_KEY") is True
        assert not mgr.exists("DEL_KEY")
        assert mgr.delete("DEL_KEY") is False

    def test_list_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AXON_KEY1", "v1")
        monkeypatch.setenv("AXON_KEY2", "v2")
        mgr = EnvSecretManager()
        keys = mgr.list_keys()
        assert "AXON_KEY1" in keys
        assert "AXON_KEY2" in keys

    def test_audit_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUDIT_KEY", "audit_value")
        mgr = EnvSecretManager()
        mgr.get("AUDIT_KEY", caller="test")
        entries = mgr.audit_log.get_entries(key="AUDIT_KEY")
        assert len(entries) == 1
        assert entries[0].action == "get"
        assert entries[0].key == "AUDIT_KEY"
        assert entries[0].caller == "test"
        assert entries[0].success is True


class TestFileSecretManager:
    def test_json_file(self, tmp_path: Path) -> None:
        path = tmp_path / "secrets.json"
        mgr = FileSecretManager(path)
        mgr.set("key1", "value1")
        assert mgr.get("key1") == "value1"
        assert path.exists()
        # Re-load from file
        mgr2 = FileSecretManager(path)
        assert mgr2.get("key1") == "value1"

    def test_dotenv_file(self, tmp_path: Path) -> None:
        path = tmp_path / "secrets.env"
        mgr = FileSecretManager(path)
        mgr.set("ENV_KEY", "env_value")
        assert mgr.get("ENV_KEY") == "env_value"
        content = path.read_text(encoding="utf-8")
        assert "ENV_KEY=env_value" in content

    def test_delete(self, tmp_path: Path) -> None:
        path = tmp_path / "secrets.json"
        mgr = FileSecretManager(path)
        mgr.set("del", "value")
        assert mgr.delete("del") is True
        assert not mgr.exists("del")

    def test_audit(self, tmp_path: Path) -> None:
        path = tmp_path / "secrets.json"
        mgr = FileSecretManager(path)
        mgr.set("audit_key", "audit_value", caller="test_file")
        entries = mgr.audit_log.get_entries(key="audit_key")
        assert len(entries) == 1
        assert entries[0].action == "set"


class TestDefaultManager:
    def test_default_is_env(self) -> None:
        mgr = get_default_secret_manager()
        assert isinstance(mgr, EnvSecretManager)

    def test_set_default_override(self) -> None:
        custom = FileSecretManager("/tmp/test_secrets.json")
        from axon.secret_manager import set_default_secret_manager
        set_default_secret_manager(custom)
        assert get_default_secret_manager() is custom


class TestAuditLog:
    def test_record_and_get(self) -> None:
        log = SecretAuditLog()
        log.record("get", "k1", caller="c1", success=True)
        log.record("get", "k1", caller="c2", success=False)
        log.record("set", "k2", caller="c3", success=True)
        entries = log.get_entries(key="k1")
        assert len(entries) == 2
        assert entries[0].action == "get"
        assert entries[1].caller == "c2"

    def test_to_dict_list(self) -> None:
        log = SecretAuditLog()
        log.record("get", "k1", caller="c1", success=True)
        dicts = log.to_dict_list(limit=10)
        assert len(dicts) == 1
        assert dicts[0]["action"] == "get"
        assert dicts[0]["success"] is True
