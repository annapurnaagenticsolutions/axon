"""Service registry for AXON distributed agent discovery.

Provides in-memory and Redis-backed registries for agent lookup
across process boundaries.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentService:
    """A registered agent service record."""

    name: str
    host: str
    port: int
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    heartbeat_at: float = field(default_factory=time.time)

    def is_alive(self, timeout_s: float = 30.0) -> bool:
        return time.time() - self.heartbeat_at < timeout_s


class ServiceRegistry:
    """In-memory service registry with optional Redis backing."""

    def __init__(self, backend: str = "in_memory", url: str | None = None) -> None:
        self._backend_name = backend
        self._agents: dict[str, AgentService] = {}
        self._lock = threading.Lock()
        self._redis: Any = None
        if backend == "redis":
            import redis  # type: ignore[import-untyped]

            self._redis = redis.from_url(url or "redis://localhost:6379", decode_responses=True)

    def register(self, service: AgentService) -> None:
        with self._lock:
            self._agents[service.name] = service
        if self._redis:
            import json

            self._redis.hset(
                "axon:services",
                service.name,
                json.dumps(
                    {
                        "name": service.name,
                        "host": service.host,
                        "port": service.port,
                        "capabilities": service.capabilities,
                        "metadata": service.metadata,
                        "heartbeat_at": service.heartbeat_at,
                    }
                ),
            )

    def unregister(self, name: str) -> None:
        with self._lock:
            self._agents.pop(name, None)
        if self._redis:
            self._redis.hdel("axon:services", name)

    def discover(self, pattern: str = "*") -> list[AgentService]:
        import fnmatch

        if self._redis:
            import json

            raw = self._redis.hgetall("axon:services")
            services = []
            for name, data in raw.items():
                obj = json.loads(data)
                if fnmatch.fnmatch(obj["name"], pattern):
                    services.append(
                        AgentService(
                            name=obj["name"],
                            host=obj["host"],
                            port=obj["port"],
                            capabilities=obj.get("capabilities", []),
                            metadata=obj.get("metadata", {}),
                            heartbeat_at=obj.get("heartbeat_at", 0),
                        )
                    )
            return services

        with self._lock:
            return [
                svc
                for svc in self._agents.values()
                if fnmatch.fnmatch(svc.name, pattern) and svc.is_alive()
            ]

    def heartbeat(self, name: str) -> None:
        with self._lock:
            if name in self._agents:
                self._agents[name].heartbeat_at = time.time()
        if self._redis:
            self._redis.hset("axon:services:heartbeat", name, str(time.time()))

    def get(self, name: str) -> AgentService | None:
        with self._lock:
            svc = self._agents.get(name)
            if svc and svc.is_alive():
                return svc
        if self._redis:
            import json

            data = self._redis.hget("axon:services", name)
            if data:
                obj = json.loads(data)
                return AgentService(
                    name=obj["name"],
                    host=obj["host"],
                    port=obj["port"],
                    capabilities=obj.get("capabilities", []),
                    metadata=obj.get("metadata", {}),
                    heartbeat_at=obj.get("heartbeat_at", 0),
                )
        return None
