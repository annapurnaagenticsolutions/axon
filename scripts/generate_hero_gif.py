"""
AXON Hero GIF Generator — Python Version
Works on Windows without bash. Produces an asciinema cast file
that can be converted to GIF using agg or asciinema.org.

Usage:
    python scripts/generate_hero_gif.py

Then either:
    1. Upload docs/launch/axon-hero.cast to https://asciinema.org and download GIF
    2. Install agg: scoop install agg  →  agg docs/launch/axon-hero.cast docs/launch/axon-hero.gif
    3. Install terminalizer: npm i -g terminalizer  →  terminalizer render docs/launch/axon-hero.cast
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
CAST = ROOT / "docs" / "launch" / "axon-hero.cast"
CAST.parent.mkdir(parents=True, exist_ok=True)

# Color codes
BLUE = "\x1b[38;5;111m"
GREEN = "\x1b[38;5;46m"
PINK = "\x1b[38;5;206m"
PEACH = "\x1b[38;5;156m"
RED = "\x1b[38;5;210m"
GRAY = "\x1b[38;5;245m"
YELLOW = "\x1b[38;5;217m"
RESET = "\x1b[0m"

events = []
t = 0.0

def emit(text, delay=0.5):
    global t
    t += delay
    events.append([round(t, 1), "o", text])

def type_cmd(cmd, delay=0.3):
    global t
    t += 0.3
    events.append([round(t, 1), "o", "$ "])
    t += delay
    events.append([round(t, 1), "o", cmd + "\r\n"])

# Header
emit(f"{BLUE}AXON — Typed DSL for Autonomous Agents{RESET}\r\n", 0.8)
emit(f"{GRAY}Compiles to Python + TypeScript{RESET}\r\n\r\n", 0.5)

# Show .ax file
type_cmd("cat examples/hello.ax", 0.4)
emit(f"{GRAY}// hello.ax — A minimal AXON agent{RESET}\r\n", 0.3)
emit("\r\n", 0.2)
emit(f"{PINK}tool{RESET} {PEACH}Greet{RESET}(name: {YELLOW}Str{RESET}) -> {YELLOW}Str{RESET} {{\r\n", 0.3)
emit(f"    {GRAY}/// Says hello to someone.{RESET}\r\n", 0.2)
emit('    "Hello, {name}!"\r\n', 0.2)
emit("}\r\n", 0.2)
emit("\r\n", 0.2)
emit(f"{PINK}agent{RESET} {PEACH}Bot{RESET} {{\r\n", 0.2)
emit(f"    model: {RED}@mock/gpt{RESET}\r\n", 0.2)
emit("    tools: [Greet]\r\n", 0.2)
emit(f"    fn run(q: {YELLOW}Str{RESET}) -> {YELLOW}Str{RESET} {{ q }}\r\n", 0.2)
emit("}\r\n", 0.3)
emit("\r\n", 0.5)

# Syntax check
type_cmd("axon syntax examples/hello.ax", 0.4)
emit(f"{GREEN}✓ Syntax OK{RESET}\r\n", 0.5)
emit("\r\n", 0.5)

# Validate
type_cmd("axon validate examples/hello.ax", 0.4)
emit(f"{GREEN}✓ Type check passed{RESET}\r\n", 0.3)
emit(f"{GREEN}✓ 1 agent, 1 tool, 0 flows validated{RESET}\r\n", 0.5)
emit("\r\n", 0.5)

# Run with mock
type_cmd("axon run examples/hello.ax --mock", 0.4)
emit(f"{BLUE}[Bot]{RESET} Hello, World!\r\n", 0.3)
emit(f"{GRAY}  → tool Greet(\"World\") → \"Hello, World!\"{RESET}\r\n", 0.3)
emit(f"{GREEN}✓ Run completed (mock mode){RESET}\r\n", 0.5)
emit("\r\n", 0.5)

# Compile to TypeScript
type_cmd("axon compile examples/hello.ax --target ts", 0.4)
emit(f"{BLUE}Compiling to TypeScript...{RESET}\r\n", 0.4)
emit(f"{GREEN}✓ Generated: hello.ts{RESET}\r\n", 0.3)
emit(f"{GRAY}  1 agent, 1 tool, 42 lines TypeScript{RESET}\r\n", 0.5)
emit("\r\n", 0.5)

# Final
emit(f"{BLUE}One language. Many worlds.{RESET}\r\n", 0.8)
emit(f"{GRAY}github.com/annapurna-agentics/axon{RESET}\r\n", 1.0)

# Write cast file
header = json.dumps({
    "version": 2,
    "width": 90,
    "height": 28,
    "timestamp": 1718889600,
    "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}
})

with open(CAST, "w", encoding="utf-8") as f:
    f.write(header + "\n")
    for event in events:
        f.write(json.dumps(event) + "\n")

print(f"✓ Cast file created: {CAST}")
print()
print("Convert to GIF using one of:")
print(f"  1. Upload to https://asciinema.org → Download GIF")
print(f"  2. agg {CAST} docs/launch/axon-hero.gif --speed 1.2 --font-size 16")
print(f"  3. terminalizer render {CAST} -o docs/launch/axon-hero.gif")
print()
print("Or use the PowerShell script (scripts/generate_hero_gif.ps1)")
print("which uses Windows Terminal + screen capture.")
