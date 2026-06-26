# AXON Enhancement Roadmap

> Created: 2026-06-25
> Status: Planning notes for future work

---

## Priority Order

| # | Enhancement | Effort | Impact | Status |
|---|------------|--------|--------|--------|
| 1 | Rust evaluator port | High | 5-20x runtime speedup | Pending |
| 2 | RAG real embeddings + vector store | Medium | Makes RAG actually useful | Pending |
| 3 | Prompt/tool caching | Low | 30-80% cost reduction | In Progress |
| 4 | WASM target | Low | Browser/edge deployment | Pending |
| 5 | Parallel tool dispatch | Medium | N-fold speedup for multi-tool | Pending |
| 6 | Structured output | Medium | Reliable LLM data extraction | Pending |
| 7 | Agent versioning + A/B testing | Medium | Safe agent iteration | Pending |
| 8 | Observability enhancement | Medium | Production debuggability | Pending |
| 9 | Security sandboxing | Medium | Safe multi-tenant deployment | Pending |
| 10 | Go/Rust codegen | High | Ecosystem expansion | Pending |

---

## 1. Rust Evaluator Port

Port `src/axon/evaluator.py` (53K, 1144 lines) to Rust as `axon-parser/src/evaluator.rs`.

- Add `evaluator.rs` module that takes IR JSON + runtime scope and evaluates expressions natively
- Expose via PyO3 as `axon_parser.evaluate(ir_json, scope_json)`
- Python `RuntimeExecutor` calls Rust evaluator when `--native` is set, falls back to Python otherwise
- Port all expression types: `think`, `act`, `let`, `if`, `for`, `match`, `go`, `await`, `chan`, `select`, `spawn`, `send`, `receive`, `broadcast`, `discover`, `pool`, `try`, `delegate`, `store`, `observe`, `remember`, `recall`, `forget`
- Challenge: tool dispatch and provider calls need to call back into Python (use PyO3 callbacks)
- Benchmark: target 5-20x speedup for compute-heavy agent loops

## 2. RAG Real Embeddings + Vector Store

Current state: `rag_embedder.py` has only `mock_embed()` (hash-based), `vector_store.py` is brute-force O(n) cosine similarity.

- Add `OpenAIEmbedder` (text-embedding-3-small) behind `[embedders]` optional extra
- Add `SentenceTransformersEmbedder` (local, free, no API key) behind `[embedders]` extra
- Add `ChromaVectorStore` (embedded, zero-config) behind `[rag]` extra
- Extend `postgres_store.py` to add `PgVectorStore` for pgvector-backed search
- Add HNSW index via `hnswlib` or `faiss` for sub-linear search
- Wire embedder/store selection from RAG declaration syntax: `embedder: @openai/text-embed-3` or `embedder: @local/minilm`
- Wire store selection: `store: VectorDB::chroma(path)` or `store: VectorDB::postgres(env.PGVECTOR_URL)`

## 3. Prompt/Tool Caching

Add caching layer to runtime for `think` calls and tool dispatches.

- Add `PromptCache` class: hashes `(prompt_text, model, temperature)` → cached response
- Add `ToolResultCache` class: hashes `(tool_name, sorted_args)` → cached result
- Add `@cache(ttl: 300)` annotation support on prompts and tools
- Add `--no-cache` CLI flag to bypass caching
- Add `--cache-dir` CLI flag for persistent cache storage (disk-backed)
- Add cache hit/miss metrics to `MetricsCollector`
- Add cache stats to trace emitter
- Invalidate on `--mock` (mock provider already deterministic, but keep semantics clean)

## 4. WASM Compilation Target

`axon-parser/Cargo.toml` already has `wasm-bindgen` as optional dep but not wired.

- Add `src/wasm.rs` with `#[wasm_bindgen]` wrappers for `parse_axon`, `validate_axon`, `check_types`, `compile_axon`
- Build with `wasm-pack build --features wasm`
- Publish to npm as `@axon/parser-wasm`
- Use cases: VS Code extension web worker validation, browser-based AXON playground, edge runtime

## 5. Parallel Tool Dispatch

Current evaluator dispatches tools sequentially.

- Add `par` block expression: `par { act WebSearch(q1)?, act WebSearch(q2)? }`
- Dispatches all tools concurrently, waits for all results
- Leverage existing `GoExpr`/`AwaitExpr` infrastructure
- Use `concurrent.futures.ThreadPoolExecutor` or `asyncio.gather` under the hood
- N independent tool calls complete in O(max) instead of O(sum)

## 6. Structured Output / JSON Mode

`ProviderPlugin.call()` returns `Result[str, ProviderError]` — just raw text.

- Add `response_format: str | dict | None` parameter to `ProviderPlugin.call()`
- When `response_format` is a type reference, runtime instructs provider to return JSON
- Validate provider response against AXON type
- Wire `think` expressions to infer structured output from expected type context
- Support OpenAI JSON mode and Anthropic tool-use for structured output

## 7. Agent Versioning + A/B Testing

No concept of agent versioning exists.

- Add `version` field to `agent` declarations: `agent ResearchAgent version: "2.0" { ... }`
- Store version in trace metadata
- Add `axon eval --compare-versions v1 v2` to A/B test against benchmark corpus
- Leverage existing `eval_harness.py` and `trace_replay.py` for regression detection

## 8. Observability — Distributed Tracing Enhancement

`otel_exporter.py` and `otlp_exporter.py` exist but are basic.

- Add OpenTelemetry spans for tool dispatch, provider calls, agent delegations with parent/child relationships
- Add `axon trace --export otlp` to stream traces to Jaeger/Tempo/Grafana
- Add structured logging with correlation IDs
- Add `axon dashboard` — local web UI showing live agent metrics, traces, message bus traffic

## 9. Security — Tool Sandboxing Enhancement

`sandbox.py` and `sandbox_client.py` provide basic restricted Python execution.

- Add `@permission` annotation to tool declarations: `@permission(network: read_only)`
- Enforce permissions in tool registry — reject calls that violate declared permissions
- Add filesystem sandboxing via `pathlib` prefix matching
- Add network sandboxing via allowlist/denylist of domains
- Add CPU/memory limits per tool call

## 10. Codegen — Go Target + MCP Protocol 2.0

`codegen/` has `mcp.py` (FastMCP) and `typescript.py`.

- Add `codegen/go.py` — generate Go MCP server (Kubernetes sidecar deployment)
- Update `codegen/mcp.py` to support MCP Protocol 2.0 (streamable HTTP transport)
- Add `codegen/rust.py` — generate Rust agent server using `axum` + `tokio`
