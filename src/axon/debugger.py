"""AXON Debugger — step-through AEL trace inspector.

Provides programmatic and CLI interfaces for inspecting AEL execution traces:
- Step forward / backward through trace events
- Breakpoints on event type, agent name, or tool name
- Memory state inspection from `store` events
- Stack-like navigation with goto / search
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axon.trace import AELTraceEvent, ActEvent, ObserveEvent, StoreEvent, ThinkEvent, TraceLog
from axon.trace_reader import read_trace_file


@dataclass
class Breakpoint:
    """A debugger breakpoint condition."""

    event_type: str | None = None      # "think", "act", "observe", "store"
    agent: str | None = None           # agent name
    tool: str | None = None            # for act events
    once: bool = False                 # remove after first hit

    def matches(self, event: AELTraceEvent) -> bool:
        if self.event_type is not None and event.t != self.event_type:
            return False
        if self.agent is not None and getattr(event, "agent", None) != self.agent:
            return False
        if self.tool is not None:
            if event.t != "act":
                return False
            if getattr(event, "tool", None) != self.tool:
                return False
        return True


@dataclass
class DebugSession:
    """Mutable debug session state."""

    log: TraceLog
    index: int = 0
    breakpoints: list[Breakpoint] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)
    history: list[int] = field(default_factory=list)

    @property
    def current(self) -> AELTraceEvent | None:
        if 0 <= self.index < len(self.log.events):
            return self.log.events[self.index]
        return None

    @property
    def total(self) -> int:
        return len(self.log.events)

    def step(self, count: int = 1) -> AELTraceEvent | None:
        """Move forward by `count` events, updating memory."""
        for _ in range(abs(count)):
            if self.index >= self.total:
                break
            ev = self.log.events[self.index]
            if isinstance(ev, StoreEvent):
                self.memory[ev.key] = ev.value
            self.index += 1 if count > 0 else -1
        self.index = max(0, min(self.index, self.total - 1))
        self.history.append(self.index)
        return self.current

    def next(self) -> AELTraceEvent | None:
        """Step forward one event."""
        return self.step(1)

    def prev(self) -> AELTraceEvent | None:
        """Step backward one event."""
        return self.step(-1)

    def goto(self, idx: int) -> AELTraceEvent | None:
        """Jump to a specific event index."""
        self.index = max(0, min(idx, self.total - 1))
        # Rebuild memory from all store events up to this point
        self.memory = {}
        for ev in self.log.events[: self.index + 1]:
            if isinstance(ev, StoreEvent):
                self.memory[ev.key] = ev.value
        self.history.append(self.index)
        return self.current

    def search(self, text: str) -> int | None:
        """Find next event containing `text` (case-insensitive)."""
        for i in range(self.index + 1, self.total):
            ev = self.log.events[i]
            if text.lower() in json.dumps(ev.to_dict(), default=str).lower():
                self.goto(i)
                return i
        return None

    def check_breakpoint(self) -> Breakpoint | None:
        """Return matching breakpoint for current event, or None."""
        ev = self.current
        if ev is None:
            return None
        for bp in self.breakpoints:
            if bp.matches(ev):
                if bp.once:
                    self.breakpoints.remove(bp)
                return bp
        return None

    def add_breakpoint(self, bp: Breakpoint) -> None:
        self.breakpoints.append(bp)

    def remove_breakpoint(self, idx: int) -> bool:
        if 0 <= idx < len(self.breakpoints):
            self.breakpoints.pop(idx)
            return True
        return False

    def format_current(self) -> str:
        """Pretty-print the current event."""
        ev = self.current
        if ev is None:
            return "No event."
        lines = [f"[{self.index + 1}/{self.total}] {ev.t.upper()}"]
        if getattr(ev, "agent", None):
            lines.append(f"  agent: {ev.agent}")
        if isinstance(ev, ThinkEvent):
            lines.append(f"  content: {ev.content[:200]}")
            if ev.tokens:
                lines.append(f"  tokens: {ev.tokens}")
        elif isinstance(ev, ActEvent):
            lines.append(f"  tool: {ev.tool}")
            if ev.args:
                lines.append(f"  args: {json.dumps(ev.args, default=str)[:200]}")
        elif isinstance(ev, ObserveEvent):
            lines.append(f"  name: {ev.name}")
            lines.append(f"  value: {str(ev.value)[:200]}")
            if ev.count is not None:
                lines.append(f"  count: {ev.count}")
        elif isinstance(ev, StoreEvent):
            lines.append(f"  key: {ev.key}")
            lines.append(f"  value: {str(ev.value)[:200]}")
        ts = getattr(ev, "ts", None)
        if ts is not None:
            lines.append(f"  ts: {ts}")
        return "\n".join(lines)

    def format_memory(self) -> str:
        if not self.memory:
            return "Memory: (empty)"
        lines = ["Memory:"]
        for k, v in self.memory.items():
            lines.append(f"  {k} = {str(v)[:100]}")
        return "\n".join(lines)

    def format_summary(self) -> str:
        return (
            f"Events: {self.total} | Index: {self.index + 1} | "
            f"Breakpoints: {len(self.breakpoints)} | Memory keys: {len(self.memory)}"
        )


class Debugger:
    """High-level debugger interface for AXON traces."""

    def __init__(self, trace_path: str | Path) -> None:
        self.log = read_trace_file(trace_path)
        self.session = DebugSession(log=self.log)

    def run_interactive(self) -> None:
        """Run an interactive REPL-style debugger session."""
        import sys

        print(f"AXON Debugger — {self.session.total} events loaded")
        print("Commands: n(ext), p(rev), goto <idx>, search <text>, mem, bp, quit")

        while True:
            try:
                cmd = input("(axon-dbg) ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not cmd:
                continue
            if cmd in ("q", "quit", "exit"):
                break
            if cmd in ("n", "next"):
                ev = self.session.next()
                if ev:
                    print(self.session.format_current())
                    bp = self.session.check_breakpoint()
                    if bp:
                        print(f"[BREAKPOINT] {bp}")
                else:
                    print("End of trace.")
                continue
            if cmd in ("p", "prev", "previous"):
                ev = self.session.prev()
                if ev:
                    print(self.session.format_current())
                else:
                    print("Start of trace.")
                continue
            if cmd in ("mem", "memory"):
                print(self.session.format_memory())
                continue
            if cmd in ("info", "summary"):
                print(self.session.format_summary())
                continue
            if cmd.startswith("goto "):
                try:
                    idx = int(cmd.split()[1]) - 1
                    self.session.goto(idx)
                    print(self.session.format_current())
                except (ValueError, IndexError):
                    print("Usage: goto <1-based-index>")
                continue
            if cmd.startswith("search "):
                text = cmd[7:]
                idx = self.session.search(text)
                if idx is not None:
                    print(self.session.format_current())
                else:
                    print("Not found.")
                continue
            if cmd.startswith("bp "):
                rest = cmd[3:].strip()
                parts = rest.split()
                kw = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        kw[k] = v
                bp = Breakpoint(
                    event_type=kw.get("type"),
                    agent=kw.get("agent"),
                    tool=kw.get("tool"),
                    once="once" in parts,
                )
                self.session.add_breakpoint(bp)
                print(f"Breakpoint added: {bp}")
                continue
            if cmd in ("bp", "breakpoints"):
                for i, bp in enumerate(self.session.breakpoints):
                    print(f"  [{i}] {bp}")
                continue
            if cmd.startswith("del "):
                try:
                    idx = int(cmd.split()[1])
                    if self.session.remove_breakpoint(idx):
                        print("Breakpoint removed.")
                    else:
                        print("Invalid breakpoint index.")
                except (ValueError, IndexError):
                    print("Usage: del <index>")
                continue
            if cmd in ("h", "help"):
                print(
                    "n / next       — step forward\n"
                    "p / prev       — step backward\n"
                    "goto <idx>     — jump to event index (1-based)\n"
                    "search <text>  — find next event containing text\n"
                    "mem / memory   — show memory state\n"
                    "info / summary — show session summary\n"
                    "bp             — list breakpoints\n"
                    "bp type=act agent=Bot tool=Search once — add breakpoint\n"
                    "del <idx>      — remove breakpoint\n"
                    "q / quit       — exit debugger"
                )
                continue

            print(f"Unknown command: {cmd}. Type 'help' for commands.")
