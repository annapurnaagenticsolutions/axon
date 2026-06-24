# AXON CLI Reference

This document summarizes the CLI surface available in the Phase 1 prototype.

## Metadata commands

```bash
axon version [--json]
axon info [--json] [--path PATH] [--config axon.toml]
axon project-info [path] [--json]
axon foundation-audit [path] [--json]
axon handoff [path] [--full] [--output PATH] [--json]
axon release-notes [--version VERSION] [--date YYYY-MM-DD] [--path PATH] [--change TEXT] [--tests TEXT] [--output PATH] [--json]
axon release-bundle-manifest [path] [--output FILE] [--format json|markdown] [--json]
axon release-artifacts [path] [--output-dir DIR] [--version VERSION] [--date YYYY-MM-DD] [--change TEXT] [--tests TEXT] [--skip-corpus] [--json]
axon release-artifacts-check [path] [--json]
axon release-artifact-consistency [path] [--json]
axon task-template [--number N] [--title TEXT] [--module PATH] [--output PATH] [--json]
axon runtime-rfc-template [--number N] [--title TEXT] [--owner NAME] [--status STATUS] [--output PATH] [--json]
axon runtime-plan <source.ax> [--json] [--write PATH] [--check PATH] [--root PATH]
axon runtime-plan-corpus [path] [--examples-dir DIR] [--snapshot-dir DIR] [--allow-missing-snapshots] [--json]
axon runtime-plan-review [--change TEXT] [--output PATH] [--json]
axon runtime-plan-review-check [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--json]
axon runtime-governance [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--json]
axon runtime-governance-gate [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--json]
axon runtime-governance-evidence [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--output FILE] [--format json|markdown] [--json]
axon changelog [--version VERSION] [--date YYYY-MM-DD] [--path PATH] [--change TEXT] [--tests TEXT] [--output PATH] [--json]
axon deps [path] [--json]
axon dependency-audit [path] [--json]
axon hygiene [path] [--json] [--write-gitignore] [--force]
axon repo-hygiene [path] [--json] [--write-gitignore] [--force]
axon precommit [print|install|check|run] [--path PATH] [--hook-path PATH] [--force] [--full] [--json]
axon health [--json]
axon run <source.ax> [--arg key=value] [--trace trace.jsonl] [--memory memory.json] [--checkpoint] [--mock] [--no-mock] [--live] [--provider openai|anthropic|mock] [--json]
axon agent spawn <source.ax> --name NAME [--arg key=value] [--trace trace.jsonl] [--memory memory.json] [--checkpoint] [--stream] [--mock] [--no-mock] [--live] [--provider openai|anthropic|mock]
axon agent pause NAME
axon agent resume NAME
axon agent terminate NAME [--reason TEXT]
axon agent status NAME [--json]
axon agent list [--json]
axon supervisor start --name NAME --strategy one_for_one|one_for_all|rest_for_one [--child source::name] [--max-restarts N] [--max-seconds S] [--mock] [--no-mock] [--live] [--provider openai|anthropic|mock]
axon supervisor stop NAME [--reason TEXT]
axon supervisor status NAME [--json]
axon watch start <source.ax> --name NAME [--arg key=value] [--poll-interval MS] [--mock] [--no-mock] [--live] [--provider openai|anthropic|mock]
axon watch stop NAME
axon agent checkpoint NAME [--output path.json]
axon agent restore NAME --snapshot path.json [--mock] [--no-mock] [--live] [--provider openai|anthropic|mock]
axon metrics show [--json]
axon metrics export --output path [--format json|text]
axon metrics reset
axon serve-api [--host HOST] [--port PORT] [--api-key KEY]
axon secret list [--file path]
axon secret get KEY [--reveal] [--file path]
axon secret set KEY VALUE [--file path]
axon secret delete KEY [--file path]
axon secret audit [--key KEY]
```

## Database configuration

Set the `AXON_DB_URL` environment variable to use a persistent backend:

```bash
# SQLite (default, built-in)
export AXON_DB_URL="sqlite:///path/to/axon.db"

# PostgreSQL (requires `pip install axon-dsl[db]`)
export AXON_DB_URL="postgresql://user:pass@localhost/axon"
```


