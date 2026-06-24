"""Hot-reload source watching for AXON runtime.

Provides polling-based file watching and agent reloading with zero
external dependencies.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from result import Ok

from axon.agent_lifecycle import AgentLifecycleManager
from axon.agent_supervisor import ChildSpec
from axon.trace_emitter import TraceEmitter


@dataclass
class _WatchEntry:
    path: Path
    callback: Callable[[Path], None]
    last_mtime: float = 0.0
    last_size: int = 0
    debounce_until: float = 0.0


class SourceWatcher:
    """Polls files for modification and invokes callbacks on change.

    Zero-dependency implementation using ``os.stat`` mtime polling.
    """

    def __init__(self, poll_interval_ms: int = 1000, debounce_ms: int = 1000) -> None:
        self._poll_interval = poll_interval_ms / 1000.0
        self._debounce = debounce_ms / 1000.0
        self._entries: dict[str, _WatchEntry] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def add_file(
        self,
        path: Path,
        callback: Callable[[Path], None],
    ) -> None:
        """Register a file to watch. Thread-safe."""
        abs_path = str(path.resolve())
        try:
            stat = path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            mtime = 0.0
            size = 0

        with self._lock:
            self._entries[abs_path] = _WatchEntry(
                path=path,
                callback=callback,
                last_mtime=mtime,
                last_size=size,
            )

    def remove_file(self, path: Path) -> None:
        """Stop watching a file. Thread-safe."""
        abs_path = str(path.resolve())
        with self._lock:
            self._entries.pop(abs_path, None)

    def start(self) -> None:
        """Start the background polling thread."""
        with self._lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="axon-source-watcher",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""
        with self._lock:
            self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval + 1.0)
            self._thread = None

    def _poll_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                entries = list(self._entries.values())

            now = time.time()
            for entry in entries:
                try:
                    stat = entry.path.stat()
                    current_mtime = stat.st_mtime
                    current_size = stat.st_size
                except OSError:
                    continue

                changed = (
                    current_mtime != entry.last_mtime
                    or current_size != entry.last_size
                )
                if changed and now >= entry.debounce_until:
                    entry.last_mtime = current_mtime
                    entry.last_size = current_size
                    entry.debounce_until = now + self._debounce
                    try:
                        entry.callback(entry.path)
                    except Exception:
                        pass  # Callback errors must not crash watcher

            time.sleep(self._poll_interval)


class AgentReloader:
    """Watches agent source files and reloads them via a lifecycle manager.

    On file change: terminate the existing agent, then re-spawn with the
    same configuration.
    """

    def __init__(
        self,
        lifecycle: AgentLifecycleManager,
        watcher: SourceWatcher,
        emitter: TraceEmitter | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._watcher = watcher
        self._emitter = emitter or TraceEmitter()
        self._specs: dict[str, ChildSpec] = {}
        self._lock = threading.Lock()

    def watch(self, spec: ChildSpec) -> None:
        """Start watching a child's source file."""
        with self._lock:
            self._specs[spec.name] = spec

        self._watcher.add_file(spec.source_path, self._make_callback(spec.name))

    def unwatch(self, name: str) -> None:
        """Stop watching a child's source file."""
        with self._lock:
            spec = self._specs.pop(name, None)
        if spec is not None:
            self._watcher.remove_file(spec.source_path)

    def _make_callback(self, name: str) -> Callable[[Path], None]:
        def _on_change(path: Path) -> None:
            with self._lock:
                spec = self._specs.get(name)
            if spec is None:
                return

            self._emitter.source_reload_start(
                agent_name=name, source_path=str(path)
            )

            # Terminate existing instance
            self._lifecycle.terminate(name, reason="source_change")
            # Wait briefly for thread exit
            time.sleep(0.1)

            # Re-spawn with same spec
            result = self._lifecycle.spawn(
                source_path=spec.source_path,
                name=spec.name,
                args=spec.args,
                mock=spec.mock,
                provider_name=spec.provider_name,
            )
            if isinstance(result, Ok):
                self._emitter.source_reload_end(
                    agent_name=name, new_id=result.ok_value
                )
            else:
                self._emitter.source_reload_error(
                    agent_name=name, error=str(result.err_value)
                )

        return _on_change
