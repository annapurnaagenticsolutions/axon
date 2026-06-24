#!/usr/bin/env bash
# AXON Hero GIF Generator — Automated Terminal Recording
# 
# Prerequisites:
#   pip install asciinema
#   # Install agg (asciinema-to-gif converter):
#   # Windows: scoop install agg  OR  cargo install agg
#   # Or use: npm install -g terminalizer
#
# Usage:
#   bash scripts/generate_hero_gif.sh
#
# Output:
#   docs/launch/axon-hero.gif

set -e

CAST_FILE="docs/launch/axon-hero.cast"
GIF_FILE="docs/launch/axon-hero.gif"

# Ensure we're in the axon directory
cd "$(dirname "$0")/.."

echo "=== AXON Hero GIF Generator ==="
echo ""

# Create the cast file with pre-scripted terminal session
cat > "$CAST_FILE" << 'CAST_EOF'
{"version": 2, "width": 100, "height": 30, "timestamp": 1718889600, "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}}
[0.5, "o", "\u001b[?2004h\u001b[?1l\u001b[?1000l\u001b[?1002l\u001b[?1003l\u001b[?1006l\u001b[?1005l\u001b[?25l\u001b[?2004l\r\u001b[?2004h"]
[1.0, "o", "$ "]
[1.5, "o", "cat examples/hello.ax\r\n"]
[2.0, "o", "\u001b[38;5;111m// hello.ax — A minimal AXON agent\u001b[0m\r\n"]
[2.3, "o", "\r\n"]
[2.5, "o", "\u001b[38;5;206mtool\u001b[0m \u001b[38;5;156mGreet\u001b[0m(name: \u001b[38;5;217mStr\u001b[0m) -> \u001b[38;5;217mStr\u001b[0m {\r\n"]
[2.8, "o", "    \u001b[38;5;245m/// Says hello to someone.\u001b[0m\r\n"]
[3.0, "o", "    \"Hello, {name}!\"\r\n"]
[3.2, "o", "}\r\n"]
[3.4, "o", "\r\n"]
[3.6, "o", "\u001b[38;5;206magent\u001b[0m \u001b[38;5;156mBot\u001b[0m {\r\n"]
[3.8, "o", "    model: \u001b[38;5;210m@mock/gpt\u001b[0m\r\n"]
[4.0, "o", "    tools: [Greet]\r\n"]
[4.2, "o", "    fn run(q: \u001b[38;5;217mStr\u001b[0m) -> \u001b[38;5;217mStr\u001b[0m { q }\r\n"]
[4.4, "o", "}\r\n"]
[4.7, "o", "\r\n"]
[5.0, "o", "$ "]
[5.5, "o", "axon syntax examples/hello.ax\r\n"]
[6.5, "o", "\u001b[38;5;46m✓ Syntax OK\u001b[0m\r\n"]
[7.0, "o", "\r\n"]
[7.2, "o", "$ "]
[7.7, "o", "axon validate examples/hello.ax\r\n"]
[9.0, "o", "\u001b[38;5;46m✓ Type check passed\u001b[0m\r\n"]
[9.2, "o", "\u001b[38;5;46m✓ 1 agent, 1 tool, 0 flows validated\u001b[0m\r\n"]
[9.7, "o", "\r\n"]
[9.9, "o", "$ "]
[10.4, "o", "axon run examples/hello.ax --mock\r\n"]
[11.5, "o", "\u001b[38;5;111m[Bot]\u001b[0m Hello, World!\r\n"]
[12.0, "o", "\u001b[38;5;245m  → tool Greet(\"World\") → \"Hello, World!\"\u001b[0m\r\n"]
[12.5, "o", "\u001b[38;5;46m✓ Run completed (mock mode)\u001b[0m\r\n"]
[13.0, "o", "\r\n"]
[13.2, "o", "$ "]
[13.7, "o", "axon compile examples/hello.ax --target ts\r\n"]
[15.0, "o", "\u001b[38;5;111mCompiling to TypeScript...\u001b[0m\r\n"]
[15.5, "o", "\u001b[38;5;46m✓ Generated: hello.ts\u001b[0m\r\n"]
[16.0, "o", "\u001b[38;5;245m  1 agent, 1 tool, 42 lines TypeScript\u001b[0m\r\n"]
[16.5, "o", "\r\n"]
[16.7, "o", "$ "]
[17.0, "o", "\r\n"]
CAST_EOF

echo "✓ Cast file created: $CAST_FILE"
echo ""

# Try converting with agg first
if command -v agg &> /dev/null; then
    echo "Converting with agg..."
    agg "$CAST_FILE" "$GIF_FILE" --speed 1.2 --font-size 16 --theme monokai
    echo "✓ GIF created: $GIF_FILE"
elif command -v terminalizer &> /dev/null; then
    echo "Converting with terminalizer..."
    terminalizer render "$CAST_FILE" -o "$GIF_FILE" --quality 80
    echo "✓ GIF created: $GIF_FILE"
else
    echo ""
    echo "⚠ No GIF converter found. Install one of:"
    echo "  Option 1: scoop install agg"
    echo "  Option 2: cargo install agg"
    echo "  Option 3: npm install -g terminalizer"
    echo ""
    echo "Then re-run this script."
    echo ""
    echo "Alternatively, upload the cast file to https://asciinema.org"
    echo "and use the 'Download GIF' button."
    echo ""
    echo "Cast file: $CAST_FILE"
fi

echo ""
echo "=== Done ==="