## Project information

```bash
axon project-info [path] [--json]
```

Summarizes safe AXON project/workspace metadata: source files, examples, docs, snapshots, golden errors, trace logs, config presence, provider names, CI workflows, Git hooks, and lightweight hygiene/dependency audit status. The command is inspection-only and does not resolve secrets, execute agents, call providers, or require FastMCP.



## Foundation audit

```bash
axon foundation-audit [path] [--json]
```

Audits the Phase 1 compiler/tooling foundation: parser and AST modules, validation diagnostics, codegen smoke harness, config safety, formatter and AST snapshots, trace tooling, runtime-plan boundary, runtime governance, release handoff, docs, examples, and developer workflow. The command is inspection-only and does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

Options:

- `--json` — print the foundation audit report as JSON.

## Release handoff checklist

```bash
axon handoff [path] [--full] [--output PATH] [--json]
```

Builds a safe release handoff checklist that connects `axon version`, `axon info`, `axon project-info`, `axon deps`, `axon hygiene`, `axon check-project`, `axon precommit run`, `axon runtime-governance-evidence`, `axon release-bundle-manifest`, and `axon release-notes` into one repeatable workflow. The command is inspection-only: it prints commands to run and documents to review, but it does not execute agents, call providers, or resolve secrets. Use `--full` for release bundles that should include smoke-enabled quality gates.

## Contributor task-ticket template

```bash
axon task-template [--number N] [--title TEXT] [--module PATH] [--output PATH] [--json]
```

Generates a self-contained implementation ticket template for human or LLM contributors. Use it to standardize background, scope, interfaces, syntax references, examples, constraints, deliverables, and validation commands. The command is deterministic and does not execute agents, call providers, or resolve secrets.

## Runtime design RFC template

```bash
axon runtime-rfc-template [--number N] [--title TEXT] [--owner NAME] [--status STATUS] [--output PATH] [--json]
```

Generates a strict runtime design RFC template. Use it before implementing any behavior that executes AXON method bodies, calls providers, dispatches tools, mutates memory, indexes RAG data, executes flows, or replays traces. The template requires sections for current boundary checks, proposed runtime scope, non-goals, provider impact, tool dispatch impact, memory/RAG/flow impact, trace guarantees, security, testing, rollback, acceptance criteria, and open questions. See `docs/RUNTIME_RFC_TEMPLATE.md` and `docs/RUNTIME_BOUNDARY.md` before starting runtime implementation.

Options:

- `--number` — optional runtime RFC number used in the heading.
- `--title` — runtime RFC title used in the heading.
- `--owner` — runtime RFC owner displayed in the template.
- `--status` — runtime RFC status displayed in the template.
- `--output` — write the template to a file instead of stdout.
- `--json` — print or write JSON instead of Markdown.

## Runtime plan

```bash
axon runtime-plan <source.ax> [--json] [--write PATH] [--check PATH] [--root PATH]
```

Builds a validated, non-executing runtime plan for one AXON source file. The plan summarizes imports, type aliases, prompts, tools, agents, RAG declarations, flows, and disabled runtime capabilities. It does not execute method bodies, call providers, dispatch tools, mutate memory, index or retrieve RAG data, execute flows, replay traces, resolve secrets, or import FastMCP.

Options:

- `--json` — print the runtime plan as JSON.
- `--write PATH` — write a stable runtime-plan JSON snapshot to a file.
- `--check PATH` — compare the current runtime-plan JSON snapshot against a file.
- `--root PATH` — project root used to normalize `source_path` in snapshots.


## Runtime plan corpus

```bash
axon runtime-plan-corpus [path] [--examples-dir DIR] [--snapshot-dir DIR] [--allow-missing-snapshots] [--json]
```

Checks runtime-plan snapshots and disabled runtime capabilities across an AXON example corpus. The command parses and validates every `.ax` example, builds non-executing runtime plans, compares checked-in runtime-plan snapshots, rejects orphan snapshots, and confirms provider calls, tool dispatch, method execution, memory mutation, RAG indexing/retrieval, flow execution, trace replay, secret resolution, and FastMCP runtime imports remain disabled.

