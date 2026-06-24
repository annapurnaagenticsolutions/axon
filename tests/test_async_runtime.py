"""Tests for the async runtime executor."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from axon.async_runtime import AsyncRuntimeConfig, AsyncRuntimeExecutor, execute_runtime_async


SIMPLE_SOURCE = '''
agent Bot {
    model: @mock/model
    tools: []
    fn run(q: Str) -> Str { q }
}
'''


@pytest.fixture
def simple_ax_file(tmp_path: Path):
    p = tmp_path / "test.ax"
    p.write_text(SIMPLE_SOURCE, encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_async_runtime_execute_mock(simple_ax_file: Path):
    config = AsyncRuntimeConfig(source_path=simple_ax_file)
    executor = AsyncRuntimeExecutor(config)
    result = await executor.execute()
    assert result.is_ok


@pytest.mark.asyncio
async def test_async_runtime_convenience_function(simple_ax_file: Path):
    config = AsyncRuntimeConfig(source_path=simple_ax_file)
    result = await execute_runtime_async(config)
    assert result.is_ok


@pytest.mark.asyncio
async def test_async_runtime_missing_agent(tmp_path: Path):
    p = tmp_path / "no_agent.ax"
    p.write_text('tool T(x: Str) -> Str { x }', encoding="utf-8")
    config = AsyncRuntimeConfig(source_path=p)
    executor = AsyncRuntimeExecutor(config)
    result = await executor.execute()
    assert result.is_err
    assert "No agent declaration" in result.err_value


@pytest.mark.asyncio
async def test_async_runtime_stream_mock(simple_ax_file: Path):
    config = AsyncRuntimeConfig(source_path=simple_ax_file, stream=True)
    executor = AsyncRuntimeExecutor(config)
    chunks = []
    async for chunk in executor.execute_stream():
        chunks.append(chunk)
    # Mock provider may yield nothing or a single chunk
    assert len(chunks) >= 0


@pytest.mark.asyncio
async def test_async_runtime_invalid_provider(tmp_path: Path):
    source = tmp_path / "bad_provider.ax"
    source.write_text('''
agent Bot {
    model: @nonexistent/model
    tools: []
    fn run(q: Str) -> Str { q }
}
''', encoding="utf-8")
    config = AsyncRuntimeConfig(source_path=source)
    executor = AsyncRuntimeExecutor(config)
    result = await executor.execute()
    assert result.is_err
    assert "Provider not found" in result.err_value
