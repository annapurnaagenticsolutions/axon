# axon-parser

AXON language parser — `.ax` source to portable IR JSON.

This crate implements the AXON parser in Rust, producing IR JSON bit-identical to the Python reference implementation (v0.2 schema). It supports the full AXON declaration surface plus rich error diagnostics, and is distributed as a CLI binary, Rust library, WebAssembly module, and native Python extension (pyo3).

## Features

| Declaration | Annotations | Type Params | Record Fields | Notes |
|-------------|-------------|-------------|---------------|-------|
| `import { … } from "…"` | — | — | — | |
| `type Alias<T> = …` | — | ✅ | ✅ | Record fields extracted for `{ name: Type }` values |
| `rag Name { … }` | ✅ | — | — | `source`, `chunker`, `embedder`, `store`, methods |
| `prompt Name(…) -> T { """…""" }` | ✅ | — | — | Inline param annotations (`@budget`) supported |
| `tool Name(…) -> T { … }` | ✅ | — | — | Multi-line `///` docstrings captured |
| `agent Name { … }` | ✅ | — | — | `model`, `tools`, `memory`, methods |
| `flow Name(…) -> T { … }` | ✅ | — | — | `stage` and `->` edge declarations |

**All declarations support:**
- Top-level annotations (`@trace`, `@cache`, `@managed`, …)
- Method-level annotations (`@schedule`, `@budget`, `@trace`, …)
- Generic type parameters (`List<T>`, `Map<K, V>`, `Result<T, E>`)
- Default parameter values (`param: Type = default`)
- Python-style `textwrap.dedent` for method bodies and prompt templates
- Rich parse errors with source context, line numbers, and suggestions

## Build

