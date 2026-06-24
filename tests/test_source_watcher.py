"""Tests for SourceWatcher and AgentReloader."""

import time
from pathlib import Path

from result import Ok

from axon.source_watcher import SourceWatcher, AgentReloader
from axon.agent_lifecycle import AgentLifecycleManager
from axon.agent_supervisor import ChildSpec


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


def test_source_watcher_detects_change(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "WatchBot")
    called_with: list[Path] = []

    watcher = SourceWatcher(poll_interval_ms=100, debounce_ms=50)
    watcher.add_file(source, lambda p: called_with.append(p))
    watcher.start()
    time.sleep(0.2)

    # Modify file
    source.write_text(source.read_text().replace("NoOp", "NoOp2"), encoding="utf-8")
    time.sleep(0.4)

    watcher.stop()
    assert len(called_with) >= 1
    assert called_with[0] == source


def test_agent_reloader_terminates_and_respawns(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "ReloaderBot")
    lifecycle = AgentLifecycleManager()
    watcher = SourceWatcher(poll_interval_ms=100, debounce_ms=50)
    reloader = AgentReloader(lifecycle, watcher)

    spec = ChildSpec(source_path=source, name="r-bot", args={"q": "hello"}, mock=True)
    reloader.watch(spec)
    watcher.start()

    # Initial spawn
    result = lifecycle.spawn(
        source_path=spec.source_path,
        name=spec.name,
        args=spec.args,
        mock=spec.mock,
    )
    assert isinstance(result, Ok)
    original_id = result.ok_value
    time.sleep(0.3)

    # Modify file to trigger reload
    source.write_text(source.read_text().replace("NoOp", "NoOp2"), encoding="utf-8")
    time.sleep(0.5)

    watcher.stop()

    # After reload, agent should exist with a different ID
    status = lifecycle.status(spec.name)
    assert isinstance(status, Ok)
    assert status.ok_value.id != original_id


def test_source_watcher_remove_file_stops_watching(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "StopBot")
    called_with: list[Path] = []

    watcher = SourceWatcher(poll_interval_ms=100, debounce_ms=50)
    watcher.add_file(source, lambda p: called_with.append(p))
    watcher.start()
    time.sleep(0.2)

    watcher.remove_file(source)
    time.sleep(0.2)

    # Modify file after removal
    source.write_text(source.read_text().replace("NoOp", "NoOp2"), encoding="utf-8")
    time.sleep(0.4)

    watcher.stop()
    assert len(called_with) == 0


def test_source_watcher_debounce_prevents_spam(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "DebounceBot")
    call_count = [0]

    # Large debounce so no callback fires during the rapid-edit burst
    watcher = SourceWatcher(poll_interval_ms=100, debounce_ms=2000)
    watcher.add_file(source, lambda p: call_count.__setitem__(0, call_count[0] + 1))
    watcher.start()
    time.sleep(0.2)

    # Rapid edits within debounce window
    for _ in range(3):
        source.write_text(source.read_text() + "\n", encoding="utf-8")
        time.sleep(0.15)

    time.sleep(0.4)
    watcher.stop()

    # First edit triggers callback; subsequent rapid edits are debounced
    assert call_count[0] == 1
