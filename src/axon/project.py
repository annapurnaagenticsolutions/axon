"""Project skeleton creation for AXON workspaces.

Task #13 keeps project initialization intentionally small and predictable. The
helpers here create a minimal AXON project that can immediately run through the
existing Phase 1 toolchain: ``axon validate``, ``axon build``, and ``axon smoke``.

No network calls are made. No real API keys are written. Provider credentials are
represented only as environment-variable placeholders inside ``axon.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


class ProjectInitError(Exception):
    """Raised for user-facing project initialization failures."""


@dataclass(frozen=True)
class ProjectInitResult:
    """Summary of files touched by ``axon new`` or ``axon init``."""

    path: Path
    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    overwritten: list[Path] = field(default_factory=list)

    @property
    def changed(self) -> list[Path]:
        """Files that were created or overwritten."""
        return [*self.created, *self.overwritten]

    def format(self) -> str:
        """Return a concise human-readable report."""
        lines = [f"AXON project ready: {self.path}"]
        if self.created:
            lines.append("Created:")
            lines.extend(f"  {path}" for path in self.created)
        if self.overwritten:
            lines.append("Overwritten:")
            lines.extend(f"  {path}" for path in self.overwritten)
        if self.skipped:
            lines.append("Skipped existing:")
            lines.extend(f"  {path}" for path in self.skipped)
        if not self.created and not self.overwritten and not self.skipped:
            lines.append("No files changed.")
        return "\n".join(lines)


def create_project(path: str | Path, *, force: bool = False) -> ProjectInitResult:
    """Create a new AXON project directory.

    ``axon new`` is conservative: if the target directory already exists and is
    not empty, it fails unless ``force=True``. This protects accidental overwrites
    when users mistype a path.
    """
    target = Path(path).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise ProjectInitError(f"target exists and is not a directory: {target}")
    if target.exists() and any(target.iterdir()) and not force:
        raise ProjectInitError(f"target directory is not empty: {target}; pass --force to add missing AXON files")
    return init_project(target, force=force)


def init_project(path: str | Path = ".", *, force: bool = False) -> ProjectInitResult:
    """Initialize an AXON project skeleton in an existing or new directory.

    Existing files are preserved by default. Passing ``force=True`` overwrites
    only the known AXON starter files managed by this helper.
    """
    root = Path(path).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ProjectInitError(f"target exists and is not a directory: {root}")
    root.mkdir(parents=True, exist_ok=True)

    project_name = _project_name(root)
    files = _starter_files(project_name)

    created: list[Path] = []
    skipped: list[Path] = []
    overwritten: list[Path] = []

    for relative, content in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        normalized_content = content.rstrip() + "\n"

        if destination.exists() and not force:
            skipped.append(relative)
            continue

        existed = destination.exists()
        destination.write_text(normalized_content, encoding="utf-8")
        if existed:
            overwritten.append(relative)
        else:
            created.append(relative)

    return ProjectInitResult(path=root, created=created, skipped=skipped, overwritten=overwritten)


def create_project_with_template(
    path: str | Path, template: str, *, force: bool = False
) -> ProjectInitResult:
    """Create a new AXON project with a pre-built agent template."""
    target = Path(path).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise ProjectInitError(f"target exists and is not a directory: {target}")
    if target.exists() and any(target.iterdir()) and not force:
        raise ProjectInitError(f"target directory is not empty: {target}; pass --force to add missing AXON files")

    root = target
    root.mkdir(parents=True, exist_ok=True)
    project_name = _project_name(root)

    files = _starter_files(project_name)
    template_files = _template_files(project_name, template)
    files.update(template_files)

    created: list[Path] = []
    skipped: list[Path] = []
    overwritten: list[Path] = []

    for relative, content in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        normalized_content = content.rstrip() + "\n"

        if destination.exists() and not force:
            skipped.append(relative)
            continue

        existed = destination.exists()
        destination.write_text(normalized_content, encoding="utf-8")
        if existed:
            overwritten.append(relative)
        else:
            created.append(relative)

    return ProjectInitResult(path=root, created=created, skipped=skipped, overwritten=overwritten)


_TEMPLATES: dict[str, dict[str, str]] = {
    "customer-support": {
        "agent.ax": '''import { Chunk } from "axon:types"

type SupportResponse = {
    answer: Str,
    confidence: Float,
    escalated: Bool
}

tool AnswerFAQ(question: Str) -> Str {
    /// Answers a customer question from FAQ knowledge.
    "Based on our FAQ: {question}"
}

tool CreateTicket(title: Str, priority: "low" | "medium" | "high" = "medium") -> Str {
    /// Creates a support ticket when escalation is needed.
    "Ticket created: {title} [{priority}]"
}

agent CustomerSupportAgent {
    model: @mock/gpt
    tools: [AnswerFAQ, CreateTicket]
    memory: Memory<Semantic>

    fn handle(question: Str) -> Str {
        let answer = act AnswerFAQ(question: question)?
        store memory.working["last_question"] = question
        answer
    }
}

test "faq answer" {
    assert CustomerSupportAgent.run("How do I reset my password?") == "Based on our FAQ: How do I reset my password?"
}
''',
        "README.md": '''# {name} — Customer Support Agent

A customer support agent built with AXON, featuring:
- FAQ answering tool
- Ticket creation for escalations
- Semantic memory for conversation context

## Try it

```bash
axon validate agent.ax
axon run agent.ax --mock
axon test agent.ax
axon govern agent.ax --mesh-url http://localhost:8000
```
''',
    },
    "code-review": {
        "agent.ax": '''tool AnalyzeCode(code: Str) -> Str {
    /// Analyzes code for issues and returns a review summary.
    "Review: {code[:50]}... — looks good"
}

tool SuggestFix(issue: Str) -> Str {
    /// Suggests a fix for a code issue.
    "Fix: {issue}"
}

agent CodeReviewer {
    model: @mock/gpt
    tools: [AnalyzeCode, SuggestFix]

    fn review(code: Str) -> Str {
        let analysis = act AnalyzeCode(code: code)?
        analysis
    }
}

test "code review" {
    assert CodeReviewer.run("def hello(): pass") == "Review: def hello(): pass... — looks good"
}
''',
        "README.md": '''# {name} — Code Review Agent

Automated code review agent that analyzes snippets and suggests fixes.

## Try it

```bash
axon validate agent.ax
axon run agent.ax --mock
axon test agent.ax
```
''',
    },
    "data-analysis": {
        "agent.ax": '''tool RunQuery(query: Str) -> Str {
    /// Executes a data query and returns results.
    "Result for: {query}"
}

tool Visualize(data: Str, chart_type: "bar" | "line" | "pie" = "bar") -> Str {
    /// Generates a visualization from data.
    "Chart({chart_type}): {data}"
}

agent DataAnalyst {
    model: @mock/gpt
    tools: [RunQuery, Visualize]

    fn analyze(query: Str) -> Str {
        let result = act RunQuery(query: query)?
        act Visualize(data: result, chart_type: "bar")?
    }
}

test "query execution" {
    assert DataAnalyst.run("SELECT * FROM users") == "Chart(bar): Result for: SELECT * FROM users"
}
''',
        "README.md": '''# {name} — Data Analysis Agent

Query execution and visualization agent.

## Try it

```bash
axon validate agent.ax
axon run agent.ax --mock
axon test agent.ax
```
''',
    },
    "research": {
        "agent.ax": '''tool WebSearch(query: Str) -> Str {
    /// Searches the web for information.
    "Search results for: {query}"
}

tool Summarize(text: Str) -> Str {
    /// Summarizes text content.
    "Summary: {text[:40]}..."
}

agent ResearchAgent {
    model: @mock/gpt
    tools: [WebSearch, Summarize]
    memory: Memory<ShortTerm>

    fn research(topic: Str) -> Str {
        let results = act WebSearch(query: topic)?
        store memory.working["topic"] = topic
        act Summarize(text: results)?
    }
}

test "research workflow" {
    assert ResearchAgent.run("AI governance") == "Summary: Search results for: AI governance..."
}
''',
        "README.md": '''# {name} — Research Agent

Multi-step research agent with web search and summarization.

## Try it

```bash
axon validate agent.ax
axon run agent.ax --mock
axon test agent.ax
```
''',
    },
    "general": {
        "agent.ax": '''tool Process(input: Str) -> Str {
    /// Processes input and returns a result.
    "Processed: {input}"
}

agent Agent {
    model: @mock/gpt
    tools: [Process]

    fn run(input: Str) -> Str {
        act Process(input: input)?
    }
}

test "process input" {
    assert Agent.run("hello") == "Processed: hello"
}
''',
        "README.md": '''# {name} — General Purpose Agent

A minimal AXON agent template.

## Try it

```bash
axon validate agent.ax
axon run agent.ax --mock
axon test agent.ax
```
''',
    },
}


def _template_files(project_name: str, template: str) -> dict[Path, str]:
    """Get template-specific files."""
    template_data = _TEMPLATES.get(template, _TEMPLATES["general"])
    files: dict[Path, str] = {}
    for filename, content in template_data.items():
        content = content.replace("{name}", project_name)
        if filename == "agent.ax":
            files[Path("examples/agent.ax")] = content
        else:
            files[Path(filename)] = content
    return files


def _project_name(root: Path) -> str:
    raw = root.name or "axon-project"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-_")
    return slug or "axon-project"


def _starter_files(project_name: str) -> dict[Path, str]:
    return {
        Path("axon.toml"): f'''# AXON project configuration for {project_name}
# API keys never belong in .ax files. Keep secrets in environment variables.

[defaults]
model = "@ollama/llama3"
embed = "@ollama/nomic-embed-text"

[providers.ollama]
base_url = "http://localhost:11434"

# Uncomment when you are ready to use cloud providers.
# [providers.anthropic]
# api_key = "${{ANTHROPIC_API_KEY}}"
#
# [providers.openai]
# api_key = "${{OPENAI_API_KEY}}"
''',
        Path("examples/hello.ax"): '''tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    /// Use as the first AXON smoke-test tool.
    "Hello, {name}!"
}

agent HelloAgent {
    model: env.DEFAULT_MODEL
    tools: [Greet]

    fn run(name: Str) -> Str {
        act Greet(name: name)?
    }
}
''',
        Path("README.md"): f'''# {project_name}

AXON project skeleton generated by `axon new` / `axon init`.

## Try it

```bash
axon validate examples/hello.ax
axon smoke examples/hello.ax
axon build examples/hello.ax --config axon.toml --stdout
```

## Files

- `axon.toml` — provider defaults and environment-variable placeholders.
- `examples/hello.ax` — minimal AXON tool + agent example.

API keys should stay in your shell environment or secret manager, never inside `.ax` source files.
''',
        Path(".gitignore"): '# Python caches and bytecode\n__pycache__/\n*.py[cod]\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n.coverage\nhtmlcov/\n\n# Python build artifacts\nbuild/\ndist/\n*.egg-info/\n\n# Virtual environments\n.venv/\nvenv/\nenv/\n\n# AXON generated outputs\n*_server.py\ntraces/*.jsonl\ntraces/**/*.jsonl\n.axon/cache/\n.axon/tmp/\n\n# Local secrets\n.env\n.env.*\n!.env.example\n*.pem\n*.key\n\n# OS / editor noise\n.DS_Store\nThumbs.db\n',
        Path("traces/.gitkeep"): "",
    }
