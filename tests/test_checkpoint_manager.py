"""Tests for CheckpointManager."""

import json
from pathlib import Path

from result import Ok, Err

from axon.agent_lifecycle import AgentLifecycleManager
from axon.checkpoint_manager import CheckpointManager, AgentStateSnapshot


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


def test_checkpoint_save_produces_valid_json(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "CkptBot")
    lifecycle = AgentLifecycleManager()
    cm = CheckpointManager(lifecycle)

    # Spawn an agent
    result = lifecycle.spawn(
        source_path=source,
        name="ckpt-bot",
        args={"q": "hello"},
        mock=True,
    )
    assert isinstance(result, Ok)

    # Checkpoint it
    output = tmp_path / "checkpoint.json"
    ckpt_result = cm.checkpoint("ckpt-bot", output_path=output)
    assert isinstance(ckpt_result, Ok)
    assert ckpt_result.ok_value == output
    assert output.exists()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["name"] == "ckpt-bot"
    assert data["source_path"] == str(source)
    assert "status" in data
    assert "config" in data


def test_checkpoint_restore_spawns_agent(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "RestoreBot")
    lifecycle = AgentLifecycleManager()
    cm = CheckpointManager(lifecycle)

    # Spawn and checkpoint
    spawn_result = lifecycle.spawn(
        source_path=source,
        name="restore-bot",
        args={"q": "hello"},
        mock=True,
    )
    assert isinstance(spawn_result, Ok)
    original_id = spawn_result.ok_value

    output = tmp_path / "checkpoint.json"
    ckpt_result = cm.checkpoint("restore-bot", output_path=output)
    assert isinstance(ckpt_result, Ok)

    # Terminate original
    lifecycle.terminate("restore-bot")

    # Restore from checkpoint
    restore_result = cm.restore("restore-bot", snapshot_path=output, mock=True)
    assert isinstance(restore_result, Ok)
    assert restore_result.ok_value != original_id

    # Verify agent exists
    status = lifecycle.status("restore-bot")
    assert isinstance(status, Ok)


def test_checkpoint_list_returns_sorted_paths(tmp_path: Path) -> None:
    lifecycle = AgentLifecycleManager()
    cm = CheckpointManager(lifecycle)

    # Create dummy checkpoint files
    ckpt_dir = tmp_path / ".axon_checkpoints"
    ckpt_dir.mkdir()
    (ckpt_dir / "a.json").write_text("{}", encoding="utf-8")
    (ckpt_dir / "b.json").write_text("{}", encoding="utf-8")

    paths = cm.list_checkpoints(ckpt_dir)
    assert len(paths) == 2
    assert all(p.suffix == ".json" for p in paths)


def test_checkpoint_for_missing_agent_returns_error(tmp_path: Path) -> None:
    lifecycle = AgentLifecycleManager()
    cm = CheckpointManager(lifecycle)

    result = cm.checkpoint("no-such-agent")
    assert isinstance(result, Err)
    assert "not found" in result.err_value.lower()