Options:

- `--examples-dir DIR` — directory containing `.ax` examples, relative to the project root unless absolute.
- `--snapshot-dir DIR` — directory containing runtime-plan snapshots, relative to the project root unless absolute.
- `--allow-missing-snapshots` — treat missing runtime-plan snapshots as warnings instead of errors.
- `--json` — print the corpus report as JSON.


## Runtime-plan workflow

The runtime-plan commands are inspection-only. They do not execute AXON method bodies, call providers, dispatch tools, mutate memory, index or retrieve RAG data, execute flows, replay traces, resolve secrets, or import FastMCP. See `docs/RUNTIME_PLAN.md` and `docs/RUNTIME_BOUNDARY.md` for the complete boundary.

Use `axon runtime-plan` for one `.ax` file and `axon runtime-plan-corpus` for the checked-in example corpus. Runtime-plan snapshots are stored under `tests/snapshots/runtime_plan/examples/`.

## Release notes

```bash
axon release-notes [--version VERSION] [--date YYYY-MM-DD] [--path PATH] [--change TEXT] [--tests TEXT] [--output PATH] [--json]
axon release-bundle-manifest [path] [--output FILE] [--format json|markdown] [--json]
axon release-artifacts [path] [--output-dir DIR] [--version VERSION] [--date YYYY-MM-DD] [--change TEXT] [--tests TEXT] [--skip-corpus] [--json]
axon release-artifacts-check [path] [--json]
axon release-artifact-consistency [path] [--json]
axon task-template [--number N] [--title TEXT] [--module PATH] [--output PATH] [--json]
axon runtime-rfc-template [--number N] [--title TEXT] [--owner NAME] [--status STATUS] [--output PATH] [--json]
axon runtime-plan <source.ax> [--json] [--write PATH] [--check PATH] [--root PATH]
axon runtime-plan-corpus [path] [--examples-dir DIR] [--snapshot-dir DIR] [--allow-missing-snapshots] [--json]
axon changelog [--version VERSION] [--date YYYY-MM-DD] [--path PATH] [--change TEXT] [--tests TEXT] [--output PATH] [--json]
```

`axon changelog` is an alias for `axon release-notes`. The command uses explicit change and test-evidence bullets plus safe local metadata; it does not inspect git history or print provider secrets.

## Project commands

```bash
axon new <path> [--force]
axon init [path] [--force]
```

## Dependency audit

```bash
axon deps [path] [--json]
axon dependency-audit [path] [--json]
axon hygiene [path] [--json] [--write-gitignore] [--force]
axon repo-hygiene [path] [--json] [--write-gitignore] [--force]
axon precommit [print|install|check|run] [--path PATH] [--hook-path PATH] [--force] [--full] [--json]
```

`axon dependency-audit` is an alias for `axon deps`. The audit checks that compiler-core dependencies remain empty, FastMCP stays in the `serve` extra, pytest stays in the `dev` extra, and source modules do not import provider SDKs or external packages.

## Repository hygiene

```bash
axon hygiene [path] [--json] [--write-gitignore] [--force]
axon repo-hygiene [path] [--json] [--write-gitignore] [--force]
```

`axon repo-hygiene` is an alias for `axon hygiene`. The audit checks `.gitignore` coverage for generated servers, trace logs, AXON caches, Python caches, virtual environments, local secrets, OS noise, and protected source/documentation paths. `--write-gitignore` writes the conservative AXON template; `--force` allows overwriting an existing `.gitignore`.

## Configuration

```bash
axon config [show] [--config axon.toml] [--json] [--resolve-env]
```

## Source analysis

```bash
axon syntax <source.ax> [--json]
axon validate <source.ax> [--json] [--warnings-as-errors]
axon type-check <source.ax> [--json]
axon token-budget <source.ax> [--json]
axon ast <source.ax> [--no-lines] [--write snapshot.json] [--check snapshot.json]
axon format <source.ax> [--check] [--write]
axon check-project [path] [--json] [--no-smoke] [--warnings-as-errors] [--snapshot-dir DIR] [--require-snapshots]
axon doctor [path] [--json] [--no-smoke] [--warnings-as-errors] [--snapshot-dir DIR] [--require-snapshots]
```

