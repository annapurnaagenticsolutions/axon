"""Tests for runtime resilience and metrics integration."""

from __future__ import annotations

from pathlib import Path

from axon.runtime import RuntimeConfig, RuntimeExecutor


SIMPLE_SOURCE = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/model
    tools: [Greet]
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
'''


def test_runtime_collects_provider_metrics(tmp_path: Path):
    source = tmp_path / "hello.ax"
    source.write_text(SIMPLE_SOURCE, encoding="utf-8")
    cfg = RuntimeConfig(source_path=source, args={"q": "World"})
    executor = RuntimeExecutor(cfg)
    result = executor.execute()
    assert result.is_ok
    metrics = executor.get_metrics()
    # Provider calls may or may not be present depending on mock provider behavior
    assert "provider_calls" in metrics
    assert "tool_dispatches" in metrics


def test_runtime_collects_tool_dispatch_metrics(tmp_path: Path):
    source = tmp_path / "hello.ax"
    source.write_text(SIMPLE_SOURCE, encoding="utf-8")
    cfg = RuntimeConfig(source_path=source, args={"q": "World"})
    executor = RuntimeExecutor(cfg)
    result = executor.execute()
    assert result.is_ok
    metrics = executor.get_metrics()
    assert "tool_dispatches" in metrics
    # One Greet dispatch should be recorded
    dispatches = metrics.get("tool_dispatches", [])
    assert len(dispatches) >= 1
    assert any(d["tool_name"] == "Greet" for d in dispatches)
    assert all(d["success"] for d in dispatches)


def test_runtime_metrics_include_latency(tmp_path: Path):
    source = tmp_path / "hello.ax"
    source.write_text(SIMPLE_SOURCE, encoding="utf-8")
    cfg = RuntimeConfig(source_path=source, args={"q": "World"})
    executor = RuntimeExecutor(cfg)
    result = executor.execute()
    assert result.is_ok
    metrics = executor.get_metrics()
    dispatches = metrics.get("tool_dispatches", [])
    if dispatches:
        assert dispatches[0]["latency_ms"] >= 0
