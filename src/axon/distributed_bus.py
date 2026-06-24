"""Distributed message bus for AXON multi-agent runtime.

Provides pluggable backends:
- in_memory (default): single-process deque-based mailboxes
- redis: cross-process via Redis Pub/Sub + Lists
- nats: cross-process via NATS subjects

Backends are loaded lazily; missing dependencies only raise if the
backend is explicitly requested.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class MessageEnvelope:
    """A message with metadata."""
    sender: str
    recipient: str
    payload: Any
    timestamp: float = field(default_factory=time.time)


class BusBackend(ABC):
    """Abstract base for message bus backends."""

    @abstractmethod
    def send(self, recipient: str, envelope: MessageEnvelope) -> None:
        """Send a message to a named recipient."""

    @abstractmethod
    def receive(
        self, agent_name: str, timeout_ms: int = 0
    ) -> MessageEnvelope | None:
        """Receive a message for the given agent."""

    @abstractmethod
    def broadcast(self, channel: str, envelope: MessageEnvelope) -> None:
        """Broadcast a message to a channel."""

    @abstractmethod
    def subscribe(
        self, channel: str, callback: Callable[[MessageEnvelope], None]
    ) -> None:
        """Subscribe to a broadcast channel."""

    @abstractmethod
    def close(self) -> None:
        """Close connections and clean up."""


class InMemoryBackend(BusBackend):
    """Single-process in-memory backend using deques."""

    def __init__(self) -> None:
        self._mailboxes: dict[str, deque[MessageEnvelope]] = {}
        self._broadcasts: dict[str, deque[MessageEnvelope]] = {}
        self._subs: dict[str, list[Callable[[MessageEnvelope], None]]] = {}
        self._lock = threading.Lock()

    def send(self, recipient: str, envelope: MessageEnvelope) -> None:
        with self._lock:
            if recipient not in self._mailboxes:
                self._mailboxes[recipient] = deque()
            self._mailboxes[recipient].append(envelope)

    def receive(
        self, agent_name: str, timeout_ms: int = 0
    ) -> MessageEnvelope | None:
        deadline = time.time() + (timeout_ms / 1000.0) if timeout_ms > 0 else 0
        while True:
            with self._lock:
                mailbox = self._mailboxes.get(agent_name, deque())
                if mailbox:
                    return mailbox.popleft()
            if time.time() >= deadline:
                return None
            time.sleep(0.01)

    def broadcast(self, channel: str, envelope: MessageEnvelope) -> None:
        with self._lock:
            if channel not in self._broadcasts:
                self._broadcasts[channel] = deque()
            self._broadcasts[channel].append(envelope)
            for cb in self._subs.get(channel, []):
                try:
                    cb(envelope)
                except Exception:
                    pass

    def subscribe(
        self, channel: str, callback: Callable[[MessageEnvelope], None]
    ) -> None:
        with self._lock:
            self._subs.setdefault(channel, []).append(callback)

    def close(self) -> None:
        with self._lock:
            self._mailboxes.clear()
            self._broadcasts.clear()
            self._subs.clear()


class RedisBackend(BusBackend):
    """Redis-backed distributed message bus."""

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        import redis  # type: ignore[import-untyped]

        self._client = redis.from_url(url, decode_responses=False)
        self._pubsub = self._client.pubsub()
        self._lock = threading.Lock()
        self._handlers: dict[str, Callable[[MessageEnvelope], None]] = {}
        self._listener: threading.Thread | None = None

    def send(self, recipient: str, envelope: MessageEnvelope) -> None:
        import pickle

        self._client.lpush(f"axon:mailbox:{recipient}", pickle.dumps(envelope))

    def receive(
        self, agent_name: str, timeout_ms: int = 0
    ) -> MessageEnvelope | None:
        import pickle

        timeout_s = timeout_ms / 1000.0 if timeout_ms > 0 else 0
        raw = self._client.brpop(
            f"axon:mailbox:{agent_name}", timeout=int(timeout_s) or 1
        )
        if raw:
            return pickle.loads(raw[1])  # type: ignore[return-value]
        return None

    def broadcast(self, channel: str, envelope: MessageEnvelope) -> None:
        import pickle

        self._client.publish(f"axon:channel:{channel}", pickle.dumps(envelope))

    def subscribe(
        self, channel: str, callback: Callable[[MessageEnvelope], None]
    ) -> None:
        def _handler(message: Any) -> None:
            import pickle

            if message["type"] == "message":
                envelope = pickle.loads(message["data"])
                callback(envelope)

        with self._lock:
            self._handlers[channel] = _handler
            self._pubsub.subscribe(**{f"axon:channel:{channel}": _handler})
        if self._listener is None:
            self._listener = threading.Thread(target=self._pubsub.run_in_thread, kwargs={"sleep_time": 0.01}, daemon=True)
            self._listener.start()

    def close(self) -> None:
        if self._listener:
            self._pubsub.close()
        self._client.close()


class NATSBackend(BusBackend):
    """NATS-backed distributed message bus."""

    def __init__(self, url: str = "nats://localhost:4222") -> None:
        import asyncio
        import nats  # type: ignore[import-untyped]

        self._url = url
        self._nc: Any = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._lock = threading.Lock()
        self._subs: dict[str, Any] = {}

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _connect(self) -> Any:
        import asyncio

        if self._nc is None:
            self._nc = asyncio.run_coroutine_threadsafe(
                nats.connect(self._url), self._loop
            ).result(timeout=5)
        return self._nc

    def send(self, recipient: str, envelope: MessageEnvelope) -> None:
        import asyncio
        import pickle

        nc = self._connect()
        asyncio.run_coroutine_threadsafe(
            nc.publish(f"axon.mailbox.{recipient}", pickle.dumps(envelope)),
            self._loop,
        ).result(timeout=5)

    def receive(
        self, agent_name: str, timeout_ms: int = 0
    ) -> MessageEnvelope | None:
        import asyncio
        import pickle

        nc = self._connect()
        fut = asyncio.run_coroutine_threadsafe(
            nc.request(f"axon.mailbox.{agent_name}", b"", timeout=timeout_ms / 1000.0),
            self._loop,
        )
        try:
            msg = fut.result(timeout=(timeout_ms / 1000.0) + 1)
            return pickle.loads(msg.data)  # type: ignore[return-value]
        except Exception:
            return None

    def broadcast(self, channel: str, envelope: MessageEnvelope) -> None:
        import asyncio
        import pickle

        nc = self._connect()
        asyncio.run_coroutine_threadsafe(
            nc.publish(f"axon.channel.{channel}", pickle.dumps(envelope)),
            self._loop,
        ).result(timeout=5)

    def subscribe(
        self, channel: str, callback: Callable[[MessageEnvelope], None]
    ) -> None:
        import asyncio
        import pickle

        async def _handler(msg: Any) -> None:
            envelope = pickle.loads(msg.data)
            callback(envelope)

        nc = self._connect()
        sub = asyncio.run_coroutine_threadsafe(
            nc.subscribe(f"axon.channel.{channel}", cb=_handler), self._loop
        ).result(timeout=5)
        with self._lock:
            self._subs[channel] = sub

    def close(self) -> None:
        import asyncio

        if self._nc:
            asyncio.run_coroutine_threadsafe(self._nc.close(), self._loop).result(timeout=5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)


class DistributedBus:
    """Pluggable distributed message bus for AXON runtime."""

    def __init__(
        self,
        backend: str = "in_memory",
        url: str | None = None,
        agent_name: str = "",
    ) -> None:
        self.backend_name = backend
        self.agent_name = agent_name
        if backend == "in_memory":
            self._backend: BusBackend = InMemoryBackend()
        elif backend == "redis":
            self._backend = RedisBackend(url or "redis://localhost:6379")
        elif backend == "nats":
            self._backend = NATSBackend(url or "nats://localhost:4222")
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def set_agent(self, name: str) -> None:
        self.agent_name = name

    def send(self, recipient: str, payload: Any) -> None:
        envelope = MessageEnvelope(
            sender=self.agent_name, recipient=recipient, payload=payload
        )
        self._backend.send(recipient, envelope)

    def receive(self, timeout_ms: int = 0) -> Any | None:
        envelope = self._backend.receive(self.agent_name, timeout_ms=timeout_ms)
        if envelope is None:
            return None
        return envelope.payload

    def receive_blocking(self, timeout_ms: int = 5000) -> Any:
        result = self.receive(timeout_ms=timeout_ms)
        if result is None:
            raise TimeoutError(
                f"No message received by '{self.agent_name}' within {timeout_ms}ms"
            )
        return result

    def broadcast(self, channel: str, payload: Any) -> None:
        envelope = MessageEnvelope(
            sender=self.agent_name, recipient="*", payload=payload
        )
        self._backend.broadcast(channel, envelope)

    def subscribe(
        self, channel: str, callback: Callable[[Any], None]
    ) -> None:
        def _wrapper(envelope: MessageEnvelope) -> None:
            callback(envelope.payload)

        self._backend.subscribe(channel, _wrapper)

    def close(self) -> None:
        self._backend.close()