## LSP server

```bash
axon lsp [--stdio]
```

Run the Language Server Protocol server for AXON IDE integration. The server provides syntax highlighting, diagnostics, autocomplete, document symbols, and go-to-definition for AXON files. This is used by IDEs like VS Code to provide rich editing support. The server communicates via stdin/stdout using JSON-RPC.

## Documentation generation

```bash
axon docs <source.ax> <output.md>
```

Generate Markdown documentation from an AXON file. The documentation generator extracts tool signatures and docstrings, agent models and methods, prompt templates and parameters, type aliases and record fields, and RAG/flow declarations.

## Health check

```bash
axon health [--json]
```

Check AXON runtime health status. Reports on parser health, type checker health, provider availability (mock, openai, anthropic), and API key presence. Use `--json` for machine-readable output.

## Code generation and serving

```bash
axon build <source.ax> [-o server.py|--output server.py] [--stdout] [--name NAME] [--config axon.toml]
axon serve <source.ax> [-o server.py|--output server.py] [--name NAME] [--config axon.toml] [--dry-run] [--python PYTHON]
axon smoke <source.ax> [--name NAME] [--json]
```

## Compiling to IR

```bash
axon compile <source.ax> [--ir] [--output path]
```

Compile an AXON source file to Intermediate Representation (IR) — a portable JSON artifact that any runtime (Python, Rust, JS/WASM, Go) can execute. Use `--ir` to print the JSON to stdout, or `--output` to write to a file. IR separates the *what* (agent definitions, workflows, tools) from the *how* (runtime implementation).

## Executing agent runtime

```bash
axon run <source.ax | source.axonir> [--arg key=value] [--trace trace.jsonl] [--memory memory.json] [--checkpoint] [--mock] [--no-mock] [--flow FLOW_NAME] [--agent AGENT_NAME] [--replay trace.jsonl] [--stream] [--sandbox-timeout MS] [--sandbox-max-depth N] [--sandbox-denied TOOL] [--metrics] [--via-ir] [--json]
```

Execute an AXON agent method body or flow with mock tool dispatch and expression evaluation. The runtime loads the agent's `run()` method or the specified flow, evaluates its body expressions, dispatches `act` calls to tools defined in the same source file, and optionally emits AEL trace events. Use `--memory` to load pre-existing agent memory from a JSON file, and `--checkpoint` to persist memory state after execution.

**IR-based execution:** `axon run file.axonir` executes a compiled AXON Intermediate Representation (IR) file directly. The runtime loads the IR JSON, converts it back to runtime-compatible declarations, and executes. This proves the IR is the real execution contract — the Python runtime is just one of many possible consumers.

**Via-IR mode:** `axon run file.ax --via-ir` compiles the `.ax` source to IR internally, then executes from IR. This validates that the compilation pipeline produces functionally identical output to direct parsing.

**Flow execution:** `--flow <FlowName>` executes a named `flow` declaration instead of an agent's `run()` method. Stages in the flow are resolved to matching tools or agents, and outputs flow between stages according to arrow syntax.

**Trace replay:** `--replay <trace.jsonl>` replays a previously recorded trace. Tool dispatches, model calls, and RAG retrievals return the exact recorded results without executing live tools or calling providers. Useful for deterministic regression testing and debugging.

**Named agent execution:** `--agent <AgentName>` executes a specific agent's `run()` method by name. Use when the source file defines multiple agents and you want to run a specific one instead of the first agent.

**Streaming mode:** `--stream` executes the agent via the async runtime and streams response chunks as they arrive from the provider. Useful for real-time UIs and long-running generations.

**Sandbox controls:** `--sandbox-timeout` sets the maximum time (in milliseconds) a single tool dispatch may run before being forcibly terminated (default: 5000). `--sandbox-max-depth` limits expression evaluation nesting depth (default: 100). `--sandbox-denied` blocks specific tool names from executing (repeatable).

