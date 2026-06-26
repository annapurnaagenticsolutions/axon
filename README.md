# AXON — The Programming Language for Autonomous Agents

![License](https://img.shields.io/badge/license-MIT-blue)
![Tests](https://img.shields.io/badge/tests-1200%2B%20passing-green)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Status](https://img.shields.io/badge/status-Alpha-orange)

```
     _    __  ______   ____  _   _
    / \   \ \/ /  _ \ / ___|| \ | |
   / _ \   \  /| |_) | |  _ |  \| |
  / ___ \  /  \|  _ <| |_| || |\  |
 /_/   \_\/_/\_\_| \_\\____||_| \_|
```

> A typed DSL where agents, tools, memory, RAG, and orchestration are first-class language constructs — not framework boilerplate. Compiles to Python + TypeScript.

AXON is the first programming language where **agents, tools, memory, RAG, and orchestration are first-class language constructs** — not framework boilerplate.

Write your agents in `.ax` files. Compile to Python MCP servers or TypeScript modules. Deploy to Docker or Fly.io in one command.

> **Pair with [AgentOps Mesh](https://github.com/annapurnaagenticsolutions/open-enterprise-agentops-mesh)** — the open-source AgentOps control plane that governs AXON agents through a 9-gate workflow (suitability, risk, data, evaluation, policy, security, audit, approval, readiness). Run both together: `docker compose -f docker-compose.unified.yml up`. See the [unified demo](../DEMO.md).

> **Status:** Compiler + executing runtime + Rust native parser/validator/type checker + distributed mesh runtime + VS Code extension + debugger + profiler. **Pre-production — sophisticated reference implementation.**

---

## 30-Second Quickstart

```bash
pip install axon-dsl

# Write an agent
cat > hello.ax << 'EOF'
agent Hello {
    model: @mock/model
    fn run(name: Str) -> Str {
        "Hello, " + name
    }
}
EOF

# Run it
axon run hello.ax --arg name=World

# Compile to TypeScript
axon compile hello.ax --target ts -o hello.ts

# Build a production MCP server
axon build hello.ax -o server.py

# Deploy
axon deploy --target fly
```

---

## What Makes AXON Different

| Feature | What You Get |
|---------|-------------|
| **Native Agent Primitives** | `spawn`, `pause`, `resume`, `terminate` are keywords, not library calls |
| **Type-Safe Tooling** | Tools are typed interfaces validated by the compiler |
| **Multi-Target Compilation** | One `.ax` source → Python MCP server or TypeScript module |
| **RAG Built In** | `rag` declaration with chunking, embedding, and vector search |
| **Flow Orchestration** | `flow` keyword with DAG scheduling across agents |
| **Debugger + Profiler** | `axon debug trace.axontrace` — step through execution, breakpoints, watches, memory inspection, export. `axon profile` — per-tool p50/p95/p99 latency, think timing, hotspot detection, CSV export. `axon replay` — trace replay with regression detection |
| **Model Router** | Route calls by cost, latency, or quality with one annotation |
| **Deploy Anywhere** | `axon deploy --target docker` or `--target fly` |

---

## See It in Action

```bash
# 1. Write your agent
axon new research_bot

# 2. Validate and format
axon validate examples/research_pipeline.ax
axon format examples/research_pipeline.ax

# 3. Run with mock provider (safe, no API keys)
axon run examples/research_pipeline.ax --query "What is AXON?"

# 4. Inspect the execution trace
axon debug trace.axontrace --non-interactive
# → [1/47] THINK  agent: ResearchCoordinator  content: Starting research...
# → [2/47] ACT     agent: ResearchCoordinator  tool: WebSearch
# → ...

# 5. Profile performance
axon profile trace.axontrace
# → AXON Profile: 4200.5ms overall, 47 events
# →   ResearchCoordinator: 1800.2ms, 12 events, 3 acts (avg 120.0ms)

# 6. Compare traces for regressions
axon replay baseline.jsonl --compare candidate.jsonl
# → Trace Comparison: baseline=4200.5ms -> candidate=5100.0ms
# →   Overall: +899.5ms (+21.4%) REGRESSION

# 7. Compile to TypeScript for your frontend
axon compile examples/research_pipeline.ax --target ts -o research.ts

# 7. Build production MCP server
axon build examples/research_pipeline.ax -o server.py

# 8. Deploy
axon deploy --target fly
```

---

## Showcase: Multi-Agent Research Pipeline

```axon
agent ResearchCoordinator {
    model: @anthropic/claude-4
    tools: [WebSearch, ResearchDocs.retrieve]

    fn run(query: ResearchQuery) -> Result<ResearchReport, AgentError> {
        let planner = spawn QueryPlanner()
        let plan = await planner.plan(query)?

        let pool = pool(size: 3, target: ResearchAgent)
        let results = []
        for sub in plan {
            results = results + (await pool.investigate(sub)?)
        }

        let summary = await spawn SummarizerAgent().summarize(results)?
        let facts = await spawn FactCheckerAgent().verify_all(summary)?

        Ok(ResearchReport { topic: query.topic, summary, facts })
    }
}
```

**See the full example:** [`examples/research_pipeline.ax`](examples/research_pipeline.ax)

---

## Why AXON exists

Most AI agent systems treat agents, tools, prompts, memory, RAG, traces, and orchestration as framework-level concepts. AXON explores the opposite direction: these concepts become first-class language constructs.

The long-term design is grounded in five stable agent primitives:

```text
Perceive  -> observe
Recall    -> memory / rag
Reason    -> think / @plan / @summarize / @classify
Act       -> act / tool / flow
Learn     -> store / future learning semantics
```

---

## What works today

Implemented declaration parsing:

- type aliases and record-style custom types
- `import`
- `type`
- `prompt`
- `rag`
- `flow`
- `tool`
- `agent`

Implemented tooling:

- version metadata with `axon version`
- environment/capability metadata with `axon info`
- safe project/workspace metadata with `axon project-info`
- Phase 1 foundation auditing with `axon foundation-audit`
- release handoff checklist generation with `axon handoff`
- contributor and LLM task-ticket templates with `axon task-template`
- runtime design RFC templates with `axon runtime-rfc-template`
- non-executing runtime-plan inspection with `axon runtime-plan`, corpus checks with `axon runtime-plan-corpus`, and review/docs consistency checks with `axon runtime-plan-review-check`
- first runtime RFC draft in `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`
- release notes and changelog generation with `axon release-notes` / `axon changelog`
- release bundle manifest generation with `axon release-bundle-manifest`
- dependency and optional-extra auditing with `axon deps` / `axon dependency-audit`
- repository hygiene and ignore-rule auditing with `axon hygiene` / `axon repo-hygiene`
- local Git hook template and quality-gate running with `axon precommit`
- project creation with `axon new`
- project initialization with `axon init`
- safe provider config inspection with `axon config`
- syntax diagnostics with `axon syntax`
- static semantic validation with `axon validate`
- stable AST snapshots with `axon ast`
- canonical source formatting with `axon format`
- checked-in formatted-source golden snapshots for the example corpus
- project quality checks with `axon check-project` / `axon doctor`
- FastMCP stub generation with `axon build`
- dry-run or run generated servers with `axon serve`
- runtime health check with `axon health`
- executing agent runtime with `axon run`
- interactive expression evaluation with `axon repl`
- agent lifecycle management (spawn, pause, resume, terminate) with `axon agent`
- agent supervision trees with restart strategies (one-for-one, one-for-all, rest-for-one) with `axon supervisor`
- hot-reload source watching for agents with `axon watch`
- agent checkpoint and restore with `axon agent checkpoint` / `axon agent restore`
- runtime metrics collection and export with `axon metrics`
- streaming provider responses with `axon run --stream` and `axon agent spawn --stream`
- REST API server with agent lifecycle, streaming, and metrics via `axon serve-api`
- SQLite/PostgreSQL persistence store for memory, traces, and checkpoints
- OpenTelemetry-style trace correlation IDs across agent delegations, provider calls, and tool dispatches
- Docker / Kubernetes production deployment with hardened images and health checks
- Load testing and chaos engineering harness for resilience validation
- Secret management with pluggable backends (env, file, keyring, Vault) via `axon secret`
- Intermediate Representation (IR) compilation with `axon compile --ir` for polyglot runtimes
- generated-server smoke testing without FastMCP installed with `axon smoke`
- static AEL preview extraction with `axon trace-preview`
- trace-log reading and filtering with `axon trace-read` / `axon trace-log`
- trace replay with exact event matching via `axon replay`
- runtime checkpoint and restore with `--checkpoint` and `--memory`
- multi-agent runtime with `delegate`, named agent execution (`--agent`), and in-memory message bus (`send`/`receive`)
- distributed multi-agent runtime with Redis/NATS message bus (`--mesh redis --mesh-url redis://localhost:6379`), service registry, agent discovery (`discover`), and remote tool dispatch (`remote_call`)
- Rust native parser, validator, type checker, and IR compiler via PyO3 (`--native` flag); 108 Rust tests passing
- persistent semantic memory with `remember`, `recall`, `forget` (RFC #009)
- token budget estimation with `axon token-budget`
- AgentOps Mesh governance submission with `axon govern` — compile `.ax` into governance JSON and submit to Mesh
- CI/CD workflow generation with `axon ci-template` — GitHub Actions and GitLab CI templates with optional governance step
- plain-English error explanations with `axon explain` — validation diagnostics with fix suggestions
- package management with `axon add` / `axon remove` — install and remove AXON packages from git repos
- performance benchmarking with `axon eval` — built-in benchmarks with regression detection
- runtime observability dashboard with `axon dashboard` — trace summaries, metrics, and live web UI with `--serve`
- browser-based playground with `axon playground` — parse, validate, and generate code from AXON source in the browser

Implemented safety foundations:

- rich syntax diagnostics with line, column, snippet, caret, and hints
- validator diagnostics for common semantic mistakes
- golden error snapshots for parser/validator UX stability
- AST snapshots for parser regression stability
- AEL trace event model for `think`, `act`, `observe`, `store`, `memory_remember`, `memory_recall`, `memory_forget`, `message_sent`, and `message_received`
- generated release notes for bundle handoff and changelog discipline
- conservative source formatting that does not execute AXON code
- formatter golden snapshots for reviewable formatting changes
- redacted `axon.toml` configuration display so secrets are not printed accidentally
- stdlib-only compiler-core dependency audit so runtime integrations stay behind optional extras
- repository hygiene audit so generated outputs, caches, traces, and local secrets stay ignored without hiding source files
- explicit runtime-boundary documentation and RFC-gated runtime feature implementation

## Install locally

From the repository root:

```bash
python -m pip install -e .
```

For development tests:

```bash
python -m pip install -e ".[dev]"
pytest
```

To run generated MCP servers, install the optional serving dependency:

```bash
python -m pip install -e ".[serve]"
```

The compiler itself does not require FastMCP. Only generated server runtime execution needs it.

## Quick start


Check the installed AXON version and environment metadata:

```bash
axon version
axon info
axon project-info .
axon foundation-audit .
axon handoff .
axon task-template --number 36 --title "Contributor Guide + Task Ticket Template"
axon runtime-rfc-template --number 1 --title "Minimal Runtime Proposal"
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json
axon runtime-plan-corpus .
# Review docs/runtime-rfcs/0001-minimal-non-executing-runtime.md before runtime implementation
axon release-notes --change "prepared release notes" --tests "pytest passed"
axon release-bundle-manifest . --output release-bundle-manifest.json
axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown
axon deps .
axon hygiene .
axon precommit print
```

Create a new project:

```bash
axon new my-agent-project
cd my-agent-project
```

Validate and smoke-test the starter agent:

```bash
axon syntax examples/hello.ax
axon validate examples/hello.ax
axon smoke examples/hello.ax
```

Run an agent with lifecycle management:

```bash
axon run examples/hello.ax --arg q=world --mock
axon agent spawn examples/hello.ax --name bot-1 --arg q=world --mock
axon agent status bot-1
axon agent pause bot-1
axon agent resume bot-1
axon agent terminate bot-1
axon agent list
```

Run a supervision tree:

```bash
axon supervisor start --name my-sup --strategy one_for_one \
  --child examples/hello.ax::bot-1 --child examples/hello.ax::bot-2
axon supervisor status my-sup
axon supervisor stop my-sup
```

Watch an agent for source changes (auto-reload):

```bash
axon watch start examples/hello.ax --name bot-1 --arg q=world --mock
axon watch stop bot-1
```

Checkpoint and restore an agent:

```bash
axon agent spawn examples/hello.ax --name bot-1 --arg q=world --mock
axon agent checkpoint bot-1 --output bot1_ckpt.json
axon agent terminate bot-1
axon agent restore bot-1 --snapshot bot1_ckpt.json --mock
```

View and export runtime metrics:

```bash
axon run examples/hello.ax --arg q=world --metrics
axon metrics show
axon metrics export --output metrics.json --format json
axon metrics reset
```

Stream provider responses in real time:

```bash
axon run examples/hello.ax --arg q=hello --stream --mock
axon agent spawn examples/hello.ax --name bot-1 --arg q=hello --stream --mock
```

Run with the Rust native parser (requires `axon_parser` PyO3 module built from `axon-parser/`):

```bash
axon run examples/hello.ax --arg q=world --native
```

The `--native` flag uses the Rust `axon-parser` crate for parsing, validation, and type checking via PyO3. If the Rust module is not installed, it falls back to the Python parser automatically.

Run agents in distributed mode with Redis mesh:

```bash
# Start Redis (via WSL2, Docker, or Memurai on Windows)
# docker run -d -p 6379:6379 redis

# Run agent A registered in the service registry
axon run examples/hello.ax --mesh redis --mesh-url redis://localhost:6379 --arg q=world

# In another process, run agent B that can discover and call agent A
axon run examples/debate.ax --mesh redis --mesh-url redis://localhost:6379
```

The `--mesh` flag enables cross-process agent communication via Redis (or NATS). Agents self-register in the service registry, discover each other with `discover()`, and dispatch remote tool calls with `remote_call(agent_name, tool_name, **kwargs)`.

Launch an interactive REPL session:

```bash
axon repl
axon repl examples/hello.ax --live --provider groq
```

Start the AXON REST API server:

```bash
axon serve-api --host 0.0.0.0 --port 8000 --api-key secret123
curl -H "X-API-Key: secret123" http://localhost:8000/agents
```

Generate a FastMCP Python server:

```bash
axon build examples/hello.ax -o hello_server.py
```

Dry-run serve without starting FastMCP:

```bash
axon serve examples/hello.ax --dry-run
```

Start the generated server after building it:

```bash
axon serve examples/hello.ax
```

## Minimal AXON example

```axon
type UserName = Str

prompt GreetingPrompt(name: UserName, @budget(tokens: 100)) -> Str {
    """
    Write a greeting for {name}.
    """
}

tool Greet(name: UserName) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]

    fn run(q: UserName) -> Str {
        let result = act Greet(name: q)?
        Ok(result)
    }
}
```


## Example corpus

The `examples/` directory now contains a validated reference corpus covering both minimal and realistic AXON patterns:

- `hello.ax` — minimal tool + agent
- `types.ax` — type aliases and record-style custom types
- `prompts.ax` — prompt declarations with `@budget`
- `rag.ax` and `customer_support.ax` — RAG-backed support workflows
- `flow.ax` and `debate.ax` — flow declarations and multi-agent orchestration shapes
- `trace_preview.ax` — static AEL trace extraction
- `github_triage.ax`, `invoice_extraction.ax`, `monitoring_alerts.ax`, `meeting_notes.ax`, and `data_analysis.ax` — realistic end-to-end agent examples

Every `.ax` example is covered by automated tests for parsing, syntax diagnostics, validation, FastMCP stub generation, generated Python compilation, smoke testing, stable AST rendering, formatter round-tripping, and formatted-source golden snapshots.



## Foundation audit workflow

`axon foundation-audit` is the Phase 1 consolidation checkpoint. It inspects whether the parser, validator, codegen smoke harness, formatter snapshots, runtime-plan boundary, runtime governance, release handoff, examples, docs, and tests are present and aligned.

```bash
axon foundation-audit .
axon foundation-audit . --json
```

The command is inspection-only. It does not execute agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces. It complements `axon deps`, `axon hygiene`, `axon check-project`, `axon runtime-governance`, and `axon release-artifacts` during handoff.

## Runtime-plan workflow

Runtime plans are AXON's current safe bridge toward future execution. They inspect parsed and validated declarations, summarize agents/tools/prompts/RAG/flows, and report capability flags without executing anything.

Use them when reviewing runtime-adjacent changes:

```bash
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --json
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json --root .
axon runtime-plan-corpus .
```

The runtime-plan workflow is documented in `docs/RUNTIME_PLAN.md`. It is tied to Runtime RFC #001 (`docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`) and the runtime boundary (`docs/RUNTIME_BOUNDARY.md`). The only enabled runtime capability is `declaration_inspection`; method execution, provider calls, tool dispatch, memory mutation, RAG indexing/retrieval, flow execution, trace replay, secret resolution, and FastMCP runtime imports remain disabled.

## CLI command reference


### `axon version`

Print the AXON package version. Use `--json` for machine-readable output.

```bash
axon version
axon version --json
```

### `axon info`

Print safe environment and capability metadata for bug reports. This command does not print provider secrets.

```bash
axon info
axon info --json
axon info --path .
axon info --config axon.toml
```


### `axon handoff`

```bash
axon handoff .
axon handoff . --json
axon handoff . --output HANDOFF_CHECKLIST.md
axon handoff . --full
```

Generates a safe release handoff checklist. It connects `axon version`, `axon info`, `axon project-info`, `axon deps`, `axon hygiene`, `axon check-project`, `axon precommit run`, `axon runtime-governance-evidence`, `axon release-bundle-manifest`, and `axon release-notes` into one repeatable workflow for bundle handoff and reviewer summaries. The command prints commands to run and documents to review; it does not execute AXON agents, call providers, resolve secrets, or require FastMCP.

### `axon runtime-plan`

Build a validated, non-executing runtime plan for one AXON file. It summarizes declarations and reports which runtime capabilities are intentionally disabled. Use `--json` for machine-readable output, `--write` to create a golden runtime-plan snapshot, and `--check` to compare against one.

```bash
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --json
axon runtime-plan examples/hello.ax --write tests/snapshots/runtime_plan/examples/hello.runtime-plan.json
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json
```

### `axon release-bundle-manifest`

```bash
axon release-bundle-manifest .
axon release-bundle-manifest . --json
axon release-bundle-manifest . --output release-bundle-manifest.json
axon release-bundle-manifest . --output RELEASE_BUNDLE_MANIFEST.md --format markdown
```

Builds a deterministic, inspection-only manifest for release bundle handoff. It lists core project files, docs, examples, snapshots, golden errors, quality-gate files, and expected generated evidence artifacts. Generate `release-bundle-manifest.json` in every final release handoff bundle, and optionally generate `RELEASE_BUNDLE_MANIFEST.md` for reviewers. It does not execute AXON agents, call providers, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.


### `axon release-artifacts-check`

```bash
axon release-artifacts-check .
axon release-artifacts-check . --json
axon release-artifact-consistency .
```

Checks that the standard release handoff artifact names stay aligned across the artifact writer, release bundle manifest, handoff checklist, README, and release documentation. The canonical artifact list is `HANDOFF_CHECKLIST.md`, `handoff-checklist.json`, `RELEASE_NOTES.md`, `release-notes.json`, `runtime-governance.json`, `RUNTIME_GOVERNANCE_EVIDENCE.md`, `runtime-plan-corpus.json`, `dependency-audit.json`, `hygiene.json`, `release-bundle-manifest.json`, `RELEASE_BUNDLE_MANIFEST.md`, `release-artifact-consistency.json`, and `release-artifacts.json`. See `docs/RELEASE_ARTIFACTS_CONSISTENCY.md`.

### `axon task-template`

Print or write a self-contained AXON implementation ticket template. Use this when assigning work to another developer or LLM coding model so the task has enough context to be implemented without hidden chat history.

```bash
axon task-template
axon task-template --number 36 --title "Contributor Guide + Task Ticket Template"
axon runtime-rfc-template --number 1 --title "Minimal Runtime Proposal"
axon runtime-plan examples/hello.ax
axon runtime-plan examples/hello.ax --check tests/snapshots/runtime_plan/examples/hello.runtime-plan.json
axon runtime-plan-corpus .
# Review docs/runtime-rfcs/0001-minimal-non-executing-runtime.md before runtime implementation
axon task-template --number 37 --title "Next Focused Task" --module src/axon/example.py --output axon_task_37.md
axon task-template --json
```


### `axon runtime-plan-corpus`

Check runtime-plan snapshots and disabled runtime capabilities across an AXON example corpus. This verifies that every example can produce a runtime plan, every checked-in runtime-plan snapshot matches, no orphan runtime-plan snapshots exist, and executable capabilities remain disabled.

```bash
axon runtime-plan-corpus .
axon runtime-plan-corpus . --json
axon runtime-plan-corpus . --examples-dir examples --snapshot-dir tests/snapshots/runtime_plan/examples
```

### `axon release-notes` / `axon changelog`

Generate Markdown or JSON release notes for an AXON project. This command combines explicit change bullets, explicit validation evidence, safe project metadata, the current CLI command surface, implemented capabilities, and the discovered `.ax` source corpus. It does not inspect git history and does not print provider secrets.

```bash
axon release-notes --change "added release notes generator" --tests "240 passed"
axon release-notes --version 0.1.0 --date 2026-05-31 --path .
axon release-notes --json
axon release-notes --output RELEASE_NOTES.md
axon changelog --change "updated docs" --tests "pytest passed"
```

### `axon new`

Create a new AXON project skeleton.

```bash
axon new my-agent-project
axon new my-agent-project --force
```

Generated starter files:

```text
axon.toml
examples/hello.ax
README.md
.gitignore
traces/.gitkeep
```

By default, `axon new` refuses to write into a non-empty directory. Use `--force` only when intentional.

### `axon init`

Initialize AXON starter files in an existing directory.

```bash
axon init
axon init . --force
axon init path/to/project
```

Without `--force`, existing starter files are preserved.


### `axon project-info`

Summarize safe AXON project/workspace metadata in one report. The command reports source files, examples, docs, snapshots, golden errors, trace logs, CI workflows, Git hooks, config presence, provider names, and lightweight hygiene/dependency audit status. It does not resolve secrets, execute agents, call providers, or require FastMCP.

```bash
axon project-info .
axon project-info . --json
```

Use this when preparing a handoff, bug report, or release summary.

### `axon deps` / `axon dependency-audit`

Audit dependency and optional-extra boundaries for the AXON project. This command verifies that the compiler core remains stdlib-only, generated FastMCP runtime support stays behind the `serve` extra, development-only tooling stays behind the `dev` extra, and source files under `src/axon` do not import provider SDKs or other external packages.

```bash
axon deps .
axon deps . --json
axon dependency-audit .
```

Use this before adding any new import or package dependency. Runtime integrations should be introduced through explicit optional extras instead of `[project].dependencies`.

### `axon hygiene` / `axon repo-hygiene`

Audit repository hygiene and `.gitignore` safety rules. This command verifies that generated FastMCP servers, trace logs, AXON caches, Python caches, virtual environments, and local secrets are ignored while source, examples, docs, tests, snapshots, CI workflows, and project configuration remain trackable.

```bash
axon hygiene .
axon hygiene . --json
axon hygiene . --write-gitignore
axon hygiene . --write-gitignore --force
axon repo-hygiene .
```

Use this before committing generated files or changing `.gitignore`. It does not inspect git history, execute agents, call providers, or resolve secrets.

### `axon precommit`

Print, install, check, or run the AXON Git pre-commit hook template.

```bash
axon precommit print
axon precommit install
axon precommit install --force
axon precommit check
axon precommit check --json
axon precommit run
axon precommit run --json
axon precommit run --full
```

The installed hook delegates to `python -m axon precommit run --path <project-root>`. The default run covers compile checks, dependency audit, project syntax/validation checks, AST snapshot checks for examples, formatter idempotency, and pytest. It does not call providers or require FastMCP. See `docs/PRECOMMIT.md`.

### `axon config`

Inspect provider configuration safely.

```bash
axon config
axon config --config axon.toml
axon config --config axon.toml --json
axon config --config axon.toml --resolve-env
```

Secrets are redacted in human and JSON output. `.ax` files should never contain API keys.

Example `axon.toml`:

```toml
[providers.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[providers.ollama]
base_url = "http://localhost:11434"

[defaults]
model = "@anthropic/claude-4"
```

### `axon syntax`

Run syntax parsing only and display rich diagnostics.

```bash
axon syntax examples/hello.ax
axon syntax bad.ax
axon syntax bad.ax --json
```

Example diagnostic:

```text
error: Unexpected token at line 1: agnt Bot { } (bad.ax:1:1)
 1 | agnt Bot { }
   | ^
hint: Did you mean `agent`?
```

### `axon validate`

Run static semantic validation.

```bash
axon validate examples/hello.ax
axon validate examples/hello.ax --json
axon validate examples/hello.ax --warnings-as-errors
```

Current validation checks include:

- duplicate top-level declaration names
- missing `///` tool docstrings
- unknown agent tool references
- duplicate tools or methods inside an agent
- agents without methods
- prompt `@budget(tokens: N)` validity
- prompt template variables not declared as prompt parameters
- duplicate RAG methods
- duplicate flow stages
- simple undeclared flow stage references as warnings
- type checking (primitive types, generics, Option, Result, Stream)

### `axon type-check`

Run type checking on an AXON file.

```bash
axon type-check examples/hello.ax
axon type-check examples/hello.ax --json
```

Type checking validates:
- Well-formed type expressions (primitives, generics, Option, Result, Stream)
- Unknown type names (warnings for types not defined in type aliases)
- Type parameter syntax

### `axon token-budget`

Check token budgets for prompt templates in an AXON file.

```bash
axon token-budget examples/hello.ax
axon token-budget examples/hello.ax --json
```

Token budget checking validates:
- Estimated token counts for prompt templates
- @budget annotations against estimated costs
- Warnings when templates exceed budgets

### `axon lsp`

Run the Language Server Protocol server for AXON IDE integration.

```bash
axon lsp --stdio
```

The LSP server provides:
- Syntax highlighting
- Diagnostics (errors, warnings)
- Autocomplete/suggestions
- Document symbols
- Go to definition

This is used by IDEs (VS Code, etc.) to provide rich AXON editing support.

### `axon docs`

Generate Markdown documentation from an AXON file.

```bash
axon docs examples/hello.ax docs/hello.md
```

Documentation generation extracts:
- Tool signatures and docstrings
- Agent models and methods
- Prompt templates and parameters
- Type aliases and record fields
- RAG and flow declarations

### `axon ast`

Print, write, or check stable JSON AST snapshots.

```bash
axon ast examples/hello.ax
axon ast examples/hello.ax --no-lines
axon ast examples/hello.ax --write tests/snapshots/hello.ast.json
axon ast examples/hello.ax --check tests/snapshots/hello.ast.json
```

Use AST snapshots to lock parser behavior and catch accidental changes.

### `axon format`

Print, check, or rewrite canonical AXON source formatting. The formatter parses source into the current AST and re-emits stable formatting; it does not execute agents, call providers, or translate method bodies.

```bash
axon format examples/hello.ax
axon format examples/hello.ax --check
axon format examples/hello.ax --write
```

Use `--check` in CI before adopting `--write` locally. Comments that are not part of the parsed AST are not preserved by this Phase 1 formatter. The test suite also stores golden formatted-source snapshots under `tests/snapshots/formatted/` so formatter changes are explicit and reviewable.

### `axon check-project` / `axon doctor`

Run the project-level quality gate for an AXON project. This checks config loading, syntax, semantic validation, AST snapshots when present, and generated-server smoke tests.

```bash
axon check-project .
axon check-project . --json
axon check-project . --no-smoke
axon check-project . --warnings-as-errors
axon check-project . --snapshot-dir tests/snapshots/examples
axon check-project . --require-snapshots
axon doctor .
```

`axon doctor` is an alias for `axon check-project`.

### `axon build`

Generate a FastMCP Python server from an AXON source file.

```bash
axon build examples/hello.ax
axon build examples/hello.ax -o hello_server.py
axon build examples/hello.ax --stdout
axon build examples/hello.ax --name CustomServer
axon build examples/hello.ax --config axon.toml --stdout
```

Generated tool bodies are stubs. AXON tool body text is preserved as comments, and each generated Python tool raises `NotImplementedError` until manually implemented or handled by a later runtime phase.

### `axon serve`

Build and optionally run the generated FastMCP server.

```bash
axon serve examples/hello.ax --dry-run
axon serve examples/hello.ax -o hello_server.py --dry-run
axon serve examples/hello.ax --config axon.toml --dry-run
axon serve examples/hello.ax --python python
```

`serve` is intentionally thin in Phase 1. It builds a generated Python file, then runs it unless `--dry-run` is provided.

### `axon govern`

Compile an AXON source file into an [AgentOps Mesh](https://github.com/annapurna-agentics/agentops-mesh) governance submission JSON. This is the integration bridge between AXON and AgentOps Mesh — it statically infers domain, autonomy level, risk factors, and governance scores from AXON declarations.

```bash
# Generate governance JSON to stdout
axon govern examples/research_pipeline.ax

# Save to file
axon govern examples/research_pipeline.ax -o governance.json

# Submit directly to a running AgentOps Mesh instance
axon govern examples/research_pipeline.ax --mesh-url http://localhost:8000

# With ownership and environment metadata
axon govern examples/research_pipeline.ax --business-owner "Alice" --technical-owner "Bob" --target-environment pilot
```

See [docs/AGENTOPS_MESH_INTEGRATION.md](docs/AGENTOPS_MESH_INTEGRATION.md) for the full integration guide.

### `axon ci-template`

Generate a CI/CD workflow file for an AXON project. Supports GitHub Actions and GitLab CI.

```bash
# Generate GitHub Actions workflow to stdout
axon ci-template --platform github-actions

# Write to .github/workflows/axon.yml
axon ci-template --platform github-actions -o .github/workflows/axon.yml

# Include governance submission step to AgentOps Mesh
axon ci-template --platform github-actions --mesh-url http://localhost:8000 -o .github/workflows/axon.yml

# Generate GitLab CI configuration
axon ci-template --platform gitlab-ci -o .gitlab-ci.yml
```

The generated workflow includes: dependency audit, hygiene check, validation, type-checking, formatting check, smoke test, and pytest. When `--mesh-url` is provided, a governance submission step is appended.

### `axon explain`

Explain validation errors in plain English with fix suggestions. A developer experience feature — no other DSL does this.

```bash
# Explain validation errors for a file
axon explain examples/hello.ax

# Example output:
# === AXON Explanation for my_agent.ax ===
#
# ❌ 1 error(s):
#
#   Error 1: tool 'WebSearch' must include at least one /// docstring line
#     Location: line 39
#     Code: tool-docstring
#     Fix: Add a /// docstring line inside the tool body, e.g.: /// "Does something useful."
```

### `axon smoke`

Smoke-test generated server code without requiring FastMCP to be installed.

```bash
axon smoke examples/hello.ax
axon smoke examples/hello.ax --json
axon smoke examples/hello.ax --name CustomServer
```

The smoke command:

```text
parse .ax
-> validate declarations
-> generate FastMCP server in memory
-> compile generated Python
-> load it with a fake FastMCP module
-> verify registered tools and metadata
-> verify mcp.run() is not called during import
```

### `axon trace-preview`

Statically extract AEL-looking trace events from parsed agent method bodies.

```bash
axon trace-preview examples/trace_preview.ax
axon trace-preview examples/trace_preview.ax --json
axon trace-preview examples/trace_preview.ax --jsonl
```

This command scans source text for statements such as:

```axon
think "Need to search"
let results = act WebSearch(query: topic)?
observe results: []
store memory.working["results"] = results
```

It does not execute tools, call providers, or mutate memory.

### `axon trace-read` / `axon trace-log`

Read, validate, summarize, and filter AEL JSONL trace logs.

```bash
axon trace-read examples/sample_trace.jsonl
axon trace-read examples/sample_trace.jsonl --events
axon trace-read examples/sample_trace.jsonl --type act
axon trace-read examples/sample_trace.jsonl --agent ResearchAgent
axon trace-read examples/sample_trace.jsonl --json
axon trace-read examples/sample_trace.jsonl --jsonl

axon trace-log examples/sample_trace.jsonl
```

Supported event types:

```text
think
act
observe
store
```

## Source declarations

### Type aliases

```axon
type IssueId = Int
type Priority = "low" | "medium" | "high"

type Issue = {
    id: Int,
    title: Str,
    labels: List<Str>
}

type PagedList<T> = {
    items: List<T>,
    total: Int,
    page: Int
}
```

### Prompt declarations

```axon
prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {
    """
    Summarize this text:
    {text}
    """
}
```

Prompt declarations are parsed and preserved for later compiler phases. The current FastMCP generator intentionally ignores prompts because Phase 1 emits callable tool stubs only.

### Tool declarations

```axon
tool WebSearch(query: Str, max_results: Int = 5) -> Result<List<Any>, ToolError> {
    /// Searches the web for current information.
    http.get("https://example.search?q={query}&n={max_results}")
}
```

Tool docstrings are required by validation because they become tool descriptions for generated MCP metadata.

Built-in tool clients available in tool bodies: `fs` (read, write, list, exists), `http` (get, post, put, delete), `db` (query, execute, transaction, tables, schema), `github` (list_issues, get_issue, create_issue, add_label, assign_issue, close_issue, create_comment, list_prs, get_pr, merge_pr, create_review), `slack` (send_message, update_message, delete_message, list_channels, get_channel_history, create_channel, archive_channel, set_topic, invite_user, search_messages), `sandbox` (run, eval — restricted Python execution with blocked dangerous modules and timeout), and `env` (environment variable access). All paths are sandboxed to the source file's directory. GitHub calls use `GITHUB_TOKEN` and Slack calls use `SLACK_BOT_TOKEN` from the environment.

### Agent declarations

```axon
agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch]
    memory: Memory<ShortTerm>(capacity: 500)

    fn run(topic: Str) -> Result<Str, AgentError> {
        let results = act WebSearch(query: topic)?
        store memory.working["results"] = results
        Ok("done")
    }
}
```

Agent method bodies are currently preserved as raw AXON text.

### RAG declarations

```axon
rag ProductDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::postgres(env.PGVECTOR_URL)

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}
```

RAG declarations are parsed only. Indexing, embeddings, vector search, and retrieval runtime are not implemented yet.

### Flow declarations

```axon
flow AnswerFlow(question: Str) -> Str {
    stage Retrieve(query: Str) -> List<Chunk>
    stage Answer(chunks: List<Chunk>, question: Str) -> Str

    Retrieve -> Answer
}
```

Flow declarations are parsed only. DAG execution, channels, fan-out/fan-in, and conditional routing are not implemented yet.

## Test and quality workflow

Run the full suite:

```bash
pytest
```

Run structural checks:

```bash
python -m compileall -q src tests
axon syntax examples/hello.ax
axon validate examples/hello.ax
axon smoke examples/hello.ax
axon ast examples/hello.ax --check tests/snapshots/hello.ast.json
axon --help
axon build --help
```

The test suite also locks CLI help consistency so README/CLI reference command lists stay aligned with the argparse implementation.

Generate release notes for a handoff bundle:

```bash
axon release-notes --change "completed Task #26" --tests "pytest passed" --output RELEASE_NOTES.md
```

Generated server compile check:

```bash
axon build examples/hello.ax -o /tmp/hello_server.py
python -m py_compile /tmp/hello_server.py
```


## Continuous integration

The repository includes a conservative GitHub Actions template at `.github/workflows/ci.yml`.
It runs compile checks, dependency-boundary audit, project quality checks, formatter checks,
generated-server smoke tests, and the pytest suite on Python 3.11 and 3.12. See
`docs/CI.md` for the exact command sequence and runtime-boundary guarantees.

For local commits, install the conservative Git pre-commit hook with:

```bash
axon precommit install
```

See `docs/PRECOMMIT.md` for the hook template and local check sequence.

See `docs/RUNTIME_BOUNDARY.md` for the current non-executing compiler/runtime boundary before starting any runtime task.

## Current limitations

Not yet implemented:

- LSP / IDE integration (basic diagnostics available; full autocomplete pending)
- Multi-agent distributed mesh networking (message bus primitives exist, production hardening pending)

## Development direction

The safe next milestones are intentionally small:

1. Keep parser and diagnostics stable.
2. Expand validation carefully.
3. Add runtime pieces only after generated-code and trace foundations are stable.
4. Preserve provider-agnostic behavior and secret-safe configuration.
5. Continue using tests, AST snapshots, golden error snapshots, and formatted-source snapshots as quality gates.



## Project quality gate

```bash
axon check-project .
axon doctor .
```


### Project quality gate

Use `axon version`, `axon info`, `axon project-info`, `axon foundation-audit`, `axon handoff`, `axon release-bundle-manifest`, `axon task-template`, `axon runtime-rfc-template`, `axon runtime-plan`, `axon runtime-plan-corpus`, `axon runtime-plan-review`, `axon runtime-plan-review-check`, `axon deps`, `axon hygiene`, and `axon precommit check` in bug reports to identify the AXON build and environment. Use `axon check-project` or the `axon doctor` alias to run syntax checks, semantic validation, AST snapshot checks, config loading, and generated-server smoke tests for an AXON project. Useful options include `--json`, `--no-smoke`, `--warnings-as-errors`, `--snapshot-dir`, and `--require-snapshots`.

## Runtime plan review checklist

Use `axon runtime-plan-review` before accepting changes that touch runtime-plan output, runtime-plan snapshots, runtime-plan corpus checks, or runtime-boundary documentation.

```bash
axon runtime-plan-review
axon runtime-plan-review --change "runtime-plan schema update"
axon runtime-plan-review --json
axon runtime-plan-review --output RUNTIME_PLAN_REVIEW.md
axon runtime-plan-review-check .
axon runtime-plan-review-check . --json
```

The checklist is documented in `docs/RUNTIME_PLAN_REVIEW.md`. The consistency check is documented in `docs/RUNTIME_PLAN_REVIEW_CONSISTENCY.md`. Together they reinforce that `declaration_inspection` is the only enabled runtime capability; method execution, provider calls, tool dispatch, memory mutation, RAG indexing/retrieval, flow execution, trace replay, secret resolution, and FastMCP runtime imports remain disabled unless a future accepted Runtime RFC changes the boundary.

### Runtime governance quality gate

Use the runtime governance gate before any change that touches runtime-plan output, runtime-plan snapshots, runtime boundary documentation, runtime RFCs, or governance docs:

```bash
axon runtime-governance .
axon runtime-governance . --json
axon runtime-governance . --skip-corpus
axon runtime-governance-gate .
```

This combines:

```bash
axon runtime-plan-review
axon runtime-plan-review-check .
axon runtime-plan-corpus .
axon deps .
axon hygiene .
```

The command is inspection-only. It does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

### Runtime governance evidence

```bash
axon runtime-governance-evidence .
axon runtime-governance-evidence . --json
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
axon release-bundle-manifest . --output release-bundle-manifest.json
```

`axon runtime-governance-evidence` writes a stable, secret-safe evidence artifact for release handoff. It is inspection-only and does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces. See `docs/RUNTIME_GOVERNANCE_EVIDENCE.md` and include `runtime-governance.json` in runtime-related release bundles.

### `axon release-artifacts`

```bash
axon release-artifacts . --output-dir release-artifacts
axon release-artifacts . --output-dir release-artifacts --version 0.1.0 --date 2026-06-01 --change "completed Task #51" --tests "targeted tests passed"
axon release-artifacts . --output-dir release-artifacts --json
```

Writes the standard release handoff artifacts into a chosen output directory: handoff checklist, release notes, runtime governance evidence, runtime-plan corpus evidence, dependency audit, hygiene audit, release bundle manifest, release artifact consistency evidence, and a `release-artifacts.json` self-report. This is the recommended one-command release bundle preparation workflow; see `docs/RELEASE_ARTIFACTS.md` for the full artifact list and review flow. This is inspection-only and does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

---

## Sibling Projects

| Project | Description |
|---------|-------------|
| **[AgentOps Mesh](https://github.com/annapurna-agentics/agentops-mesh)** | Open-source enterprise AgentOps control plane — govern, evaluate, and audit AI agents before production. MIT licensed. |
| **[Agentic AI Systems Lab](https://github.com/annapurna-agentics/agentic-ai-systems-lab)** | Free interactive labs for learning agentic AI architecture — teaching lab, decision tree advisor, architecture review rubric. |
| **[Python Hidden Gems](https://github.com/annapurna-agentics/python-hidden-gems)** | 100 Python mini-projects using lesser-known PyPI packages. MIT licensed. |
| **[Agentic Patterns Cookbook](https://github.com/annapurna-agentics/agentic-patterns-cookbook)** | 17+ reusable agentic solution patterns for enterprise IT problems. MIT licensed. |
| **[Starter Templates](https://github.com/annapurna-agentics/starter-templates)** | Offline-first PWA boilerplates — zero dependencies, mobile-first, installable. MIT licensed. |

---

## License

**MIT License** — see [LICENSE](LICENSE).

AXON is free and open-source. Use it, modify it, distribute it — no restrictions. We believe in building adoption first. If AXON becomes critical infrastructure for your business and you'd like enterprise support, hosting, or custom features, reach out.

Why MIT? We're a new company building developer tools. Royalty models create adoption friction for unknown projects. MIT maximizes contributor growth and community adoption. We'll consider dual-licensing or enterprise features when we have market leverage.
