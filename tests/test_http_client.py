"""Tests for AXON HTTP client builtins."""

from axon.http_client import HttpClient, EnvProxy, http_builtins, _try_parse_json


def test_try_parse_json_valid():
    assert _try_parse_json('{"a": 1}') == {"a": 1}


def test_try_parse_json_invalid():
    assert _try_parse_json("not json") == "not json"


def test_env_proxy_get_existing(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "test_value")
    env = EnvProxy()
    assert env.TEST_KEY == "test_value"
    assert env["TEST_KEY"] == "test_value"
    assert env.get("TEST_KEY") == "test_value"


def test_env_proxy_get_missing():
    env = EnvProxy()
    assert env.MISSING_VAR is None
    assert env["MISSING_VAR"] is None
    assert env.get("MISSING_VAR", "default") == "default"


def test_http_builtins_keys():
    builtins = http_builtins()
    assert "http" in builtins
    assert "env" in builtins
    assert isinstance(builtins["http"], HttpClient)
    assert isinstance(builtins["env"], EnvProxy)


def test_http_client_mocked_get(monkeypatch):
    import json
    import urllib.request
    from io import BytesIO

    class FakeResponse:
        status = 200

        def read(self):
            return BytesIO(json.dumps({"ok": True}).encode()).read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def getheaders(self):
            return [("Content-Type", "application/json")]

        def get_content_charset(self, failobj="utf-8"):
            return "utf-8"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    client = HttpClient()
    result = client.get("http://example.com/api")
    assert result == {"ok": True}


def test_http_client_mocked_post(monkeypatch):
    import json
    import urllib.request
    from io import BytesIO

    captured = {}

    class FakeResponse:
        status = 201

        def read(self):
            return BytesIO(json.dumps({"created": True}).encode()).read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def getheaders(self):
            return [("Content-Type", "application/json")]

        def get_content_charset(self, failobj="utf-8"):
            return "utf-8"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    client = HttpClient()
    result = client.post("http://example.com/api", data={"name": "test"})
    assert result == {"created": True}
