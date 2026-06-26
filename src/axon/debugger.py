"""AXON Debugger — step-through AEL trace inspector.

Provides programmatic and CLI interfaces for inspecting AEL execution traces:
- Step forward / backward through trace events
- Continue until breakpoint hit
- Breakpoints on event type, agent name, tool name, or memory key=value
- Variable watch on memory keys with change detection
- Memory state inspection from `store` events
- Event filtering and listing by type
- Trace statistics (event counts, agent breakdown)
- Range listing around current position
- Export filtered events or memory state to file
- Navigation backtrace
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
    mem_key: str | None = None         # break when this memory key is set
    mem_value: str | None = None       # break when memory key equals this value

    def matches(self, event: AELTraceEvent, memory: dict[str, Any] | None = None) -> bool:
        if self.event_type is not None and event.t != self.event_type:
            return False
        if self.agent is not None and getattr(event, "agent", None) != self.agent:
            return False
        if self.tool is not None:
            if event.t != "act":
                return False
            if getattr(event, "tool", None) != self.tool:
                return False
        if self.mem_key is not None:
            if memory is None or self.mem_key not in memory:
                return False
            if self.mem_value is not None and str(memory[self.mem_key]) != self.mem_value:
                return False
        return True


@dataclass
class Watch:
    """A variable watch on a memory key."""

    key: str
    last_value: Any = None
    initialized: bool = False

    def update(self, memory: dict[str, Any]) -> tuple[bool, Any, Any]:
        """Check if watched key changed. Returns (changed, old_value, new_value)."""
        old = self.last_value
        new = memory.get(self.key)
        if not self.initialized:
            self.initialized = True
            self.last_value = new
            return True, None, new
        if new != old:
            self.last_value = new
            return True, old, new
        return False, old, new


@dataclass
class DebugSession:
    """Mutable debug session state."""

    log: TraceLog
    index: int = 0
    breakpoints: list[Breakpoint] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)
    history: list[int] = field(default_factory=list)
    watches: list[Watch] = field(default_factory=list)
    _prev_memory: dict[str, Any] = field(default_factory=dict)

    @property
    def current(self) -> AELTraceEvent | None:
        if 0 <= self.index < len(self.log.events):
            return self.log.events[self.index]
        return None

    @property
    def total(self) -> int:
        return len(self.log.events)

    def _apply_event_to_memory(self, ev: AELTraceEvent) -> None:
        """Update memory state from a store event."""
        if isinstance(ev, StoreEvent):
            self.memory[ev.key] = ev.value

    def _rebuild_memory(self) -> None:
        """Rebuild memory from all store events up to current index."""
        self.memory = {}
        for ev in self.log.events[: self.index + 1]:
            if isinstance(ev, StoreEvent):
                self.memory[ev.key] = ev.value

    def _check_watches(self) -> list[tuple[str, Any, Any]]:
        """Check all watches for changes. Returns list of (key, old, new) tuples."""
        changes = []
        for w in self.watches:
            changed, old, new = w.update(self.memory)
            if changed:
                changes.append((w.key, old, new))
        return changes

    def step(self, count: int = 1) -> AELTraceEvent | None:
        """Move forward by `count` events, updating memory."""
        for _ in range(abs(count)):
            if count > 0:
                if self.index >= self.total:
                    break
                ev = self.log.events[self.index]
                self._apply_event_to_memory(ev)
                self.index += 1
            else:
                self.index -= 1
                if self.index < 0:
                    self.index = 0
                    break
                self._rebuild_memory()
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
        self._rebuild_memory()
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

    def continue_until_breakpoint(self) -> tuple[int, Breakpoint | None]:
        """Step forward until a breakpoint is hit or trace ends.
        Returns (events_stepped, breakpoint_hit_or_None)."""
        stepped = 0
        while self.index < self.total - 1:
            ev = self.session_next_quiet()
            stepped += 1
            bp = self.check_breakpoint()
            if bp:
                return stepped, bp
        return stepped, None

    def session_next_quiet(self) -> AELTraceEvent | None:
        """Step forward without checking breakpoints (internal)."""
        if self.index >= self.total - 1:
            return None
        ev = self.log.events[self.index]
        self._apply_event_to_memory(ev)
        self.index += 1
        self.history.append(self.index)
        return self.current

    def check_breakpoint(self) -> Breakpoint | None:
        """Return matching breakpoint for current event, or None."""
        ev = self.current
        if ev is None:
            return None
        for bp in self.breakpoints:
            if bp.matches(ev, memory=self.memory):
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

    def add_watch(self, key: str) -> Watch:
        """Add a variable watch on a memory key."""
        w = Watch(key=key)
        self.watches.append(w)
        return w

    def remove_watch(self, idx: int) -> bool:
        if 0 <= idx < len(self.watches):
            self.watches.pop(idx)
            return True
        return False

    def format_watches(self) -> str:
        if not self.watches:
            return "Watches: (none)"
        lines = ["Watches:"]
        for i, w in enumerate(self.watches):
            val = self.memory.get(w.key, "<unset>")
            lines.append(f"  [{i}] {w.key} = {str(val)[:100]}")
        return "\n".join(lines)

    def filter_events(self, event_type: str | None = None, agent: str | None = None) -> list[tuple[int, AELTraceEvent]]:
        """Return list of (index, event) tuples matching filters."""
        results = []
        for i, ev in enumerate(self.log.events):
            if event_type is not None and ev.t != event_type:
                continue
            if agent is not None and getattr(ev, "agent", None) != agent:
                continue
            results.append((i, ev))
        return results

    def format_event_list(self, events: list[tuple[int, AELTraceEvent]], max_count: int = 20) -> str:
        if not events:
            return "(no matching events)"
        lines = []
        shown = events[:max_count]
        for idx, ev in shown:
            marker = " => " if idx == self.index else "    "
            if isinstance(ev, ThinkEvent):
                desc = ev.content[:60]
            elif isinstance(ev, ActEvent):
                desc = f"{ev.tool}({json.dumps(ev.args, default=str)[:40]})"
            elif isinstance(ev, ObserveEvent):
                desc = f"{ev.name} = {str(ev.value)[:40]}"
            elif isinstance(ev, StoreEvent):
                desc = f"{ev.key} = {str(ev.value)[:40]}"
            else:
                desc = str(ev)[:60]
            lines.append(f"{marker}[{idx + 1}] {ev.t.upper():8s} {desc}")
        if len(events) > max_count:
            lines.append(f"    ... and {len(events) - max_count} more (use --all for full list)")
        return "\n".join(lines)

    def format_range(self, before: int = 2, after: int = 2) -> str:
        """Show events around the current position."""
        start = max(0, self.index - before)
        end = min(self.total, self.index + after + 1)
        lines = []
        for i in range(start, end):
            ev = self.log.events[i]
            marker = " => " if i == self.index else "    "
            if isinstance(ev, ThinkEvent):
                desc = ev.content[:60]
            elif isinstance(ev, ActEvent):
                desc = f"{ev.tool}({json.dumps(ev.args, default=str)[:40]})"
            elif isinstance(ev, ObserveEvent):
                desc = f"{ev.name} = {str(ev.value)[:40]}"
            elif isinstance(ev, StoreEvent):
                desc = f"{ev.key} = {str(ev.value)[:40]}"
            else:
                desc = str(ev)[:60]
            lines.append(f"{marker}[{i + 1}] {ev.t.upper():8s} {desc}")
        return "\n".join(lines)

    def format_stats(self) -> str:
        """Show trace statistics."""
        type_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}
        for ev in self.log.events:
            type_counts[ev.t] = type_counts.get(ev.t, 0) + 1
            a = getattr(ev, "agent", None) or "(none)"
            agent_counts[a] = agent_counts.get(a, 0) + 1
        lines = ["Trace Statistics:", f"  Total events: {self.total}"]
        lines.append("  By type:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    {t:10s}: {c}")
        lines.append("  By agent:")
        for a, c in sorted(agent_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    {a:20s}: {c}")
        return "\n".join(lines)

    def format_backtrace(self, max_entries: int = 20) -> str:
        """Show navigation history."""
        if not self.history:
            return "Backtrace: (empty)"
        lines = ["Backtrace:"]
        entries = self.history[-max_entries:]
        for i, idx in enumerate(entries):
            marker = " *" if i == len(entries) - 1 else ""
            lines.append(f"  [{i + 1}] event {idx + 1}{marker}")
        if len(self.history) > max_entries:
            lines.append(f"  ... ({len(self.history) - max_entries} older entries)")
        return "\n".join(lines)

    def export_filtered(self, event_type: str | None = None, agent: str | None = None) -> str:
        """Export filtered events as JSONL."""
        events = self.filter_events(event_type=event_type, agent=agent)
        lines = [json.dumps(ev.to_dict(), default=str) for _, ev in events]
        return "\n".join(lines)

    def export_memory(self) -> str:
        """Export current memory state as JSON."""
        return json.dumps(self.memory, indent=2, default=str)

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
            f"Breakpoints: {len(self.breakpoints)} | Memory keys: {len(self.memory)} | "
            f"Watches: {len(self.watches)}"
        )


class Debugger:
    """High-level debugger interface for AXON traces."""

    def __init__(self, trace_path: str | Path) -> None:
        self.log = read_trace_file(trace_path)
        self.session = DebugSession(log=self.log)

    def run_interactive(self) -> None:
        """Run an interactive REPL-style debugger session."""
        print(f"AXON Debugger — {self.session.total} events loaded")
        print("Type 'help' for commands.\n")
        print(self.session.format_current())
        print()

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
                    self._check_bp_and_watches()
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
            if cmd in ("c", "cont", "continue"):
                stepped, bp = self.session.continue_until_breakpoint()
                if bp:
                    print(f"Stepped {stepped} event(s). Hit breakpoint: {bp}")
                    print(self.session.format_current())
                else:
                    print(f"Stepped {stepped} event(s). End of trace.")
                    print(self.session.format_current())
                continue
            if cmd in ("mem", "memory"):
                print(self.session.format_memory())
                continue
            if cmd in ("info", "summary"):
                print(self.session.format_summary())
                continue
            if cmd in ("stats", "statistics"):
                print(self.session.format_stats())
                continue
            if cmd in ("bt", "backtrace"):
                print(self.session.format_backtrace())
                continue
            if cmd in ("w", "watch", "watches"):
                print(self.session.format_watches())
                continue
            if cmd in ("list", "ls"):
                events = self.session.filter_events()
                print(self.session.format_event_list(events))
                continue
            if cmd.startswith("list "):
                rest = cmd[5:].strip()
                event_type = None
                agent = None
                for part in rest.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        if k == "type":
                            event_type = v
                        elif k == "agent":
                            agent = v
                    else:
                        event_type = part
                events = self.session.filter_events(event_type=event_type, agent=agent)
                print(self.session.format_event_list(events))
                continue
            if cmd in ("range", "ctx", "context"):
                print(self.session.format_range())
                continue
            if cmd.startswith("range "):
                try:
                    parts = cmd[6:].split()
                    before = int(parts[0]) if len(parts) > 0 else 2
                    after = int(parts[1]) if len(parts) > 1 else 2
                    print(self.session.format_range(before=before, after=after))
                except ValueError:
                    print("Usage: range [before] [after]")
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
                    mem_key=kw.get("mem"),
                    mem_value=kw.get("value"),
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
            if cmd.startswith("watch "):
                key = cmd[6:].strip()
                if not key:
                    print("Usage: watch <memory-key>")
                else:
                    w = self.session.add_watch(key)
                    print(f"Watching: {w.key} (current: {self.session.memory.get(key, '<unset>')})")
                continue
            if cmd.startswith("unwatch "):
                try:
                    idx = int(cmd.split()[1])
                    if self.session.remove_watch(idx):
                        print("Watch removed.")
                    else:
                        print("Invalid watch index.")
                except (ValueError, IndexError):
                    print("Usage: unwatch <index>")
                continue
            if cmd.startswith("export "):
                rest = cmd[7:].strip()
                parts = rest.split(maxsplit=1)
                if not parts:
                    print("Usage: export <file> [filter]")
                else:
                    filepath = parts[0]
                    filter_str = parts[1] if len(parts) > 1 else ""
                    event_type = None
                    agent = None
                    for p in filter_str.split():
                        if "=" in p:
                            k, v = p.split("=", 1)
                            if k == "type":
                                event_type = v
                            elif k == "agent":
                                agent = v
                        else:
                            event_type = p
                    if event_type or agent:
                        content = self.session.export_filtered(event_type=event_type, agent=agent)
                    else:
                        content = self.session.export_memory()
                    Path(filepath).write_text(content, encoding="utf-8")
                    print(f"Exported to {filepath}")
                continue
            if cmd in ("h", "help"):
                print(self._format_help())
                continue

            print(f"Unknown command: {cmd}. Type 'help' for commands.")

    def _check_bp_and_watches(self) -> None:
        """Check breakpoints and watches after stepping."""
        bp = self.session.check_breakpoint()
        if bp:
            print(f"[BREAKPOINT] {bp}")
        changes = self.session._check_watches()
        for key, old, new in changes:
            if old is None:
                print(f"[WATCH] {key} set to {str(new)[:80]}")
            else:
                print(f"[WATCH] {key} changed: {str(old)[:40]} -> {str(new)[:40]}")

    def _format_help(self) -> str:
        return (
            "Navigation:\n"
            "  n / next              — step forward one event\n"
            "  p / prev              — step backward one event\n"
            "  c / cont / continue   — run until breakpoint or end\n"
            "  goto <idx>            — jump to event index (1-based)\n"
            "  search <text>         — find next event containing text\n"
            "  bt / backtrace        — show navigation history\n"
            "\n"
            "Inspection:\n"
            "  mem / memory          — show memory state\n"
            "  info / summary        — show session summary\n"
            "  stats                 — show trace statistics\n"
            "  range [before] [after] — show events around current position\n"
            "  list [type] [agent=X] — list events (optionally filtered)\n"
            "\n"
            "Breakpoints:\n"
            "  bp                    — list breakpoints\n"
            "  bp type=act agent=Bot tool=Search once — add breakpoint\n"
            "  bp mem=result value=found — break when memory key equals value\n"
            "  del <idx>             — remove breakpoint\n"
            "\n"
            "Watches:\n"
            "  watch <key>           — watch a memory key for changes\n"
            "  w / watches           — list watches\n"
            "  unwatch <idx>         — remove watch\n"
            "\n"
            "Export:\n"
            "  export <file>         — export memory state as JSON\n"
            "  export <file> type=act — export filtered events as JSONL\n"
            "\n"
            "  q / quit              — exit debugger"
        )
