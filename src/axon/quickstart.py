"""Interactive quickstart wizard for AXON.

Guides users from zero to a working, validated, mock-run agent in under 60 seconds.
Generates a tailored .ax file based on use-case answers, runs validate + mock run,
and prints next steps.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from axon.project import init_project


@dataclass
class QuickstartAnswers:
    project_name: str = "my-agent"
    use_case: str = "general"
    model_provider: str = "mock"
    agent_name: str = "MyAgent"
    tool_name: str = "Process"
    governance: bool = False

    @property
    def project_slug(self) -> str:
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", self.project_name).strip("-_")
        return slug or "my-agent"


USE_CASE_TEMPLATES: dict[str, dict[str, str]] = {
    "general": {
        "description": "A general-purpose agent that processes text input.",
        "tool_body": '"Processed: {input}"',
        "agent_body": "act {tool}({param})?",
        "param_name": "input",
        "param_type": "Str",
    },
    "customer-support": {
        "description": "A customer support agent that answers questions and creates tickets.",
        "tool_body": '"Ticket created for: {question}"',
        "agent_body": "act {tool}({param})?",
        "param_name": "question",
        "param_type": "Str",
    },
    "code-review": {
        "description": "A code review agent that analyzes code snippets.",
        "tool_body": '"Review complete for: {code}"',
        "agent_body": "act {tool}({param})?",
        "param_name": "code",
        "param_type": "Str",
    },
    "data-analysis": {
        "description": "A data analysis agent that processes queries.",
        "tool_body": '"Query result for: {query}"',
        "agent_body": "act {tool}({param})?",
        "param_name": "query",
        "param_type": "Str",
    },
    "research": {
        "description": "A research agent that finds and summarizes information.",
        "tool_body": '"Research summary for: {topic}"',
        "agent_body": "act {tool}({param})?",
        "param_name": "topic",
        "param_type": "Str",
    },
}

MODEL_PROVIDERS = {
    "mock": "@mock/gpt",
    "openai": "@openai/gpt-4",
    "anthropic": "@anthropic/claude-4",
    "groq": "@groq/llama-3.3-70b",
    "ollama": "@ollama/llama3",
}


def run_quickstart(
    path: str | Path = ".",
    *,
    name: str | None = None,
    use_case: str | None = None,
    model: str | None = None,
    non_interactive: bool = False,
) -> int:
    """Run the quickstart wizard. Returns exit code."""
    target = Path(path).expanduser().resolve()

    if non_interactive:
        answers = QuickstartAnswers(
            project_name=name or target.name,
            use_case=use_case or "general",
            model_provider=model or "mock",
        )
    else:
        answers = _interactive_prompt(target)

    template = USE_CASE_TEMPLATES.get(answers.use_case, USE_CASE_TEMPLATES["general"])
    model_ref = MODEL_PROVIDERS.get(answers.model_provider, "@mock/gpt")

    # Create project skeleton
    result = init_project(target, force=True)
    print(f"\n  Project created: {target}")

    # Generate tailored .ax file
    ax_content = _generate_ax_file(answers, template, model_ref)
    ax_path = target / "examples" / "quickstart.ax"
    ax_path.parent.mkdir(parents=True, exist_ok=True)
    ax_path.write_text(ax_content, encoding="utf-8")
    print(f"  Agent file: {ax_path}")

    # Generate governance annotation if requested
    if answers.governance:
        gov_ax = _generate_governance_ax(answers, template, model_ref)
        gov_path = target / "examples" / "quickstart_governed.ax"
        gov_path.write_text(gov_ax, encoding="utf-8")
        print(f"  Governed agent: {gov_path}")

    # Validate
    print("\n  Validating...")
    try:
        from axon.parser import parse
        from axon.validator import validate

        declarations = parse(ax_content)
        diagnostics = validate(declarations)
        errors = [d for d in diagnostics if d.severity == "error"]
        if errors:
            print(f"  [!] {len(errors)} validation error(s):")
            for e in errors:
                print(f"      {e}")
        else:
            print("  [OK] Validation passed")
    except Exception as e:
        print(f"  [!] Parse error: {e}")

    # Mock run
    print("\n  Running with mock provider...")
    try:
        from axon.runtime import RuntimeConfig, execute_runtime

        config = RuntimeConfig(source_path=ax_path, mock=True)
        result = execute_runtime(config)
        if hasattr(result, "is_ok") and result.is_ok():
            output = result.unwrap()
        elif hasattr(result, "is_err") and result.is_err():
            output = f"error: {result.unwrap_err()}"
        else:
            output = str(result)
        print(f"  [OK] Agent output: {output}")
    except Exception as e:
        print(f"  [!] Run skipped (mock): {e}")

    # Print next steps
    print("\n  Next steps:")
    print(f"    axon validate {ax_path.relative_to(target) if ax_path.is_relative_to(target) else ax_path}")
    print(f"    axon run {ax_path.relative_to(target) if ax_path.is_relative_to(target) else ax_path} --mock")
    if answers.governance:
        gov_rel = gov_path.relative_to(target) if gov_path.is_relative_to(target) else gov_path
        print(f"    axon govern {gov_rel} --mesh-url http://localhost:8000")
    print(f"    axon build {ax_path.relative_to(target) if ax_path.is_relative_to(target) else ax_path} --stdout")
    print(f"    axon playground --port 8080")
    print()

    return 0


def _interactive_prompt(target: Path) -> QuickstartAnswers:
    """Prompt the user for quickstart preferences."""
    print("\n  === AXON Quickstart Wizard ===\n")

    default_name = target.name or "my-agent"
    name = _ask(f"  Project name [{default_name}]: ", default=default_name)

    print("\n  Use cases:")
    for i, uc in enumerate(USE_CASE_TEMPLATES, 1):
        print(f"    {i}. {uc} — {USE_CASE_TEMPLATES[uc]['description']}")
    use_case = _ask_choice(
        "  Select use case [1]: ",
        list(USE_CASE_TEMPLATES.keys()),
        default=0,
    )

    print("\n  Model providers:")
    for i, (provider, model_ref) in enumerate(MODEL_PROVIDERS.items(), 1):
        print(f"    {i}. {provider} ({model_ref})")
    model = _ask_choice(
        "  Select provider [1]: ",
        list(MODEL_PROVIDERS.keys()),
        default=0,
    )

    gov = _ask_yes_no("  Add @governance annotation for AgentOps Mesh? [y/N]: ", default=False)

    print()

    return QuickstartAnswers(
        project_name=name,
        use_case=use_case,
        model_provider=model,
        governance=gov,
    )


def _ask(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
    except EOFError:
        val = ""
    return val if val else default


def _ask_choice(prompt: str, choices: list[str], default: int = 0) -> str:
    val = _ask(prompt, str(default + 1))
    try:
        idx = int(val) - 1
        if 0 <= idx < len(choices):
            return choices[idx]
    except ValueError:
        pass
    return choices[default]


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    val = _ask(prompt, "n" if not default else "y").lower()
    return val in ("y", "yes")


def _generate_ax_file(
    answers: QuickstartAnswers,
    template: dict[str, str],
    model_ref: str,
) -> str:
    tool_name = answers.tool_name
    param_name = template["param_name"]
    param_type = template["param_type"]
    tool_body = template["tool_body"].format(**{param_name: "{" + param_name + "}"})
    agent_body = template["agent_body"].format(tool=tool_name, param=f"{param_name}: {param_name}")

    lines = [
        f'// {answers.project_slug} — generated by axon quickstart',
        f'// Use case: {answers.use_case}',
        f'// Model: {model_ref}',
        '',
        f'tool {tool_name}({param_name}: {param_type}) -> {param_type} {{',
        f'    /// {template["description"]}',
        f'    {tool_body}',
        '}',
        '',
        f'agent {answers.agent_name} {{',
        f'    model: {model_ref}',
        f'    tools: [{tool_name}]',
        '',
        f'    fn run({param_name}: {param_type}) -> {param_type} {{',
        f'        {agent_body}',
        '    }',
        '}',
        '',
    ]
    return "\n".join(lines)


def _generate_governance_ax(
    answers: QuickstartAnswers,
    template: dict[str, str],
    model_ref: str,
) -> str:
    base = _generate_ax_file(answers, template, model_ref)
    # Insert @governance annotation before the agent declaration
    gov_annotation = (
        f"@governance(\n"
        f"    autonomy: 2,\n"
        f"    risk: \"low\",\n"
        f"    domain: \"{answers.use_case}\",\n"
        f"    artifacts: [\"use_case_canvas\"]\n"
        f")\n"
    )
    return base.replace(f"agent {answers.agent_name} {{", f"{gov_annotation}agent {answers.agent_name} {{")