Requires Rust 1.70+ (installed via [rustup](https://rustup.rs/)).

```bash
cd axon-parser
cargo build --release
```

The release binary is placed at `target/release/axon-parser.exe` (Windows) or `target/release/axon-parser` (Unix).

## Usage

### CLI

```bash
# Parse an .ax file and print IR JSON to stdout
axon-parser parse file.ax

# Write IR JSON to a file
axon-parser parse file.ax --output ir.json

# Parse a single AXON expression to AST JSON
axon-parser parse-expr '1 + 2 * 3'
axon-parser parse-expr 'if status == "ok" { result.value } else { Err("fail") }' --output ast.json
```

### Library

```rust
use axon_parser::{parse_source, AxonIR};

let source = r#"
@trace
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

type User = { id: Int, name: Str }

@managed
agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]
    fn run(q: Str) -> Str { Greet(q) }
}
"#;

let ir = parse_source(source).unwrap();
println!("{}", serde_json::to_string_pretty(&ir).unwrap());
```

### Expression Parser

The crate also exposes a standalone expression parser for method/tool bodies, producing a typed AST:

```rust
use axon_parser::expression::parse_expression;

let ast = parse_expression(r#"if status == "ok" { result.value } else { Err("fail") }"#).unwrap();
println!("{}", serde_json::to_string_pretty(&ast).unwrap());
// → { "kind": "if", "condition": { "kind": "binary_op", "op": "==", ... }, ... }
```

Supported expression constructs:

| Construct | Example |
|-----------|---------|
| Literals | `42`, `3.14`, `"hello"`, `True`, `None` |
| Variables | `name`, `result.value` (member access), `items[0]` (index) |
| Binary ops | `+`, `-`, `*`, `/`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `&&`, `\|\|` |
| Unary ops | `!flag`, `-count` |
| Calls | `greet("world")`, `List<T>(items)` |
| Blocks | `{ a; b; c }` |
| Control flow | `if cond { … } else { … }`, `while cond { … }`, `for item in items { … }`, `match val { A => 1 }` |
| Loop control | `break`, `continue` |
| Let binding | `let x = 1 in x + 2` |
| Agentic keywords | `act Tool(arg: val)`, `delegate Agent(arg: val)`, `think "msg"`, `observe name: val`, `store memory = "data"` |
| Result/Option | `Ok(42)`, `Err("msg")`, `Some(v)`, `None` |
| Model calls | `model.complete("prompt")` |
| String interpolation | `"Hello {name}!"` |

Errors include **line and column** information:

```
ExprParseError at 3:5: Expected expression
```

## Benchmarks

The Rust parser is benchmarked against the Python reference parser via its WASM build (which IS the Rust parser running in Node.js/V8).

Run benchmarks locally:

```bash
cd ..
# Generate stress-test fixtures
python tests/gen_stress_axon.py --agents 50 --tools 20 --methods 5 --body-lines 3 -o tests/fixtures/stress_small.ax
python tests/gen_stress_axon.py --agents 200 --tools 50 --methods 10 --body-lines 5 -o tests/fixtures/stress_large.ax

# Run benchmark
python tests/benchmark_parser.py
```

### Representative results (Windows, 50 iterations)

| File | Size | Python | Rust (WASM) | Speedup |
|------|------|--------|-------------|---------|
| hello.ax | 228 B | 0.08 ms | 0.07 ms | **1.1x** |
| customer_support.ax | 1,456 B | 0.26 ms | 0.09 ms | **2.9x** |
| stress_small.ax | 50 KB | 21.5 ms | 0.92 ms | **23.4x** |
| stress_large.ax | 534 KB | 267.0 ms | 7.4 ms | **35.9x** |

The Rust parser scales dramatically with file size — **36x faster** on a half-megabyte source. Throughput on the large file: **3.7 parses/sec** (Python) vs **134.6 parses/sec** (Rust).

## Native Python Bindings (pyo3)

For Python projects that want maximum performance without the WASM/JS overhead, build the native extension:

```bash
# Install maturin (once)
pip install maturin

# Build and install in the current virtualenv
maturin develop --features python

# Or build a wheel
maturin build --features python --release
```

### Usage

```python
import axon_parser

# Parse full .ax source to IR dict
ir = axon_parser.parse_axon('agent Bot { model: @mock/gpt fn run() -> Str { "hi" } }')
print(ir['version'])  # '0.2.0'

# Parse a single expression to AST dict
ast = axon_parser.parse_expr('1 + 2 * 3')
print(ast['kind'])  # 'binary_op'
```

The pyo3 binding returns a native Python `dict` directly (no JSON string intermediate), giving the fastest possible Python integration.

## WASM Size Optimization

Install `wasm-opt` (from the Binaryen toolkit) to shrink the `.wasm` binary:

```bash
npm install -g binaryen
wasm-opt -Oz pkg/axon_parser_bg.wasm -o pkg/axon_parser_bg.wasm
```

Typical result: **155 KB → 128 KB** (~18% reduction). All three targets (web, bundler, node) can be optimized.

## Playground

Open `playground/index.html` in any browser (served via static file server) for a live AXON-to-IR playground:

```bash
cd playground
python -m http.server 8080
# open http://localhost:8080
```

Features:
- **Split-pane editor** — AXON source on the left, IR JSON on the right
- **3 built-in examples** — hello.ax, hello_run.ax, customer_support.ax
- **Real-time parsing** — click Parse or press the button to generate IR
- **JSON syntax highlighting** — colored keys, strings, numbers, booleans
- **Copy / Download** — copy IR JSON to clipboard or download as `.json`
- **Error display** — parse errors shown inline with the output panel
- **Draggable divider** — resize source/output panels

## npm Install

```bash
npm install @axon/parser
```

### Node.js

```javascript
const { parse_axon, parse_expr } = require('@axon/parser');

// Parse full .ax source to IR
const irJson = parse_axon('agent Bot { model: @mock/gpt fn run() -> Str { "hi" } }');
console.log(JSON.parse(irJson));

// Parse a single expression to AST
const astJson = parse_expr('1 + 2 * 3');
console.log(JSON.parse(astJson));
```

### Bundler (Vite, Webpack, Rollup)

```javascript
import { parse_axon, parse_expr } from '@axon/parser';
const irJson = parse_axon('agent Bot { model: @mock/gpt fn run() -> Str { "hi" } }');
console.log(JSON.parse(irJson));

const astJson = parse_expr('if ready { go() } else { wait() }');
console.log(JSON.parse(astJson));
```

### Browser (ESM, no bundler)

```javascript
import init, { parse_axon } from '@axon/parser/web';
await init();
const json = parse_axon('agent Bot { model: @mock/gpt fn run() -> Str { "hi" } }');
console.log(JSON.parse(json));
```

## WASM Build (from source)

The parser can be compiled to WebAssembly for use in browsers and Node.js.

### Build

```bash
# Install wasm32 target (once)
rustup target add wasm32-unknown-unknown

# Install wasm-bindgen CLI (once)
cargo install wasm-bindgen-cli

# Build release WASM (library only — excludes CLI binary)
cargo build --lib --target wasm32-unknown-unknown --release --features wasm

# Generate JS bindings
wasm-bindgen --target web --out-dir pkg target/wasm32-unknown-unknown/release/axon_parser.wasm
```

### Browser Usage

Serve `demo.html` and the `pkg/` directory from any static file server:

```bash
python -m http.server 8080
```

Then open `http://localhost:8080/demo.html`.

### JS API

```javascript
import init, { parse_axon } from './pkg/axon_parser.js';
await init();
const json = parse_axon('agent Bot { model: @mock/gpt fn run() -> Str { "hi" } }');
console.log(JSON.parse(json));
```

## Conformance

Run the Python conformance test to verify Rust IR matches Python IR:

```bash
cd ..
python -m pytest tests/test_rust_ir_conformance.py -v
```

## IR Schema

The emitted IR follows the AXON IR v0.2 schema used by the Python runtime. Top-level fields:

- `version` — `"0.2.0"`
- `imports` — list of `ImportDef`
- `type_aliases` — list of `TypeAliasDef`
- `rags` — list of `RagDef`
- `prompts` — list of `PromptDef`
- `tools` — list of `ToolDef`
- `agents` — list of `AgentDef`
- `flows` — list of `FlowDef`
- `global_security` — `SecurityPolicy`
- `metadata` — arbitrary JSON object

## License

MIT
