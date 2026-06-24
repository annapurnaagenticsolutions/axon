# AXON Hero GIF Recording Guide

**Goal:** 20-second loopable GIF, no sound, that makes someone want to try AXON immediately.

## What the GIF Should Show

A terminal session demonstrating the core AXON workflow in ~20 seconds:

1. **Write .ax file** (3s) — show `hello.ax` or a small agent in an editor
2. **Syntax check** (2s) — `axon syntax examples/hello.ax` → green ✓
3. **Validate** (2s) — `axon validate examples/hello.ax` → green ✓
4. **Run with mock** (3s) — `axon run examples/hello.ax --mock` → output
5. **Compile to TypeScript** (4s) — `axon compile examples/hello.ax --target ts` → show TS output
6. **Show the result** (3s) — the generated TypeScript file in editor

## Recording Setup

### Tools needed:
- **Windows:** Use `screenToGif` (free, lightweight) or OBS Studio + ffmpeg
- **Or:** Use `asciinema` + `agg` for terminal-only GIFs (cleaner, smaller)

### Terminal setup:
- Use Windows Terminal or a clean terminal with dark background
- Font: Cascadia Code or Fira Code (monospace, ligatures)
- Font size: 16-18pt (readable in GIF)
- Window size: 1200x600 (16:9 or 2:1 aspect ratio)
- Hide cursor when not typing (for cleaner look)

### Recording steps:

```bash
# 1. Open terminal in axon directory
cd d:\vision_agentic\annapurnaagenticsolutions\axon

# 2. Show the .ax file
cat examples/hello.ax
# (or open in VS Code with AXON extension for syntax highlighting)

# 3. Run the commands in sequence
axon syntax examples/hello.ax
axon validate examples/hello.ax
axon run examples/hello.ax --mock
axon compile examples/hello.ax --target ts

# 4. Show the output
cat examples/hello.ts  # or the generated TS file
```

### Timing:
- Type commands at a readable speed (not too fast)
- Pause 1s after each command's output
- Total: 15-20 seconds
- Loop seamlessly (end on the same state as beginning)

### Post-production:
- Crop to content area (remove window chrome)
- Reduce to 15fps (smaller file, still smooth for terminal)
- Optimize with: `gifsicle --optimize=3 --colors 64`
- Target size: < 5MB for GitHub README
- Dimensions: 1200x600 or 800x400

## Alternative: Asciinema approach (cleaner)

```bash
# Record
asciinema rec axon-demo.cast

# Run the demo commands
cat examples/hello.ax
axon syntax examples/hello.ax
axon validate examples/hello.ax
axon run examples/hello.ax --mock
axon compile examples/hello.ax --target ts

# Stop recording (Ctrl+D or exit)

# Convert to GIF
agg axon-demo.cast axon-hero.gif --speed 1.5 --font-size 16
```

## Where to place the GIF

In `README.md`, at the very top, after the title:

```markdown
# AXON

> A typed DSL for autonomous agents. Compiles to Python + TypeScript.

![AXON Demo](docs/launch/axon-hero.gif)

## Quick Start
...
```

## Loom Demo (90-180s)

For the Loom video (longer demo), record:

1. **Problem statement** (15s) — "Building multi-agent pipelines in LangChain takes 500+ lines with no type safety"
2. **Show AXON solution** (30s) — open `research_pipeline.ax`, walk through the key parts
3. **Compile and run** (30s) — `axon validate`, `axon run --mock`, `axon compile --target ts`
4. **Show TypeScript output** (15s) — "One source, two targets"
5. **Call to action** (15s) — "Clone the repo, try it with --mock, no API key needed"

Upload to YouTube unlisted, embed in blog post.
