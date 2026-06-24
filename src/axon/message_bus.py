"""In-memory message bus for AXON multi-agent communication.

Provides send/receive operations between named agents.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any


class MessageBus:
    """Simple in-memory message bus for inter-agent communication."""

    def __init__(self) -> None:
        self._mailboxes: dict[str, deque[Any]] = {}
        self._current_agent: str = ""

    def set_current_agent(self, name: str) -> None:
        """Set the current agent context (used for trace emission)."""
        self._current_agent = name

    def send(self, recipient: str, message: Any) -> None:
        """Send a message to a named agent's mailbox."""
        if recipient not in self._mailboxes:
            self._mailboxes[recipient] = deque()
        self._mailboxes[recipient].append(message)

    def receive(self, timeout_ms: int = 0) -> Any | None:
        """Receive a message from the current agent's mailbox.

        Non-blocking if timeout_ms is 0. Returns None if no message.
        """
        mailbox = self._mailboxes.get(self._current_agent, deque())
        if mailbox:
            return mailbox.popleft()
        if timeout_ms <= 0:
            return None
        # Simple blocking with polling
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            mailbox = self._mailboxes.get(self._current_agent, deque())
            if mailbox:
                return mailbox.popleft()
            time.sleep(0.01)
        return None

    def receive_blocking(self, timeout_ms: int = 5000) -> Any:
        """Block until a message arrives or timeout."""
        result = self.receive(timeout_ms=timeout_ms)
        if result is None:
            raise TimeoutError(
                f"No message received by '{self._current_agent}' within {timeout_ms}ms"
            )
        return result

    def has_messages(self, agent_name: str) -> bool:
        """Check if an agent has pending messages."""
        mailbox = self._mailboxes.get(agent_name, deque())
        return len(mailbox) > 0

    def clear(self) -> None:
        """Remove all messages from all mailboxes."""
        self._mailboxes.clear()

    def broadcast(self, channel: str, message: Any) -> None:
        """Broadcast a message to a channel (all agents receive)."""
        for mailbox in self._mailboxes.values():
            mailbox.append(message)

    def subscribe(self, channel: str, callback: Any) -> None:
        """No-op for in-memory bus (broadcast goes to all mailboxes)."""
        pass
