"""Graceful shutdown handling for AXON runtime.

Provides signal handlers for SIGTERM / SIGINT that initiate a controlled
shutdown of running agents, giving them a chance to checkpoint and exit.
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from typing import Any, Callable


class ShutdownController:
    """Manages graceful shutdown of the AXON runtime."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._shutdown_event = threading.Event()
        self._handlers: list[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._installed = False

    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()

    def register(self, handler: Callable[[], None]) -> None:
        """Register a callback to run during graceful shutdown."""
        with self._lock:
            self._handlers.append(handler)

    def install(self) -> None:
        """Install signal handlers for SIGTERM and SIGINT."""
        if self._installed:
            return
        self._installed = True

        def _handler(signum: int, frame: Any) -> None:
            print(f"\nReceived signal {signum}, initiating graceful shutdown...")
            self._shutdown()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    def _shutdown(self) -> None:
        """Run all registered handlers with a timeout."""
        self._shutdown_event.set()

        def _run_handlers() -> None:
            with self._lock:
                handlers = list(self._handlers)
            for handler in handlers:
                try:
                    handler()
                except Exception as e:
                    print(f"Shutdown handler error: {e}", file=sys.stderr)

        thread = threading.Thread(target=_run_handlers, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout_seconds)

        if thread.is_alive():
            print("Graceful shutdown timed out, forcing exit.", file=sys.stderr)
        sys.exit(0)

    def wait(self, interval: float = 0.1) -> bool:
        """Block until shutdown is requested. Returns True if shutdown."""
        while not self._shutdown_event.is_set():
            time.sleep(interval)
        return True
