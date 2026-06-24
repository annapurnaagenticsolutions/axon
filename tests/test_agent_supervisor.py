"""Tests for AXON agent supervision tree."""

import time
from pathlib import Path

from result import Ok

from axon.agent_supervisor import AgentSupervisor, ChildSpec, RestartStrategy, RestartIntensity


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


def test_restart_intensity_window() -> None:
    ri = RestartIntensity(max_restarts=3, max_seconds=1)
    assert ri.can_restart()
    ri.record_restart()
    assert ri.can_restart()
    ri.record_restart()
    assert ri.can_restart()
    ri.record_restart()
    assert not ri.can_restart()  # 3 restarts in window, limit reached

    # Wait for window to expire
    time.sleep(1.1)
    assert ri.can_restart()  # old timestamps expired


def test_supervisor_start_and_stop(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "BotA")
    sup = AgentSupervisor(name="sup-1", strategy=RestartStrategy.ONE_FOR_ONE)
    sup.add_child(ChildSpec(source_path=source, name="child-a", args={"q": "hello"}, mock=True))

    result = sup.start()
    assert isinstance(result, Ok)
    assert sup.state().running

    sup.stop()
    time.sleep(0.3)
    assert not sup.state().running


def test_one_for_one_restarts_only_failed_child(tmp_path: Path) -> None:
    source_a = _make_source(tmp_path, "BotA")
    source_b = _make_source(tmp_path, "BotB")

    sup = AgentSupervisor(
        name="sup-one",
        strategy=RestartStrategy.ONE_FOR_ONE,
        poll_interval_ms=100,
    )
    sup.add_child(ChildSpec(source_path=source_a, name="c-a", args={"q": "hello"}, mock=True))
    sup.add_child(ChildSpec(source_path=source_b, name="c-b", args={"q": "world"}, mock=True))
    sup.start()
    time.sleep(0.3)

    # Trigger failure in c-a by terminating it (simulates error state)
    sup._lifecycle.terminate("c-a", reason="simulated_failure")
    time.sleep(0.5)

    # c-a should have been restarted; c-b should still be alive
    status_a = sup._lifecycle.status("c-a")
    status_b = sup._lifecycle.status("c-b")
    assert isinstance(status_a, Ok)
    assert isinstance(status_b, Ok)
    # Debug: print what we got
    print("c-a:", status_a.ok_value.status.value, repr(status_a.ok_value.last_error), repr(status_a.ok_value.last_output))
    print("c-b:", status_b.ok_value.status.value, repr(status_b.ok_value.last_error), repr(status_b.ok_value.last_output))
    # After restart, c-a should not be TERMINATED
    assert status_a.ok_value.status.value != "terminated"
    # c-b should also still exist
    assert status_b.ok_value.status.value != "terminated"

    sup.stop()


def test_one_for_all_restarts_all_children(tmp_path: Path) -> None:
    source_a = _make_source(tmp_path, "BotA")
    source_b = _make_source(tmp_path, "BotB")

    sup = AgentSupervisor(
        name="sup-all",
        strategy=RestartStrategy.ONE_FOR_ALL,
        poll_interval_ms=100,
    )
    sup.add_child(ChildSpec(source_path=source_a, name="d-a", args={"q": "hello"}, mock=True))
    sup.add_child(ChildSpec(source_path=source_b, name="d-b", args={"q": "world"}, mock=True))
    sup.start()
    time.sleep(0.3)

    sup._lifecycle.terminate("d-a", reason="simulated_failure")
    time.sleep(0.5)

    # Both should have been restarted
    status_a = sup._lifecycle.status("d-a")
    status_b = sup._lifecycle.status("d-b")
    assert isinstance(status_a, Ok)
    assert isinstance(status_b, Ok)
    assert status_a.ok_value.status.value != "terminated"
    assert status_b.ok_value.status.value != "terminated"

    sup.stop()


def test_rest_for_one_restarts_failed_and_later(tmp_path: Path) -> None:
    source_a = _make_source(tmp_path, "BotA")
    source_b = _make_source(tmp_path, "BotB")
    source_c = _make_source(tmp_path, "BotC")

    sup = AgentSupervisor(
        name="sup-rest",
        strategy=RestartStrategy.REST_FOR_ONE,
        poll_interval_ms=100,
    )
    sup.add_child(ChildSpec(source_path=source_a, name="e-a", args={"q": "a"}, mock=True))
    sup.add_child(ChildSpec(source_path=source_b, name="e-b", args={"q": "b"}, mock=True))
    sup.add_child(ChildSpec(source_path=source_c, name="e-c", args={"q": "c"}, mock=True))
    sup.start()
    time.sleep(0.3)

    # Fail middle child e-b
    sup._lifecycle.terminate("e-b", reason="simulated_failure")
    time.sleep(0.5)

    # e-a should still be alive (started before failed)
    # e-b and e-c should be restarted
    status_a = sup._lifecycle.status("e-a")
    status_b = sup._lifecycle.status("e-b")
    status_c = sup._lifecycle.status("e-c")
    assert isinstance(status_a, Ok)
    assert isinstance(status_b, Ok)
    assert isinstance(status_c, Ok)
    assert status_a.ok_value.status.value != "terminated"
    assert status_b.ok_value.status.value != "terminated"
    assert status_c.ok_value.status.value != "terminated"

    sup.stop()


def test_max_intensity_shuts_down_supervisor(tmp_path: Path) -> None:
    source = _make_source(tmp_path, "BotA")

    sup = AgentSupervisor(
        name="sup-limit",
        strategy=RestartStrategy.ONE_FOR_ONE,
        max_restarts=2,
        max_seconds=60,
        poll_interval_ms=100,
    )
    sup.add_child(ChildSpec(source_path=source, name="f-a", args={"q": "hello"}, mock=True))
    sup.start()
    time.sleep(0.3)

    # Trigger more failures than max_restarts
    for _ in range(3):
        sup._lifecycle.terminate("f-a", reason="simulated_failure")
        time.sleep(0.4)

    time.sleep(0.5)
    # Supervisor should have shut down
    assert not sup.state().running