**Metrics:** `--metrics` prints runtime observability data after execution, including provider call counts and latencies, tool dispatch counts and latencies, and histogram statistics.

**Mock mode (default):** `--mock` uses the deterministic mock provider regardless of the agent's model declaration. This is safe for testing without API keys.

**Real provider mode:** `--no-mock` resolves the agent's `model: @provider/model` reference to a real provider plugin and makes actual LLM API calls. Requires the provider SDK (e.g., `openai`) and a valid API key in the environment.

## Traces

```bash
axon trace-preview <source.ax> [--json] [--jsonl]
axon trace-read <trace.jsonl> [--type think|act|observe|store] [--agent AGENT] [--events] [--json] [--jsonl]
axon trace-log <trace.jsonl> [--type think|act|observe|store] [--agent AGENT] [--events] [--json] [--jsonl]
```
## Help consistency

The CLI reference is regression-tested against the argparse command surface.
When a command or option is added, update both the parser and this document in the same change.


## `axon runtime-plan-review`

```bash
axon runtime-plan-review [--change TEXT] [--output PATH] [--json]
```

Print or write a reviewer checklist for runtime-plan and runtime-boundary changes. Use this before accepting changes to runtime-plan output, runtime-plan snapshots, runtime-plan corpus checks, or runtime-boundary documentation.

Options:

- `--change TEXT` — short description of the change under review.
- `--output PATH` — write the checklist to a file instead of stdout.
- `--json` — print or write the checklist as JSON.

The checklist is inspection-only. It does not execute agents, call providers, dispatch tools, mutate memory, index RAG data, execute flows, replay traces, resolve secrets, or import FastMCP. See `docs/RUNTIME_PLAN_REVIEW.md`, `docs/RUNTIME_PLAN.md`, and `docs/RUNTIME_BOUNDARY.md`.

## `axon runtime-plan-review-check`

```bash
axon runtime-plan-review-check [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--json]
```

Check that the runtime-plan reviewer checklist stays aligned with runtime-plan docs, Runtime RFC #001, runtime-boundary docs, handoff evidence, CLI docs, and runtime-plan corpus validation. The command is inspection-only and does not execute agents, call providers, dispatch tools, mutate memory, index RAG data, execute flows, replay traces, resolve secrets, or import FastMCP.

Options:

- `--examples-dir DIR` — directory containing `.ax` examples, relative to the project root unless absolute.
- `--snapshot-dir DIR` — directory containing runtime-plan snapshots, relative to the project root unless absolute.
- `--skip-corpus` — skip runtime-plan-corpus execution and check docs/checklist consistency only.
- `--json` — print the consistency report as JSON.

See `docs/RUNTIME_PLAN_REVIEW_CONSISTENCY.md`.

## `axon runtime-governance`

```bash
axon runtime-governance [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--json]
```

Runs the inspection-only runtime governance quality gate. It combines the runtime-plan reviewer checklist, runtime-plan review/docs consistency check, runtime-plan corpus check, dependency audit, and repository hygiene audit into one release evidence report.

This command does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.

## `axon runtime-governance-gate`

```bash
axon runtime-governance-gate [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--json]
```

Alias for `axon runtime-governance`.

## `axon runtime-governance-evidence`

```bash
axon runtime-governance-evidence [path] [--examples-dir DIR] [--snapshot-dir DIR] [--skip-corpus] [--output FILE] [--format json|markdown] [--json]
```

Writes or prints a stable runtime-governance evidence artifact for release handoff. The command is inspection-only and wraps the runtime-governance gate without executing AXON agents or calling providers. See `docs/RUNTIME_GOVERNANCE_EVIDENCE.md` for the standard release-bundle workflow.

Examples:

```bash
axon runtime-governance-evidence .
axon runtime-governance-evidence . --json
axon runtime-governance-evidence . --output runtime-governance.json
axon runtime-governance-evidence . --output RUNTIME_GOVERNANCE_EVIDENCE.md --format markdown
```

## `axon release-artifacts`

