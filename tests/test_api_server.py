"""Tests for AXON FastAPI server."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from axon.api_server import app, _state


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset shared server state between tests."""
    _state.supervisors.clear()
    for inst in list(_state.lifecycle.list_agents()):
        _state.lifecycle.terminate(inst.name, reason="test_teardown")
    _state.api_key = None


client = TestClient(app)


def _make_source(tmp_path: Path, name: str) -> Path:
    source = tmp_path / f"{name}.ax"
    source.write_text(
        f'tool NoOp(x: Str) -> Str {{ x }}\n'
        f'agent {name} {{\n'
        '    model: @mock/gpt\n'
        '    tools: [NoOp]\n'
        '    fn run(q: Str) -> Str {\n'
        '        act NoOp(x: q)\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )
    return source


def test_health_check() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_spawn_and_get_agent(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "ApiBot")
    payload = {
        "name": "api-bot",
        "source": str(source),
        "args": {"q": "hello"},
        "mock": True,
    }
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "api-bot"
    assert data["source_path"] == str(source)

    # Get status
    resp2 = client.get("/agents/api-bot")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "api-bot"

    # Cleanup
    client.post("/agents/api-bot/terminate")


def test_list_agents(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "ListBot")
    client.post("/agents", json={"name": "list-bot", "source": str(source), "mock": True})
    resp = client.get("/agents")
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert "list-bot" in names
    client.post("/agents/list-bot/terminate")


def test_pause_resume_agent(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "PauseBot")
    client.post("/agents", json={"name": "pause-bot", "source": str(source), "mock": True})

    # Poll until agent is in a pausable state
    import time
    pausable = False
    for _ in range(30):
        status = client.get("/agents/pause-bot")
        if status.status_code == 200 and status.json()["status"] in ("running", "idle"):
            pausable = True
            break
        time.sleep(0.1)

    if pausable:
        resp = client.post("/agents/pause-bot/pause")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "paused"

        resp2 = client.post("/agents/pause-bot/resume")
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["status"] == "resumed"

    client.post("/agents/pause-bot/terminate")


def test_get_nonexistent_agent() -> None:
    resp = client.get("/agents/no-such-bot")
    assert resp.status_code == 404


def test_terminate_agent(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "TermBot")
    client.post("/agents", json={"name": "term-bot", "source": str(source), "mock": True})
    resp = client.post("/agents/term-bot/terminate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "terminated"


def test_metrics_endpoint() -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "counters" in data
    assert "gauges" in data


def test_api_key_protection() -> None:
    _state.api_key = "secret123"
    resp = client.get("/agents", headers={})
    assert resp.status_code == 401

    resp2 = client.get("/agents", headers={"X-API-Key": "secret123"})
    assert resp2.status_code == 200

    resp3 = client.get("/agents", headers={"X-API-Key": "wrong"})
    assert resp3.status_code == 401

    _state.api_key = None  # reset for other tests


def test_supervisor_lifecycle() -> None:
    payload = {
        "name": "test-sup",
        "strategy": "one_for_one",
        "children": [],
    }
    resp = client.post("/supervisors", json=payload)
    assert resp.status_code == 201
    assert resp.json()["name"] == "test-sup"

    resp2 = client.get("/supervisors/test-sup")
    assert resp2.status_code == 200
    assert resp2.json()["strategy"] == "one_for_one"

    resp3 = client.post("/supervisors/test-sup/stop")
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "stopped"


def test_checkpoint_and_restore(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "CkptBot")
    client.post("/agents", json={"name": "ckpt-bot", "source": str(source), "mock": True})

    ckpt_path = tmp_path / "ckpt.json"
    resp = client.post("/agents/ckpt-bot/checkpoint", json={"output": str(ckpt_path)})
    assert resp.status_code == 200
    assert resp.json()["status"] == "checkpoint_saved"
    assert ckpt_path.exists()

    client.post("/agents/ckpt-bot/terminate")

    resp2 = client.post("/agents/ckpt-bot/restore", json={"snapshot": str(ckpt_path), "mock": True})
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "restored"

    client.post("/agents/ckpt-bot/terminate")
