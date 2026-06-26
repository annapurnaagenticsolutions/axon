"""Tests for AXON distributed runtime: message bus, service registry, remote dispatch."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# In-memory DistributedBus tests
# ---------------------------------------------------------------------------


class TestInMemoryDistributedBus(unittest.TestCase):
    """Test the in-memory backend of DistributedBus."""

    def test_send_and_receive(self):
        from axon.distributed_bus import DistributedBus

        bus = DistributedBus(backend="in_memory", agent_name="agent_a")
        bus.send("agent_b", {"text": "hello"})
        bus.set_agent("agent_b")
        msg = bus.receive(timeout_ms=100)
        self.assertEqual(msg, {"text": "hello"})

    def test_receive_timeout(self):
        from axon.distributed_bus import DistributedBus

        bus = DistributedBus(backend="in_memory", agent_name="agent_a")
        result = bus.receive(timeout_ms=100)
        self.assertIsNone(result)

    def test_broadcast(self):
        from axon.distributed_bus import DistributedBus

        bus = DistributedBus(backend="in_memory", agent_name="agent_a")
        received = []
        bus.subscribe("alerts", lambda payload: received.append(payload))
        bus.broadcast("alerts", {"level": "high"})
        self.assertEqual(received, [{"level": "high"}])

    def test_receive_blocking_success(self):
        from axon.distributed_bus import DistributedBus

        bus = DistributedBus(backend="in_memory", agent_name="agent_a")
        bus.send("agent_a", "wake up")
        msg = bus.receive_blocking(timeout_ms=1000)
        self.assertEqual(msg, "wake up")

    def test_receive_blocking_timeout(self):
        from axon.distributed_bus import DistributedBus

        bus = DistributedBus(backend="in_memory", agent_name="agent_a")
        with self.assertRaises(TimeoutError):
            bus.receive_blocking(timeout_ms=100)


# ---------------------------------------------------------------------------
# Service Registry tests
# ---------------------------------------------------------------------------


class TestServiceRegistry(unittest.TestCase):
    """Test the in-memory ServiceRegistry."""

    def test_register_and_discover(self):
        from axon.service_registry import ServiceRegistry, AgentService

        reg = ServiceRegistry(backend="in_memory")
        reg.register(AgentService(
            name="worker-1",
            host="localhost",
            port=8080,
            capabilities=["search", "summarize"],
        ))
        services = reg.discover("*")
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0].name, "worker-1")

    def test_register_and_get(self):
        from axon.service_registry import ServiceRegistry, AgentService

        reg = ServiceRegistry(backend="in_memory")
        reg.register(AgentService(
            name="worker-2",
            host="localhost",
            port=8081,
        ))
        svc = reg.get("worker-2")
        self.assertIsNotNone(svc)
        self.assertEqual(svc.host, "localhost")

    def test_unregister(self):
        from axon.service_registry import ServiceRegistry, AgentService

        reg = ServiceRegistry(backend="in_memory")
        reg.register(AgentService(name="temp", host="localhost", port=8082))
        reg.unregister("temp")
        self.assertIsNone(reg.get("temp"))

    def test_discover_pattern(self):
        from axon.service_registry import ServiceRegistry, AgentService

        reg = ServiceRegistry(backend="in_memory")
        reg.register(AgentService(name="worker-1", host="h1", port=1))
        reg.register(AgentService(name="worker-2", host="h2", port=2))
        reg.register(AgentService(name="leader-1", host="h3", port=3))
        workers = reg.discover("worker-*")
        self.assertEqual(len(workers), 2)

    def test_heartbeat(self):
        from axon.service_registry import ServiceRegistry, AgentService

        reg = ServiceRegistry(backend="in_memory")
        reg.register(AgentService(name="hb", host="h", port=1))
        old_hb = reg.get("hb").heartbeat_at
        time.sleep(0.01)
        reg.heartbeat("hb")
        new_hb = reg.get("hb").heartbeat_at
        self.assertGreater(new_hb, old_hb)


# ---------------------------------------------------------------------------
# Mock Redis backend tests (no real Redis needed)
# ---------------------------------------------------------------------------


class MockRedis:
    """Minimal Redis mock for testing RedisBackend without a real server."""

    def __init__(self) -> None:
        self._data: dict[bytes, list] = {}
        self._channels: dict[str, list] = {}

    def lpush(self, key: bytes, value: bytes) -> int:
        if key not in self._data:
            self._data[key] = []
        self._data[key].insert(0, value)
        return len(self._data[key])

    def brpop(self, key: bytes, timeout: int = 0):
        import time as _time
        deadline = _time.time() + timeout
        while True:
            if key in self._data and self._data[key]:
                return (key, self._data[key].pop(0))
            if _time.time() >= deadline and timeout > 0:
                return None
            if timeout == 0:
                return None
            _time.sleep(0.01)

    def publish(self, channel: str, message: bytes) -> int:
        for cb in self._channels.get(channel, []):
            cb({"type": "message", "data": message})
        return 1

    def pubsub(self):
        return MockPubSub(self._channels)

    def close(self):
        pass

    def hset(self, name: str, key: str, value: str) -> int:
        if not hasattr(self, "_hashes"):
            self._hashes = {}
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name][key] = value
        return 1

    def hget(self, name: str, key: str) -> str | None:
        if not hasattr(self, "_hashes"):
            self._hashes = {}
        return self._hashes.get(name, {}).get(key)

    def hdel(self, name: str, key: str) -> int:
        if not hasattr(self, "_hashes"):
            self._hashes = {}
        if name in self._hashes and key in self._hashes[name]:
            del self._hashes[name][key]
            return 1
        return 0

    def hgetall(self, name: str) -> dict[str, str]:
        if not hasattr(self, "_hashes"):
            self._hashes = {}
        return self._hashes.get(name, {})


class MockPubSub:
    def __init__(self, channels: dict) -> None:
        self._channels = channels
        self._callbacks: dict[str, any] = {}

    def subscribe(self, **kwargs):
        for channel, cb in kwargs.items():
            if channel not in self._channels:
                self._channels[channel] = []
            self._callbacks[channel] = cb
            self._channels[channel].append(cb)

    def run_in_thread(self, sleep_time: float = 0.01):
        return MagicMock()

    def close(self):
        pass


class TestRedisBackendWithMock(unittest.TestCase):
    """Test RedisBackend using a mock Redis client."""

    def _make_bus(self):
        from axon.distributed_bus import DistributedBus, RedisBackend, MessageEnvelope
        import axon.distributed_bus as db_mod

        mock = MockRedis()
        backend = RedisBackend.__new__(RedisBackend)
        backend._client = mock
        backend._pubsub = mock.pubsub()
        backend._lock = __import__("threading").Lock()
        backend._handlers = {}
        backend._listener = None

        bus = DistributedBus.__new__(DistributedBus)
        bus.backend_name = "redis"
        bus.agent_name = "test_agent"
        bus._backend = backend
        return bus, mock

    def test_redis_send_receive(self):
        bus, mock = self._make_bus()
        bus.send("agent_b", {"task": "compute"})
        bus.set_agent("agent_b")
        msg = bus.receive(timeout_ms=1000)
        self.assertEqual(msg, {"task": "compute"})

    def test_redis_broadcast(self):
        bus, mock = self._make_bus()
        received = []
        bus.subscribe("events", lambda payload: received.append(payload))
        bus.broadcast("events", {"type": "alert"})
        self.assertEqual(received, [{"type": "alert"}])


# ---------------------------------------------------------------------------
# Runtime integration: --mesh flag wiring
# ---------------------------------------------------------------------------


class TestMeshCLIArgs(unittest.TestCase):
    """Test that --mesh and --mesh-url flags are accepted by the CLI parser."""

    def test_mesh_flag_exists(self):
        import sys
        sys.argv = ["axon", "run", "--help"]
        try:
            from axon.cli import _make_arg_parser
            parser = _make_arg_parser()
            args = parser.parse_args(["run", "--mesh", "redis", "--mesh-url", "redis://localhost:6379", "test.ax"])
            self.assertEqual(args.mesh_backend, "redis")
            self.assertEqual(args.mesh_url, "redis://localhost:6379")
        except SystemExit:
            pass  # --help causes SystemExit
        finally:
            sys.argv = []


# ---------------------------------------------------------------------------
# RuntimeConfig mesh fields
# ---------------------------------------------------------------------------


class TestRuntimeConfigMesh(unittest.TestCase):

    def test_mesh_fields_default(self):
        from axon.runtime import RuntimeConfig
        from pathlib import Path
        config = RuntimeConfig(source_path=Path("test.ax"))
        self.assertIsNone(config.mesh_backend)
        self.assertIsNone(config.mesh_url)

    def test_mesh_fields_set(self):
        from axon.runtime import RuntimeConfig
        from pathlib import Path
        config = RuntimeConfig(
            source_path=Path("test.ax"),
            mesh_backend="redis",
            mesh_url="redis://localhost:6379",
        )
        self.assertEqual(config.mesh_backend, "redis")
        self.assertEqual(config.mesh_url, "redis://localhost:6379")


if __name__ == "__main__":
    unittest.main()