```bash
axon release-artifacts [path] [--output-dir DIR] [--version VERSION] [--date YYYY-MM-DD] [--change TEXT] [--tests TEXT] [--skip-corpus] [--json]
```

Writes the standard release handoff artifacts into a chosen output directory. The generated directory includes `HANDOFF_CHECKLIST.md`, `handoff-checklist.json`, `RELEASE_NOTES.md`, `release-notes.json`, `runtime-governance.json`, `RUNTIME_GOVERNANCE_EVIDENCE.md`, `runtime-plan-corpus.json`, `dependency-audit.json`, `hygiene.json`, `release-bundle-manifest.json`, `RELEASE_BUNDLE_MANIFEST.md`, `release-artifact-consistency.json`, and `release-artifacts.json`.

Use `--output-dir` to choose the artifact directory, `--change` and `--tests` to provide release-note evidence, and `--skip-corpus` only for faster local handoff drafts. For the standard release-bundle workflow and file-by-file artifact meaning, see `docs/RELEASE_ARTIFACTS.md`. The command is inspection-only: it does not execute AXON agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.


## `axon release-artifacts-check`

```bash
axon release-artifacts-check [path] [--json]
axon release-artifact-consistency [path] [--json]
```

Checks that the standard release handoff artifact names are consistent across `src/axon/release_artifacts.py`, `src/axon/release_bundle_manifest.py`, `src/axon/handoff.py`, `docs/RELEASE_ARTIFACTS.md`, `docs/RELEASE_BUNDLE.md`, `docs/HANDOFF.md`, `docs/CLI_REFERENCE.md`, and `README.md`.

The canonical artifact list is `HANDOFF_CHECKLIST.md`, `handoff-checklist.json`, `RELEASE_NOTES.md`, `release-notes.json`, `runtime-governance.json`, `RUNTIME_GOVERNANCE_EVIDENCE.md`, `runtime-plan-corpus.json`, `dependency-audit.json`, `hygiene.json`, `release-bundle-manifest.json`, `RELEASE_BUNDLE_MANIFEST.md`, `release-artifact-consistency.json`, and `release-artifacts.json`. Use `--json` for machine-readable release evidence.

## `axon govern`

```bash
axon govern <source.ax> [--mesh-url URL] [--output PATH] [--business-owner NAME] [--technical-owner NAME] [--target-environment sandbox|pilot|production]
```

Compiles an AXON source file into an AgentOps Mesh governance submission JSON. Statically infers domain, autonomy level, risk factors, and governance scores from AXON declarations. When `--mesh-url` is provided, submits the JSON to the `/governance/run` endpoint and prints the governance decision.

## `axon ci-template`

```bash
axon ci-template [--platform github-actions|gitlab-ci] [--output PATH] [--mesh-url URL]
```

Generates a CI/CD workflow file for an AXON project. Supports GitHub Actions and GitLab CI. When `--mesh-url` is provided, appends a governance submission step using `axon govern`.

## `axon explain`

```bash
axon explain <source.ax>
```

Explains validation errors in plain English with fix suggestions. Reports errors and warnings with location, diagnostic code, and actionable fix hints.

## `axon eval`

```bash
axon eval [--iterations N] [--baseline PATH] [--json]
```

Runs built-in performance benchmarks with regression detection.

## `axon add`

```bash
axon add <source> [--branch BRANCH]
```

Installs an AXON package from a git repository.

## `axon remove`

```bash
axon remove <name>
```

Removes an installed AXON package.

## `axon deploy`

```bash
axon deploy <name> [--target docker|fly] [--image-tag TAG] [--file DOCKERFILE]
```

Builds and deploys an AXON app as a Docker image or to cloud.

## `axon debug`

```bash
axon debug <trace.jsonl> [--non-interactive]
```

Interactive AEL trace debugger.

## `axon profile`

```bash
axon profile <trace.jsonl> [--json]
```

Profiles an AEL trace for execution time breakdown.

This check is inspection-only and does not execute agents, call providers, dispatch tools, resolve secrets, import FastMCP, mutate memory, index RAG data, execute flows, or replay traces.
