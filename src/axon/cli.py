"""Command-line interface for the AXON Phase 1 prototype.

Task #04 intentionally keeps the CLI small and deterministic. The first
production-worthy milestone is `axon build`: read a `.ax` source file, parse it,
and write the generated FastMCP Python server to disk. `axon serve` is included
as a thin convenience wrapper that builds the server and then optionally runs the
generated Python file.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from result import Err, Ok

from axon.agent_lifecycle import AgentLifecycleManager
from axon.agent_supervisor import AgentSupervisor, ChildSpec, RestartStrategy
from axon.source_watcher import SourceWatcher, AgentReloader
from axon.metrics_exporter import MetricsExporter
from axon.metrics import MetricsCollector, reset_metrics
from axon.codegen.mcp import generate_mcp_server
from axon.ast_snapshot import (
    SnapshotCheckResult,
    check_snapshot_file,
    source_file_to_snapshot_json,
    write_snapshot_file,
)
from axon.check_project import check_project
from axon.config import ConfigError, config_to_json, find_config_path, load_config
from axon.contributor import build_task_ticket, format_task_ticket, task_ticket_to_json, write_task_ticket
from axon.dependency_audit import audit_dependencies, dependency_audit_to_json, format_dependency_audit
from axon.hygiene import audit_hygiene, format_hygiene_report, hygiene_report_to_json, write_default_gitignore
from axon.handoff import build_handoff_checklist, format_handoff_checklist, handoff_checklist_to_json, write_handoff_checklist
from axon.formatter import check_format_file, format_file, write_formatted_file
from axon.foundation_audit import audit_foundation, format_foundation_audit_report, foundation_audit_to_json
from axon.info import collect_info, format_info, format_version, info_to_json, version_to_json
from axon.project import ProjectInitError, create_project, init_project
from axon.project_info import collect_project_info, format_project_info, project_info_to_json
from axon.precommit import (
    PrecommitError,
    check_precommit_hook,
    render_precommit_hook,
    run_precommit_checks,
    write_precommit_hook,
)
from axon.release_notes import build_release_notes, format_release_notes, release_notes_to_json, write_release_notes
from axon.release_bundle_manifest import (
    build_release_bundle_manifest,
    format_release_bundle_manifest,
    release_bundle_manifest_to_json,
    write_release_bundle_manifest,
)
from axon.release_artifacts import (
    format_release_artifact_bundle,
    release_artifact_bundle_to_json,
    write_release_artifacts,
)
from axon.release_artifact_consistency import (
    check_release_artifact_consistency,
    format_release_artifact_consistency_report,
    release_artifact_consistency_to_json,
)
from axon.runtime_rfc import build_runtime_rfc_template, format_runtime_rfc_template, runtime_rfc_to_json, write_runtime_rfc_template
from axon.runtime_plan import build_runtime_plan_from_file, format_runtime_plan, runtime_plan_to_json
from axon.runtime_plan_snapshot import (
    check_runtime_plan_snapshot_file,
    write_runtime_plan_snapshot_file,
)
from axon.runtime_plan_corpus import (
    check_runtime_plan_corpus,
    format_runtime_plan_corpus_report,
    runtime_plan_corpus_report_to_json,
)
from axon.runtime_plan_review import (
    build_runtime_plan_review_checklist,
    format_runtime_plan_review_checklist,
    runtime_plan_review_checklist_to_json,
    write_runtime_plan_review_checklist,
)
from axon.runtime_plan_review_consistency import (
    check_runtime_plan_review_consistency,
    format_runtime_plan_review_consistency_report,
    runtime_plan_review_consistency_report_to_json,
)
from axon.runtime_governance import (
    check_runtime_governance,
    format_runtime_governance_report,
    runtime_governance_report_to_json,
)
from axon.runtime_governance_evidence import (
    build_runtime_governance_evidence,
    format_runtime_governance_evidence,
    runtime_governance_evidence_to_json,
    write_runtime_governance_evidence,
)
from axon.parser import parse
from axon.smoke import report_to_json, smoke_test_source_file
from axon.syntax import check_syntax_file, diagnostic_from_syntax_error, result_to_json
from axon.trace_extract import extract_trace_preview_from_file, format_trace_preview, trace_preview_to_json
from axon.trace import TraceEventType, TraceFormatError
from axon.trace_reader import (
    filter_trace_log,
    format_trace_summary,
    read_trace_file,
    trace_report_to_json,
)
from axon.type_checker import check_types
from axon.token_budget import check_token_budgets
from axon.lsp_server import run_lsp_server
from axon.runtime import RuntimeConfig, RuntimeExecutor, execute_runtime
from axon.validator import (
    AxonValidationError,
    diagnostics_to_json,
    has_errors,
    validate,
    validate_or_raise,
)


DEFAULT_ENCODING = "utf-8"

# In-memory registry for started supervisors (CLI session only)
_SUPERVISOR_REGISTRY: dict[str, AgentSupervisor] = {}
_WATCHER_REGISTRY: dict[str, tuple[SourceWatcher, AgentReloader]] = {}


class AxonCLIError(Exception):
    """User-facing CLI failure with a concise message."""


def build_file(
    source_path: str | Path,
    output_path: str | Path | None = None,
    output_name: str | None = None,
    config_path: str | Path | None = None,
) -> Path:
    """Build one `.ax` file into a generated FastMCP Python server.

    Args:
        source_path: Path to the AXON source file.
        output_path: Optional destination path for generated Python code.
            Defaults to `<source_stem>_server.py` beside the input file.
        output_name: Optional fallback server name passed to the generator when
            the source contains no agent declaration.
        config_path: Optional axon.toml path used for provider defaults.

    Returns:
        The path written.

    Raises:
        AxonCLIError: for missing files or invalid input paths.
        SyntaxError: propagated from the parser for malformed AXON syntax.
    """
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    destination = Path(output_path) if output_path is not None else _default_output_path(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_text = source.read_text(encoding=DEFAULT_ENCODING)
    declarations = parse(source_text)
    validate_or_raise(declarations)
    config = load_config(path=config_path, start=source.parent)
    code = generate_mcp_server(
        declarations,
        output_name=output_name or source.stem,
        config=config,
    )
    destination.write_text(code, encoding=DEFAULT_ENCODING)
    return destination


def build_to_stdout(
    source_path: str | Path,
    output_name: str | None = None,
    config_path: str | Path | None = None,
) -> str:
    """Return generated FastMCP server code for one `.ax` source file."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    source_text = source.read_text(encoding=DEFAULT_ENCODING)
    declarations = parse(source_text)
    validate_or_raise(declarations)
    config = load_config(path=config_path, start=source.parent)
    return generate_mcp_server(declarations, output_name=output_name or source.stem, config=config)


def validate_file(
    source_path: str | Path,
    warnings_as_errors: bool = False,
    json_output: bool = False,
) -> tuple[int, str]:
    """Validate one AXON source file and return (exit_code, output)."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    declarations = parse(source.read_text(encoding=DEFAULT_ENCODING), parse_expressions=False)
    diagnostics = validate(declarations, enable_type_check=False)

    failing = has_errors(diagnostics) or (warnings_as_errors and bool(diagnostics))
    if json_output:
        return (1 if failing else 0), diagnostics_to_json(diagnostics)

    if not diagnostics:
        return 0, f"OK: {source} passed AXON validation"

    lines = [diagnostic.format() for diagnostic in diagnostics]
    return (1 if failing else 0), "\n".join(lines)


def syntax_check_file(
    source_path: str | Path,
    json_output: bool = False,
) -> tuple[int, str]:
    """Parse one AXON file and return rich syntax diagnostics without semantic validation."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    result = check_syntax_file(source)
    if json_output:
        return (0 if result.ok else 1), result_to_json(result)
    if result.ok:
        return 0, f"OK: {source} parsed {len(result.declarations)} declaration(s)"
    return 1, result.format()


def type_check_file(
    source_path: str | Path,
    json_output: bool = False,
) -> tuple[int, str]:
    """Type check one AXON file and return type diagnostics."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    source_text = source.read_text(encoding=DEFAULT_ENCODING)
    declarations = parse(source_text, parse_expressions=True)
    diagnostics = check_types(declarations)

    if json_output:
        return (0 if not diagnostics else 1), diagnostics_to_json(diagnostics)

    if not diagnostics:
        return 0, f"OK: {source} passed type checking"

    lines = [diagnostic.format() for diagnostic in diagnostics]
    return 1, "\n".join(lines)


def generate_docs_file(
    source_path: str | Path,
    output_path: str | Path,
) -> tuple[int, str]:
    """Generate documentation from an AXON file."""
    source = Path(source_path)
    output = Path(output_path)
    
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")
    
    try:
        from axon.docs_generator import generate_docs_file as gen_docs
        gen_docs(str(source), str(output))
        return 0, f"Documentation generated: {output}"
    except Exception as e:
        return 1, f"Error generating documentation: {e}"


def show_config(
    config_path: str | Path | None = None,
    start_path: str | Path | None = None,
    json_output: bool = False,
    resolve_env: bool = False,
) -> tuple[int, str]:
    """Load and safely display AXON project configuration."""
    resolved_path = Path(config_path).expanduser().resolve() if config_path else find_config_path(start_path)
    if resolved_path is None:
        raise AxonCLIError("axon.toml not found; pass --config or run from an AXON project")

    config = load_config(
        path=resolved_path,
        resolve_env=resolve_env,
        allow_missing_env=True,
    )

    if json_output:
        return 0, config_to_json(config)

    lines = [f"Config: {config.path}"]
    lines.append("Defaults:")
    if config.defaults:
        for key, value in sorted(config.defaults.items()):
            lines.append(f"  {key}: {value}")
    else:
        lines.append("  <none>")

    lines.append("Providers:")
    if config.providers:
        for name, provider in sorted(config.providers.items()):
            lines.append(f"  {name}:")
            safe = provider.safe_settings()
            if safe:
                for key, value in sorted(safe.items()):
                    lines.append(f"    {key}: {value}")
            else:
                lines.append("    <no settings>")
    else:
        lines.append("  <none>")

    return 0, "\n".join(lines)




def hygiene_command(
    project_path: str | Path = ".",
    *,
    json_output: bool = False,
    write_gitignore: bool = False,
    force: bool = False,
) -> tuple[int, str]:
    """Audit or write repository hygiene ignore rules for an AXON project."""
    root = Path(project_path).expanduser().resolve()
    if write_gitignore:
        destination = write_default_gitignore(root / ".gitignore", force=force)
        return 0, f"Wrote AXON .gitignore template: {destination}"
    report = audit_hygiene(root)
    return (0 if report.passed else 1), hygiene_report_to_json(report) if json_output else format_hygiene_report(report)

def dependency_audit_command(
    project_path: str | Path = ".",
    *,
    json_output: bool = False,
) -> tuple[int, str]:
    """Audit dependency and optional-extra boundaries for an AXON project."""
    report = audit_dependencies(project_path)
    return (0 if report.passed else 1), dependency_audit_to_json(report) if json_output else format_dependency_audit(report)


def check_project_command(
    project_path: str | Path = ".",
    *,
    json_output: bool = False,
    no_smoke: bool = False,
    warnings_as_errors: bool = False,
    snapshot_dir: str | Path | None = None,
    require_snapshots: bool = False,
) -> tuple[int, str]:
    """Run the AXON project-level quality gate and return (exit_code, output)."""
    report = check_project(
        project_path,
        no_smoke=no_smoke,
        warnings_as_errors=warnings_as_errors,
        snapshot_dir=snapshot_dir,
        require_snapshots=require_snapshots,
    )
    return (0 if report.passed else 1), report.to_json() if json_output else report.format()

def release_notes_command(
    *,
    version: str | None = None,
    release_date: str | None = None,
    project_path: str | Path = ".",
    changes: Sequence[str] | None = None,
    tests: Sequence[str] | None = None,
    output_path: str | Path | None = None,
    json_output: bool = False,
) -> tuple[int, str]:
    """Generate Markdown or JSON release notes for the current AXON project."""
    commands = _all_command_names(include_aliases=True)
    notes = build_release_notes(
        version=version,
        release_date=release_date,
        project_path=project_path,
        commands=commands,
        changes=changes,
        tests=tests,
    )

    if output_path is not None:
        destination = write_release_notes(output_path, notes, json_output=json_output)
        return 0, f"Wrote release notes: {destination}"

    return 0, release_notes_to_json(notes) if json_output else format_release_notes(notes).rstrip("\n")


def trace_preview_file(
    source_path: str | Path,
    json_output: bool = False,
    jsonl_output: bool = False,
) -> tuple[int, str]:
    """Generate a static AEL trace preview for one AXON source file."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    log = extract_trace_preview_from_file(source)
    if jsonl_output:
        return 0, log.to_jsonl().rstrip("\n")
    if json_output:
        return 0, trace_preview_to_json(log)
    return 0, format_trace_preview(log)


def run_file(
    source_path: str | Path,
    args: dict[str, Any] | None = None,
    trace_output: Path | str | None = None,
    memory_path: Path | str | None = None,
    checkpoint: bool = False,
    mock: bool = True,
    provider_name: str | None = None,
    stream: bool = False,
    flow_name: str | None = None,
    agent_name: str | None = None,
    replay_path: Path | str | None = None,
    json_output: bool = False,
    sandbox_timeout_ms: int | None = 5000,
    sandbox_max_depth: int | None = 100,
    sandbox_denied_tools: set[str] | None = None,
    metrics_output: bool = False,
    strict_types: bool = False,
    via_ir: bool = False,
) -> tuple[int, str]:
    """Run one AXON source file and return (exit_code, output)."""
    from axon.config import load_config

    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    # Load axon.toml for sandbox defaults (CLI flags override config)
    axon_cfg = load_config(start=source)
    effective_timeout = sandbox_timeout_ms
    if effective_timeout is None:
        effective_timeout = int(axon_cfg.sandbox.timeout_ms) if axon_cfg.sandbox.timeout_ms is not None else 5000
    effective_depth = sandbox_max_depth
    if effective_depth is None:
        effective_depth = int(axon_cfg.sandbox.max_depth) if axon_cfg.sandbox.max_depth is not None else 100
    effective_denied = sandbox_denied_tools or set()
    if axon_cfg.sandbox.denied_tools:
        # Merge axon.toml denied tools with CLI denied tools
        toml_denied = {t.strip() for t in axon_cfg.sandbox.denied_tools.split(",")}
        effective_denied = effective_denied | toml_denied

    config = RuntimeConfig(
        source_path=source,
        args=args or {},
        trace_output=Path(trace_output) if trace_output else None,
        memory_path=Path(memory_path) if memory_path else None,
        checkpoint=checkpoint,
        mock=mock,
        provider_name=provider_name,
        stream=stream,
        flow_name=flow_name,
        agent_name=agent_name,
        replay_path=Path(replay_path) if replay_path else None,
        sandbox_timeout_ms=effective_timeout,
        sandbox_max_depth=effective_depth,
        sandbox_denied_tools=effective_denied,
        strict_types=strict_types,
        via_ir=via_ir,
    )

    executor = RuntimeExecutor(config)
    result = executor.execute()

    if isinstance(result, Err):
        error = result.err_value
        if json_output:
            return 1, f'{{"error": "{error}"}}'
        return 1, f"Error: {error}"

    output = result.ok_value
    if metrics_output:
        import json
        metrics = executor.get_metrics()
        if json_output:
            return 0, json.dumps({"output": output, "metrics": metrics}, indent=2)
        return 0, output + "\n\n--- Runtime Metrics ---\n" + json.dumps(metrics, indent=2)

    if json_output:
        return 0, f'{{"output": "{output}"}}'

    return 0, output


def run_file_stream(
    source_path: str | Path,
    args: dict[str, Any] | None = None,
    mock: bool = True,
    provider_name: str | None = None,
    flow_name: str | None = None,
    agent_name: str | None = None,
    json_output: bool = False,
) -> tuple[int, str]:
    """Run an AXON source file with async streaming and return (exit_code, output)."""
    from axon.async_runtime import AsyncRuntimeConfig, AsyncRuntimeExecutor

    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    effective_provider = "@mock/model" if mock else f"@{provider_name}/gpt-4" if provider_name else "@openai/gpt-4"
    config = AsyncRuntimeConfig(
        source_path=source,
        provider_name=effective_provider,
        stream=True,
    )
    executor = AsyncRuntimeExecutor(config)

    async def _stream() -> str:
        chunks: list[str] = []
        async for chunk in executor.execute_stream():
            if isinstance(chunk, Ok):
                chunks.append(chunk.ok_value)
            # Err chunks are silently ignored in stream mode for CLI UX
        return "".join(chunks)

    output = asyncio.run(_stream())

    if json_output:
        import json
        return 0, json.dumps({"output": output}, indent=2)
    return 0, output


def health_check_file(
    json_output: bool = False,
) -> tuple[int, str]:
    """Check AXON runtime health status.

    Reports on:
    - Parser health
    - Type checker health
    - Provider availability (mock, openai, anthropic)
    - Runtime boundary compliance
    """
    import os
    import axon

    checks = {
        "axon_version": axon.__version__ if hasattr(axon, "__version__") else "unknown",
        "parser": "ok",
        "type_checker": "ok",
        "mock_provider": "ok",
        "openai_provider": "not_installed",
        "anthropic_provider": "not_installed",
        "openai_api_key": "missing",
        "anthropic_api_key": "missing",
    }

    # Check parser
    try:
        from axon.parser import parse
        parse("agent Test { model: @mock/test tools: [] }")
    except Exception as e:
        checks["parser"] = f"error: {e}"

    # Check type checker
    try:
        from axon.type_checker import check_types
        decls = parse("agent Test { model: @mock/test tools: [] fn run() -> Str { 'hello' } }", parse_expressions=True)
        check_types(decls)
    except Exception as e:
        checks["type_checker"] = f"error: {e}"

    # Check providers
    try:
        from axon.providers.openai_provider import OpenAIProvider
        checks["openai_provider"] = "available"
    except Exception:
        checks["openai_provider"] = "not_installed"

    try:
        from axon.providers.anthropic_provider import AnthropicProvider
        checks["anthropic_provider"] = "available"
    except Exception:
        checks["anthropic_provider"] = "not_installed"

    # Check API keys
    if os.environ.get("OPENAI_API_KEY"):
        checks["openai_api_key"] = "present"
    if os.environ.get("ANTHROPIC_API_KEY"):
        checks["anthropic_api_key"] = "present"

    healthy = all(
        v == "ok" or v == "available" or v == "not_installed" or v == "missing"
        for v in checks.values()
    )
    status = "healthy" if healthy else "degraded"

    if json_output:
        import json
        return 0 if healthy else 1, json.dumps({"status": status, "checks": checks}, indent=2)

    lines = [f"AXON Health Check: {status}", ""]
    for name, value in checks.items():
        icon = "✓" if value in ("ok", "available", "present") else "✗"
        lines.append(f"  {icon} {name}: {value}")
    return 0 if healthy else 1, "\n".join(lines)


def trace_read_file(
    trace_path: str | Path,
    *,
    event_type: TraceEventType | None = None,
    agent: str | None = None,
    include_events: bool = False,
    json_output: bool = False,
    jsonl_output: bool = False,
) -> tuple[int, str]:
    """Read, validate, optionally filter, and format an AEL JSONL trace log."""
    trace_file = Path(trace_path)
    log = read_trace_file(trace_file)
    filtered = filter_trace_log(log, event_type=event_type, agent=agent)
    if jsonl_output:
        return 0, filtered.to_jsonl().rstrip("\n")
    if json_output:
        return 0, trace_report_to_json(filtered, source=trace_file)
    return 0, format_trace_summary(filtered, source=trace_file, include_events=include_events)



def ast_snapshot_file(
    source_path: str | Path,
    *,
    include_lines: bool = True,
    write_path: str | Path | None = None,
    check_path: str | Path | None = None,
) -> tuple[int, str]:
    """Render, write, or check a stable JSON AST snapshot for one AXON file."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")

    if write_path is not None and check_path is not None:
        raise AxonCLIError("choose only one of --write or --check")

    if write_path is not None:
        destination = write_snapshot_file(source, write_path, include_lines=include_lines)
        return 0, f"Wrote AST snapshot: {destination}"

    if check_path is not None:
        result = check_snapshot_file(source, check_path, include_lines=include_lines)
        return (0 if result.matched else 1), result.message

    return 0, source_file_to_snapshot_json(source, include_lines=include_lines).rstrip("\n")


def format_source_file(
    source_path: str | Path,
    *,
    check: bool = False,
    write: bool = False,
) -> tuple[int, str]:
    """Format, check, or print canonical AXON source formatting."""
    source = Path(source_path)
    if not source.exists():
        raise AxonCLIError(f"source file not found: {source}")
    if not source.is_file():
        raise AxonCLIError(f"source path is not a file: {source}")
    if check and write:
        raise AxonCLIError("choose only one of --check or --write")

    if check:
        result = check_format_file(source)
        return (0 if result.formatted else 1), result.message

    if write:
        destination = write_formatted_file(source)
        return 0, f"Formatted AXON source: {destination}"

    return 0, format_file(source).rstrip("\n")

def serve_file(
    source_path: str | Path,
    output_path: str | Path | None = None,
    output_name: str | None = None,
    dry_run: bool = False,
    python_executable: str | None = None,
    config_path: str | Path | None = None,
) -> int:
    """Build and optionally run the generated FastMCP server.

    In Phase 1, `serve` remains deliberately thin: it writes the same generated
    Python server as `build`, then runs that file with Python unless `dry_run` is
    true. This avoids adding FastMCP as a dependency of the compiler itself.
    """
    generated_path = build_file(
        source_path,
        output_path=output_path,
        output_name=output_name,
        config_path=config_path,
    )
    print(f"Generated MCP server: {generated_path}")

    if dry_run:
        print("Dry run enabled; server was not started.")
        return 0

    executable = python_executable or sys.executable
    completed = subprocess.run([executable, str(generated_path)], check=False)
    return int(completed.returncode)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AXON CLI and return a process exit code."""
    parser = _make_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "version":
            print(version_to_json() if args.json else format_version())
            return 0

        if args.command == "info":
            info = collect_info(project_path=args.path, config_path=args.config)
            print(info_to_json(info) if args.json else format_info(info))
            return 0

        if args.command == "project-info":
            report = collect_project_info(args.path)
            print(project_info_to_json(report) if args.json else format_project_info(report))
            return 0

        if args.command == "foundation-audit":
            report = audit_foundation(args.path)
            print(foundation_audit_to_json(report) if args.json else format_foundation_audit_report(report))
            return 0 if report.passed else 1

        if args.command == "handoff":
            checklist = build_handoff_checklist(args.path, full=args.full)
            if args.output:
                destination = write_handoff_checklist(args.output, checklist, json_output=args.json)
                print(f"Wrote AXON handoff checklist: {destination}")
            else:
                print(handoff_checklist_to_json(checklist) if args.json else format_handoff_checklist(checklist))
            return 0

        if args.command in {"release-notes", "changelog"}:
            code, output = release_notes_command(
                version=args.version,
                release_date=args.date,
                project_path=args.path,
                changes=args.change,
                tests=args.tests,
                output_path=args.output,
                json_output=args.json,
            )
            print(output)
            return code

        if args.command == "release-bundle-manifest":
            manifest = build_release_bundle_manifest(args.path)
            if args.output:
                destination = write_release_bundle_manifest(
                    args.output,
                    manifest,
                    format="json" if args.json else args.format,
                )
                print(f"Wrote release bundle manifest: {destination}")
            else:
                print(
                    release_bundle_manifest_to_json(manifest)
                    if args.json
                    else format_release_bundle_manifest(manifest)
                )
            return 0 if manifest.passed else 1

        if args.command == "release-artifacts":
            bundle = write_release_artifacts(
                args.path,
                output_dir=args.output_dir,
                version=args.version,
                release_date=args.date,
                changes=args.change,
                tests=args.tests,
                skip_corpus=args.skip_corpus,
            )
            print(release_artifact_bundle_to_json(bundle) if args.json else format_release_artifact_bundle(bundle))
            return 0 if bundle.passed else 1

        if args.command in {"release-artifacts-check", "release-artifact-consistency"}:
            report = check_release_artifact_consistency(args.path)
            print(
                release_artifact_consistency_to_json(report)
                if args.json
                else format_release_artifact_consistency_report(report)
            )
            return 0 if report.passed else 1

        if args.command == "task-template":
            ticket = build_task_ticket(number=args.number, title=args.title, module=args.module)
            if args.output:
                destination = write_task_ticket(args.output, ticket, json_output=args.json)
                print(f"Wrote AXON task ticket template: {destination}")
            else:
                print(task_ticket_to_json(ticket) if args.json else format_task_ticket(ticket).rstrip("\n"))
            return 0

        if args.command == "runtime-rfc-template":
            rfc = build_runtime_rfc_template(
                number=args.number,
                title=args.title,
                owner=args.owner,
                status=args.status,
            )
            if args.output:
                destination = write_runtime_rfc_template(args.output, rfc, json_output=args.json)
                print(f"Wrote AXON runtime RFC template: {destination}")
            else:
                print(runtime_rfc_to_json(rfc) if args.json else format_runtime_rfc_template(rfc).rstrip("\n"))
            return 0

        if args.command == "runtime-plan":
            if args.write and args.check:
                raise AxonCLIError("runtime-plan accepts either --write or --check, not both")
            if args.write:
                destination = write_runtime_plan_snapshot_file(args.source, args.write, root=args.root)
                print(f"Wrote runtime-plan snapshot: {destination}")
                return 0
            if args.check:
                result = check_runtime_plan_snapshot_file(args.source, args.check, root=args.root)
                print(result.message)
                return 0 if result.matched else 1
            plan = build_runtime_plan_from_file(args.source)
            print(runtime_plan_to_json(plan) if args.json else format_runtime_plan(plan))
            return 0

        if args.command == "runtime-plan-corpus":
            report = check_runtime_plan_corpus(
                args.path,
                examples_dir=args.examples_dir,
                snapshot_dir=args.snapshot_dir,
                require_snapshots=not args.allow_missing_snapshots,
            )
            print(runtime_plan_corpus_report_to_json(report) if args.json else format_runtime_plan_corpus_report(report))
            return 0 if report.passed else 1

        if args.command == "runtime-plan-review":
            checklist = build_runtime_plan_review_checklist(change=args.change)
            if args.output:
                destination = write_runtime_plan_review_checklist(args.output, checklist, json_output=args.json)
                print(f"Wrote runtime-plan review checklist: {destination}")
            else:
                print(
                    runtime_plan_review_checklist_to_json(checklist)
                    if args.json
                    else format_runtime_plan_review_checklist(checklist).rstrip("\n")
                )
            return 0

        if args.command == "runtime-plan-review-check":
            report = check_runtime_plan_review_consistency(
                args.path,
                examples_dir=args.examples_dir,
                snapshot_dir=args.snapshot_dir,
                skip_corpus=args.skip_corpus,
            )
            print(
                runtime_plan_review_consistency_report_to_json(report)
                if args.json
                else format_runtime_plan_review_consistency_report(report)
            )
            return 0 if report.passed else 1

        if args.command == "runtime-governance":
            report = check_runtime_governance(
                args.path,
                examples_dir=args.examples_dir,
                snapshot_dir=args.snapshot_dir,
                skip_corpus=args.skip_corpus,
            )
            print(runtime_governance_report_to_json(report) if args.json else format_runtime_governance_report(report))
            return 0 if report.passed else 1

        if args.command == "runtime-governance-evidence":
            evidence = build_runtime_governance_evidence(
                args.path,
                examples_dir=args.examples_dir,
                snapshot_dir=args.snapshot_dir,
                skip_corpus=args.skip_corpus,
            )
            if args.output:
                destination = write_runtime_governance_evidence(
                    args.output,
                    evidence,
                    format="json" if args.json else args.format,
                )
                print(f"Wrote runtime governance evidence: {destination}")
            else:
                print(
                    runtime_governance_evidence_to_json(evidence)
                    if args.json
                    else format_runtime_governance_evidence(evidence)
                )
            return 0 if evidence.passed else 1

        if args.command == "runtime-governance-gate":
            report = check_runtime_governance(
                args.path,
                examples_dir=args.examples_dir,
                snapshot_dir=args.snapshot_dir,
                skip_corpus=args.skip_corpus,
            )
            print(runtime_governance_report_to_json(report) if args.json else format_runtime_governance_report(report))
            return 0 if report.passed else 1

        if args.command == "new":
            result = create_project(args.path, force=args.force)
            print(result.format())
            return 0

        if args.command == "init":
            result = init_project(args.path, force=args.force)
            print(result.format())
            return 0

        if args.command == "precommit":
            if args.action == "print":
                print(render_precommit_hook().rstrip("\n"))
                return 0
            if args.action == "install":
                result = write_precommit_hook(args.path, hook_path=args.hook_path, force=args.force)
                print(result.to_json() if args.json else result.message)
                return 0
            if args.action == "check":
                result = check_precommit_hook(args.path, hook_path=args.hook_path)
                print(result.to_json() if args.json else result.message)
                return 0 if result.installed else 1
            if args.action == "run":
                result = run_precommit_checks(args.path, full=args.full)
                print(result.to_json() if args.json else result.format())
                return 0 if result.passed else 1

        if args.command in {"deps", "dependency-audit"}:
            code, output = dependency_audit_command(
                args.path,
                json_output=args.json,
            )
            print(output)
            return code

        if args.command in {"hygiene", "repo-hygiene"}:
            code, output = hygiene_command(
                args.path,
                json_output=args.json,
                write_gitignore=args.write_gitignore,
                force=args.force,
            )
            print(output)
            return code

        if args.command == "config":
            code, output = show_config(
                config_path=args.config,
                json_output=args.json,
                resolve_env=args.resolve_env,
            )
            print(output)
            return code

        if args.command == "validate":
            code, output = validate_file(
                args.source,
                warnings_as_errors=args.warnings_as_errors,
                json_output=args.json,
            )
            print(output)
            return code

        if args.command == "type-check":
            code, output = type_check_file(
                args.source,
                json_output=args.json,
            )
            print(output)
            return code

        if args.command == "token-budget":
            code, output = token_budget_check_file(
                args.source,
                json_output=args.json,
            )
            print(output)
            return code

        if args.command == "lsp":
            # LSP server runs as a long-running process
            run_lsp_server()
            return 0

        if args.command == "docs":
            code, output = generate_docs_file(
                args.source,
                args.output,
            )
            print(output)
            return code

        if args.command == "syntax":
            code, output = syntax_check_file(
                args.source,
                json_output=args.json,
            )
            print(output)
            return code

        if args.command == "ast":
            code, output = ast_snapshot_file(
                args.source,
                include_lines=not args.no_lines,
                write_path=args.write,
                check_path=args.check,
            )
            print(output)
            return code

        if args.command == "format":
            code, output = format_source_file(
                args.source,
                check=args.check,
                write=args.write,
            )
            print(output)
            return code

        if args.command in {"check-project", "doctor"}:
            code, output = check_project_command(
                args.path,
                json_output=args.json,
                no_smoke=args.no_smoke,
                warnings_as_errors=args.warnings_as_errors,
                snapshot_dir=args.snapshot_dir,
                require_snapshots=args.require_snapshots,
            )
            print(output)
            return code

        if args.command == "trace-preview":
            code, output = trace_preview_file(
                args.source,
                json_output=args.json,
                jsonl_output=args.jsonl,
            )
            print(output)
            return code

        if args.command in {"trace-read", "trace-log"}:
            code, output = trace_read_file(
                args.trace_file,
                event_type=args.type,
                agent=args.agent,
                include_events=args.events,
                json_output=args.json,
                jsonl_output=args.jsonl,
            )
            print(output)
            return code

        if args.command == "smoke":
            report = smoke_test_source_file(args.source, output_name=args.name)
            print(report_to_json(report) if args.json else report.format())
            return 0 if report.passed else 1

        if args.command == "build":
            if args.stdout:
                code = build_to_stdout(args.source, output_name=args.name, config_path=args.config)
                print(code)
                return 0

            output_path = build_file(
                args.source,
                output_path=args.output,
                output_name=args.name,
                config_path=args.config,
            )
            print(f"Generated MCP server: {output_path}")
            return 0

        if args.command == "compile":
            source_path = Path(args.source)
            if not source_path.exists():
                raise AxonCLIError(f"Source file not found: {args.source}")

            target = getattr(args, "target", "ir")

            if target == "ts" or target == "typescript":
                from axon.codegen.typescript import generate_typescript
                from axon.parser import parse
                declarations = parse(source_path.read_text(encoding="utf-8"))
                ts_code = generate_typescript(declarations, output_name=source_path.stem)

                if getattr(args, "output", None):
                    out_path = Path(args.output)
                    out_path.write_text(ts_code, encoding="utf-8")
                    print(f"TypeScript written to {out_path}")
                else:
                    print(ts_code)
                return 0

            if target == "governance":
                from axon.codegen.governance import generate_governance_submission
                from axon.parser import parse
                from axon.validator import validate
                declarations = parse(source_path.read_text(encoding="utf-8"))
                diagnostics = validate(declarations)
                errors = [d for d in diagnostics if d.severity == "error"]
                if errors:
                    for e in errors:
                        print(f"error: {e}", file=sys.stderr)
                    raise AxonCLIError(f"Validation failed with {len(errors)} error(s)")
                submission = generate_governance_submission(
                    declarations,
                    source_filename=source_path.name,
                )
                gov_json = json.dumps(submission, indent=2)

                if getattr(args, "output", None):
                    out_path = Path(args.output)
                    out_path.write_text(gov_json, encoding="utf-8")
                    print(f"AgentOps Mesh governance submission written to {out_path}")
                else:
                    print(gov_json)
                return 0

            import json
            from axon.ir_compiler import compile_to_ir

            ir = compile_to_ir(source_path)
            ir_json = json.dumps(ir.to_dict(), indent=2)

            if getattr(args, "output", None):
                out_path = Path(args.output)
                out_path.write_text(ir_json, encoding="utf-8")
                print(f"IR written to {out_path}")
            elif getattr(args, "emit_ir", False):
                print(ir_json)
            else:
                print(f"Compiled successfully: {ir.version}")
                parts = [
                    f"Agents: {len(ir.agents)}",
                    f"Flows: {len(ir.flows)}",
                    f"Tools: {len(ir.tools)}",
                    f"RAGs: {len(ir.rags)}",
                    f"Prompts: {len(ir.prompts)}",
                    f"Types: {len(ir.type_aliases)}",
                    f"Imports: {len(ir.imports)}",
                ]
                print(f"  {', '.join(parts)}")
            return 0

        if args.command == "govern":
            source_path = Path(args.source)
            if not source_path.exists():
                raise AxonCLIError(f"Source file not found: {args.source}")

            from axon.codegen.governance import generate_governance_submission
            from axon.parser import parse
            from axon.validator import validate

            declarations = parse(source_path.read_text(encoding="utf-8"))
            diagnostics = validate(declarations)
            errors = [d for d in diagnostics if d.severity == "error"]
            if errors:
                for e in errors:
                    print(f"error: {e}", file=sys.stderr)
                raise AxonCLIError(f"Validation failed with {len(errors)} error(s)")

            business_owner = getattr(args, "business_owner", "TBD")
            technical_owner = getattr(args, "technical_owner", "TBD")
            target_env = getattr(args, "target_environment", "sandbox")

            submission = generate_governance_submission(
                declarations,
                source_filename=source_path.name,
                business_owner=business_owner,
                technical_owner=technical_owner,
                target_environment=target_env,
            )
            gov_json = json.dumps(submission, indent=2)

            mesh_url = getattr(args, "mesh_url", None)
            if mesh_url:
                import urllib.request
                url = f"{mesh_url.rstrip('/')}/governance/run"
                print(f"Submitting governance request to {url}...")
                req = urllib.request.Request(
                    url,
                    data=gov_json.encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                    gates = result.get("gates", [])
                    passed = sum(1 for g in gates if g.get("status") == "pass")
                    caution = sum(1 for g in gates if g.get("status") == "caution")
                    failed = sum(1 for g in gates if g.get("status") == "fail")
                    print(f"Governance decision: {result.get('overall_decision', 'N/A')}")
                    print(f"  Gates: {passed} passed, {caution} caution, {failed} failed")
                    if getattr(args, "output", None):
                        out_path = Path(args.output)
                        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                        print(f"Result written to {out_path}")
                except Exception as e:
                    print(f"Submit failed: {e}", file=sys.stderr)
                    raise AxonCLIError(f"Failed to submit to AgentOps Mesh at {mesh_url}")
            elif getattr(args, "output", None):
                out_path = Path(args.output)
                out_path.write_text(gov_json, encoding="utf-8")
                print(f"AgentOps Mesh governance submission written to {out_path}")
            else:
                print(gov_json)
            return 0

        if args.command == "ci-template":
            platform = getattr(args, "platform", "github-actions")
            output = getattr(args, "output", None)
            mesh_url = getattr(args, "mesh_url", None)
            template = _generate_ci_template(platform, mesh_url)
            if output:
                out_path = Path(output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(template, encoding="utf-8")
                print(f"CI template written to {out_path}")
            else:
                print(template)
            return 0

        if args.command == "explain":
            source_path = Path(args.source)
            if not source_path.exists():
                raise AxonCLIError(f"Source file not found: {args.source}")
            from axon.parser import parse as _parse
            from axon.validator import validate as _validate
            declarations = _parse(source_path.read_text(encoding="utf-8"))
            diagnostics = _validate(declarations)
            errors = [d for d in diagnostics if d.severity == "error"]
            warnings = [d for d in diagnostics if d.severity == "warning"]
            if not errors and not warnings:
                print(f"No issues found in {source_path.name}. Everything looks good!")
                return 0
            explanation = _explain_diagnostics(errors, warnings, source_path.name)
            print(explanation)
            return 1 if errors else 0

        if args.command == "run":
            # Parse --arg key=value strings into a dict
            run_args: dict[str, Any] = {}
            for arg in args.args:
                if "=" not in arg:
                    raise AxonCLIError(f"--arg must be key=value, got: {arg}")
                key, value = arg.split("=", 1)
                # Try to parse as int/float/bool, fallback to string
                value = _parse_cli_arg_value(value)
                run_args[key] = value

            denied_tools = set(args.sandbox_denied_tools) if getattr(args, "sandbox_denied_tools", None) else set()
            if getattr(args, "stream", False):
                code, output = run_file_stream(
                    args.source,
                    args=run_args,
                    mock=args.mock,
                    provider_name=args.provider_name,
                    flow_name=args.flow_name,
                    agent_name=args.agent_name,
                    json_output=args.json,
                )
            else:
                code, output = run_file(
                    args.source,
                    args=run_args,
                    trace_output=args.trace_output,
                    memory_path=args.memory_path,
                    checkpoint=args.checkpoint,
                    mock=args.mock,
                    provider_name=args.provider_name,
                    flow_name=args.flow_name,
                    agent_name=args.agent_name,
                    replay_path=args.replay_path,
                    json_output=args.json,
                    sandbox_timeout_ms=args.sandbox_timeout,
                    sandbox_max_depth=args.sandbox_max_depth,
                    sandbox_denied_tools=denied_tools,
                    metrics_output=getattr(args, "metrics", False),
                    strict_types=getattr(args, "strict_types", False),
                    via_ir=getattr(args, "via_ir", False),
                )
            print(output)
            return code

        if args.command == "serve":
            return serve_file(
                args.source,
                output_path=args.output,
                output_name=args.name,
                dry_run=args.dry_run,
                python_executable=args.python,
                config_path=args.config,
            )

        if args.command == "serve-api":
            import uvicorn
            from axon.api_server import app, _state
            if args.api_key:
                _state.api_key = args.api_key
            print(f"Starting AXON API server on {args.host}:{args.port}")
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
            return 0

        if args.command == "health":
            code, output = health_check_file(json_output=args.json)
            print(output)
            return code

        if args.command == "agent":
            manager = AgentLifecycleManager()
            sub = args.agent_command

            if sub == "spawn":
                run_args: dict[str, Any] = {}
                for arg in args.args:
                    if "=" not in arg:
                        raise AxonCLIError(f"--arg must be key=value, got: {arg}")
                    key, value = arg.split("=", 1)
                    value = _parse_cli_arg_value(value)
                    run_args[key] = value
                result = manager.spawn(
                    source_path=Path(args.source),
                    name=args.name,
                    args=run_args,
                    mock=args.mock,
                    provider_name=args.provider_name,
                    trace_output=Path(args.trace) if args.trace else None,
                    memory_path=Path(args.memory) if args.memory else None,
                    checkpoint=args.checkpoint,
                    stream=getattr(args, "stream", False),
                )
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                print(f"Spawned agent '{args.name}' (id={result.ok_value})")
                return 0

            if sub == "pause":
                result = manager.pause(args.name)
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                print(f"Paused agent '{args.name}'")
                return 0

            if sub == "resume":
                result = manager.resume(args.name)
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                print(f"Resumed agent '{args.name}'")
                return 0

            if sub == "terminate":
                result = manager.terminate(args.name, reason=args.reason or "user_request")
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                print(f"Terminated agent '{args.name}'")
                return 0

            if sub == "status":
                result = manager.status(args.name)
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                inst = result.ok_value
                if args.json:
                    import json
                    print(json.dumps(inst.to_dict(), indent=2))
                else:
                    print(f"Agent: {inst.name} (id={inst.id})")
                    print(f"  Status: {inst.status.value}")
                    print(f"  Source: {inst.source_path}")
                    print(f"  Last output: {inst.last_output[:100]}")
                    if inst.last_error:
                        print(f"  Last error: {inst.last_error[:100]}")
                return 0

            if sub == "list":
                agents = manager.list_agents()
                if args.json:
                    import json
                    print(json.dumps([a.to_dict() for a in agents], indent=2))
                else:
                    if not agents:
                        print("No active agents")
                    else:
                        for a in agents:
                            print(f"{a.name:20} {a.status.value:10} {a.source_path}")
                return 0

            if sub == "checkpoint":
                from axon.checkpoint_manager import CheckpointManager
                cm = CheckpointManager(manager)
                output = Path(args.output) if args.output else None
                result = cm.checkpoint(args.name, output_path=output)
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                print(f"Checkpoint saved: {result.ok_value}")
                return 0

            if sub == "restore":
                from axon.checkpoint_manager import CheckpointManager
                cm = CheckpointManager(manager)
                result = cm.restore(
                    args.name,
                    snapshot_path=Path(args.snapshot),
                    mock=args.mock,
                    provider_name=args.provider_name,
                )
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                print(f"Restored agent '{args.name}' (id={result.ok_value})")
                return 0

            raise AxonCLIError(f"Unknown agent subcommand: {sub}")

        if args.command == "supervisor":
            sub = args.supervisor_command

            if sub == "start":
                strategy = RestartStrategy(args.strategy)
                supervisor = AgentSupervisor(
                    name=args.name,
                    strategy=strategy,
                    max_restarts=args.max_restarts,
                    max_seconds=args.max_seconds,
                    poll_interval_ms=args.poll_interval,
                )
                for child in args.children:
                    parts = child.split("::", 1)
                    if len(parts) != 2:
                        raise AxonCLIError(f"Child spec must be source::name, got: {child}")
                    source_path, child_name = parts
                    supervisor.add_child(
                        ChildSpec(
                            source_path=Path(source_path),
                            name=child_name,
                            mock=args.mock,
                            provider_name=args.provider_name,
                        )
                    )
                result = supervisor.start()
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)
                _SUPERVISOR_REGISTRY[args.name] = supervisor
                print(f"Started supervisor '{args.name}' with strategy={args.strategy}")
                return 0

            if sub == "stop":
                supervisor = _SUPERVISOR_REGISTRY.pop(args.name, None)
                if supervisor is None:
                    raise AxonCLIError(f"Supervisor '{args.name}' not found")
                supervisor.stop(reason=args.reason or "user_request")
                print(f"Stopped supervisor '{args.name}'")
                return 0

            if sub == "status":
                supervisor = _SUPERVISOR_REGISTRY.get(args.name)
                if supervisor is None:
                    raise AxonCLIError(f"Supervisor '{args.name}' not found")
                state = supervisor.state()
                if args.json:
                    import json
                    print(json.dumps(
                        {
                            "name": state.name,
                            "strategy": state.strategy.value,
                            "running": state.running,
                            "child_count": len(state.children),
                            "shutdown_reason": state.shutdown_reason,
                        },
                        indent=2,
                    ))
                else:
                    print(f"Supervisor: {state.name}")
                    print(f"  Strategy: {state.strategy.value}")
                    print(f"  Running: {state.running}")
                    print(f"  Children: {len(state.children)}")
                    for child in state.children:
                        print(f"    - {child.name} ({child.source_path})")
                return 0

            raise AxonCLIError(f"Unknown supervisor subcommand: {sub}")

        if args.command == "watch":
            sub = args.watch_command

            if sub == "start":
                run_args: dict[str, Any] = {}
                for arg in args.args:
                    if "=" not in arg:
                        raise AxonCLIError(f"--arg must be key=value, got: {arg}")
                    key, value = arg.split("=", 1)
                    value = _parse_cli_arg_value(value)
                    run_args[key] = value

                lifecycle = AgentLifecycleManager()
                watcher = SourceWatcher(poll_interval_ms=args.poll_interval)
                reloader = AgentReloader(lifecycle, watcher)

                spec = ChildSpec(
                    source_path=Path(args.source),
                    name=args.name,
                    args=run_args,
                    mock=args.mock,
                    provider_name=args.provider_name,
                )
                reloader.watch(spec)
                watcher.start()

                # Spawn initial agent
                result = lifecycle.spawn(
                    source_path=spec.source_path,
                    name=spec.name,
                    args=spec.args,
                    mock=spec.mock,
                    provider_name=spec.provider_name,
                )
                if isinstance(result, Err):
                    raise AxonCLIError(result.err_value)

                _WATCHER_REGISTRY[args.name] = (watcher, reloader)
                print(f"Watching agent '{args.name}' ({args.source}) — press Ctrl+C to stop")
                try:
                    while True:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    watcher.stop()
                    lifecycle.terminate(args.name, reason="watch_interrupt")
                    print(f"\nStopped watching '{args.name}'")
                return 0

            if sub == "stop":
                entry = _WATCHER_REGISTRY.pop(args.name, None)
                if entry is None:
                    raise AxonCLIError(f"Watch session '{args.name}' not found")
                watcher, reloader = entry
                watcher.stop()
                print(f"Stopped watching '{args.name}'")
                return 0

            raise AxonCLIError(f"Unknown watch subcommand: {sub}")

        if args.command == "metrics":
            sub = args.metrics_command
            collector = MetricsCollector()

            if sub == "show":
                exporter = MetricsExporter(collector)
                if args.json:
                    print(exporter.to_json())
                else:
                    print(exporter.to_text())
                return 0

            if sub == "export":
                exporter = MetricsExporter(collector)
                output_path = Path(args.output)
                exporter.export_to_file(output_path, format=args.format)
                print(f"Metrics exported to {output_path}")
                return 0

            if sub == "reset":
                reset_metrics()
                print("Metrics reset")
                return 0

            raise AxonCLIError(f"Unknown metrics subcommand: {sub}")

        if args.command == "secret":
            from axon.secret_manager import FileSecretManager, get_default_secret_manager

            sub = args.secret_command
            manager = get_default_secret_manager()
            file_mgr = None
            if getattr(args, "file", None):
                file_mgr = FileSecretManager(args.file)

            if sub == "list":
                keys = (file_mgr or manager).list_keys()
                if not keys:
                    print("No secrets found")
                    return 0
                for key in sorted(keys):
                    print(key)
                return 0

            if sub == "get":
                value = (file_mgr or manager).get(args.key)
                if value is None:
                    raise AxonCLIError(f"Secret '{args.key}' not found")
                if args.reveal:
                    print(value)
                else:
                    print("***REDACTED***")
                return 0

            if sub == "set":
                target = file_mgr or manager
                target.set(args.key, args.value)
                print(f"Secret '{args.key}' set")
                return 0

            if sub == "delete":
                target = file_mgr or manager
                existed = target.delete(args.key)
                if existed:
                    print(f"Secret '{args.key}' deleted")
                else:
                    print(f"Secret '{args.key}' not found")
                return 0

            if sub == "audit":
                entries = manager.audit_log.to_dict_list(key=getattr(args, "key", None), limit=50)
                if not entries:
                    print("No audit entries")
                    return 0
                import json
                for entry in entries:
                    print(json.dumps(entry))
                return 0

            raise AxonCLIError(f"Unknown secret subcommand: {sub}")

        if args.command == "eval":
            from axon.eval_harness import EvalHarness
            harness = EvalHarness(
                iterations=args.iterations,
                baseline_path=Path(args.baseline) if args.baseline else None,
            )
            report = harness.run()
            if args.json:
                print(report.to_json())
            else:
                status = "PASS" if report.overall_passed else "FAIL"
                print(f"AXON eval: {status} ({len(report.benchmarks)} benchmarks, {report.total_time_ms:.1f}ms total)")
                for b in report.benchmarks:
                    mark = "✓" if b.passed else "✗"
                    print(f"  {mark} {b.name}: {b.avg_ms:.2f}ms (threshold: {b.threshold_ms:.2f}ms)")
            return 0 if report.overall_passed else 1

        if args.command == "add":
            from axon.package_manager import PackageManager, PackageManagerError
            manager = PackageManager()
            try:
                manifest = manager.add(args.source, branch=args.branch)
                print(f"Installed '{manifest.name}' v{manifest.version}")
                if manifest.agents:
                    print(f"  Agents: {', '.join(manifest.agents)}")
                if manifest.tools:
                    print(f"  Tools: {', '.join(manifest.tools)}")
                return 0
            except PackageManagerError as e:
                raise AxonCLIError(str(e))

        if args.command == "remove":
            from axon.package_manager import PackageManager
            manager = PackageManager()
            if manager.remove(args.name):
                print(f"Removed package '{args.name}'")
                return 0
            raise AxonCLIError(f"Package '{args.name}' not found")

        if args.command == "deploy":
            from axon.package_manager import PackageManager, PackageManagerError
            # Build Docker image
            image_tag = args.image_tag or f"axon-app:{args.name}"
            build_cmd = [
                "docker", "build", "-t", image_tag, "."
            ]
            if args.file:
                build_cmd = [
                    "docker", "build", "-t", image_tag, "-f", args.file, "."
                ]
            print(f"Building Docker image '{image_tag}'...")
            try:
                subprocess.run(build_cmd, check=True)
            except FileNotFoundError:
                raise AxonCLIError("docker is not installed. Install docker to use 'axon deploy'.")
            except subprocess.CalledProcessError as e:
                raise AxonCLIError(f"docker build failed: {e}")

            if args.target == "docker":
                print(f"Built image: {image_tag}")
                return 0

            if args.target == "fly":
                print("Deploying to Fly.io...")
                fly_cmd = ["fly", "deploy", "--image", image_tag]
                try:
                    subprocess.run(fly_cmd, check=True)
                except FileNotFoundError:
                    raise AxonCLIError("flyctl is not installed. Install flyctl to deploy to Fly.io.")
                except subprocess.CalledProcessError as e:
                    raise AxonCLIError(f"fly deploy failed: {e}")
                print("Deployed to Fly.io")
                return 0

            raise AxonCLIError(f"Unknown deploy target: {args.target}")

        if args.command == "debug":
            from axon.debugger import Debugger
            trace_path = Path(args.trace)
            if not trace_path.exists():
                raise AxonCLIError(f"Trace file not found: {args.trace}")
            debugger = Debugger(trace_path)
            if args.non_interactive:
                # Print summary and first few events
                print(debugger.session.format_summary())
                for i in range(min(5, debugger.session.total)):
                    debugger.session.goto(i)
                    print(debugger.session.format_current())
                    print()
                return 0
            debugger.run_interactive()
            return 0

        if args.command == "profile":
            from axon.profiler import profile_trace
            trace_path = Path(args.trace)
            if not trace_path.exists():
                raise AxonCLIError(f"Trace file not found: {args.trace}")
            report = profile_trace(trace_path)
            if args.json:
                import json
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print(f"AXON Profile: {report.overall_ms:.1f}ms overall, {report.total_events} events")
                for name, p in report.agents.items():
                    act_avg = p.act_total_ms / p.act_calls if p.act_calls else 0
                    print(f"  {name}: {p.total_ms:.1f}ms, {p.event_count} events, {p.act_calls} acts (avg {act_avg:.1f}ms)")
                    if p.think_tokens:
                        print(f"    think tokens: {p.think_tokens}")
                    if p.method_breakdown:
                        for method, ms in p.method_breakdown.items():
                            print(f"    method '{method}': {ms:.1f}ms")
            return 0

        parser.print_help()
        return 2
    except (AxonCLIError, AxonValidationError, ConfigError, ProjectInitError, PrecommitError, TraceFormatError, FileNotFoundError, IsADirectoryError, SyntaxError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _make_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="axon",
        description="AXON Phase 1 compiler CLI",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    version = subcommands.add_parser(
        "version",
        help="print AXON version information",
    )
    version.add_argument(
        "--json",
        action="store_true",
        help="print version information as JSON",
    )

    info = subcommands.add_parser(
        "info",
        help="print AXON environment and capability information",
    )
    info.add_argument(
        "--json",
        action="store_true",
        help="print AXON environment information as JSON",
    )
    info.add_argument(
        "--path",
        default=".",
        help="project path used when discovering axon.toml; defaults to the current directory",
    )
    info.add_argument(
        "--config",
        help="explicit axon.toml path to report if present",
    )

    project_info = subcommands.add_parser(
        "project-info",
        help="summarize safe AXON project/workspace metadata",
    )
    project_info.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    project_info.add_argument(
        "--json",
        action="store_true",
        help="print project metadata as JSON",
    )

    foundation_audit = subcommands.add_parser(
        "foundation-audit",
        help="audit the current Phase 1 compiler/tooling foundation",
    )
    foundation_audit.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to audit; defaults to the current directory",
    )
    foundation_audit.add_argument(
        "--json",
        action="store_true",
        help="print the foundation audit report as JSON",
    )

    handoff = subcommands.add_parser(
        "handoff",
        help="print or write a release handoff checklist",
    )
    handoff.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory for the checklist; defaults to the current directory",
    )
    handoff.add_argument(
        "--full",
        action="store_true",
        help="include full release-quality commands such as smoke-enabled project checks",
    )
    handoff.add_argument(
        "--output",
        help="write the checklist to this file instead of stdout",
    )
    handoff.add_argument(
        "--json",
        action="store_true",
        help="print or write the handoff checklist as JSON",
    )

    release_notes = subcommands.add_parser(
        "release-notes",
        aliases=["changelog"],
        help="generate Markdown or JSON release notes for an AXON project",
    )
    release_notes.add_argument(
        "--version",
        help="release version to display; defaults to the installed AXON version",
    )
    release_notes.add_argument(
        "--date",
        help="release date in YYYY-MM-DD format; defaults to today",
    )
    release_notes.add_argument(
        "--path",
        default=".",
        help="project path used for corpus discovery; defaults to the current directory",
    )
    release_notes.add_argument(
        "--change",
        action="append",
        default=[],
        help="release change bullet; may be provided multiple times",
    )
    release_notes.add_argument(
        "--tests",
        action="append",
        default=[],
        help="validation or test evidence bullet; may be provided multiple times",
    )
    release_notes.add_argument(
        "--output",
        help="write release notes to this file instead of stdout",
    )
    release_notes.add_argument(
        "--json",
        action="store_true",
        help="print or write release notes as JSON",
    )

    release_bundle_manifest = subcommands.add_parser(
        "release-bundle-manifest",
        help="print or write a release bundle manifest for handoff artifacts",
    )
    release_bundle_manifest.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    release_bundle_manifest.add_argument(
        "--output",
        help="write the manifest to this file instead of stdout",
    )
    release_bundle_manifest.add_argument(
        "--format",
        choices=["json", "markdown"],
        default=None,
        help="output file format; inferred from suffix when omitted",
    )
    release_bundle_manifest.add_argument(
        "--json",
        action="store_true",
        help="print or write the manifest as JSON",
    )

    release_artifacts = subcommands.add_parser(
        "release-artifacts",
        help="write the standard release handoff artifacts into an output directory",
    )
    release_artifacts.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    release_artifacts.add_argument(
        "--output-dir",
        default="release-artifacts",
        help="directory where release artifacts will be written",
    )
    release_artifacts.add_argument(
        "--version",
        help="release version to include in release notes",
    )
    release_artifacts.add_argument(
        "--date",
        help="release date in YYYY-MM-DD format for release notes",
    )
    release_artifacts.add_argument(
        "--change",
        action="append",
        default=[],
        help="release change bullet; may be provided multiple times",
    )
    release_artifacts.add_argument(
        "--tests",
        action="append",
        default=[],
        help="validation or test evidence bullet; may be provided multiple times",
    )
    release_artifacts.add_argument(
        "--skip-corpus",
        action="store_true",
        help="skip runtime-governance corpus execution for faster artifact generation",
    )
    release_artifacts.add_argument(
        "--json",
        action="store_true",
        help="print the generated artifact report as JSON",
    )

    release_artifacts_check = subcommands.add_parser(
        "release-artifacts-check",
        aliases=["release-artifact-consistency"],
        help="check that standard release artifact names are consistent across source and docs",
    )
    release_artifacts_check.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    release_artifacts_check.add_argument(
        "--json",
        action="store_true",
        help="print the consistency report as JSON",
    )

    task_template = subcommands.add_parser(
        "task-template",
        help="print or write a self-contained AXON task ticket template",
    )
    task_template.add_argument(
        "--number",
        type=int,
        help="optional task number used in the ticket heading",
    )
    task_template.add_argument(
        "--title",
        default="Untitled AXON Task",
        help="task title used in the ticket heading",
    )
    task_template.add_argument(
        "--module",
        help="suggested source module or area for this task",
    )
    task_template.add_argument(
        "--output",
        help="write the template to this file instead of stdout",
    )
    task_template.add_argument(
        "--json",
        action="store_true",
        help="print or write the task ticket template as JSON",
    )

    runtime_rfc_template = subcommands.add_parser(
        "runtime-rfc-template",
        help="print or write a runtime design RFC template",
    )
    runtime_rfc_template.add_argument(
        "--number",
        type=int,
        help="optional runtime RFC number used in the heading",
    )
    runtime_rfc_template.add_argument(
        "--title",
        default="Untitled AXON Runtime RFC",
        help="runtime RFC title used in the heading",
    )
    runtime_rfc_template.add_argument(
        "--owner",
        default="TBD",
        help="runtime RFC owner displayed in the template",
    )
    runtime_rfc_template.add_argument(
        "--status",
        default="Draft",
        help="runtime RFC status displayed in the template",
    )
    runtime_rfc_template.add_argument(
        "--output",
        help="write the template to this file instead of stdout",
    )
    runtime_rfc_template.add_argument(
        "--json",
        action="store_true",
        help="print or write the runtime RFC template as JSON",
    )

    runtime_plan = subcommands.add_parser(
        "runtime-plan",
        help="summarize a validated, non-executing runtime plan for an AXON file",
    )
    runtime_plan.add_argument("source", help="path to the input .ax file")
    runtime_plan.add_argument(
        "--json",
        action="store_true",
        help="print the runtime plan as JSON",
    )
    runtime_plan.add_argument(
        "--write",
        help="write the stable runtime-plan JSON snapshot to this file",
    )
    runtime_plan.add_argument(
        "--check",
        help="compare the current runtime-plan JSON snapshot against this file",
    )
    runtime_plan.add_argument(
        "--root",
        default=".",
        help="project root used to normalize source_path in --write/--check snapshots",
    )

    runtime_plan_corpus = subcommands.add_parser(
        "runtime-plan-corpus",
        help="check runtime-plan snapshots and disabled capabilities across an AXON example corpus",
    )
    runtime_plan_corpus.add_argument(
        "path",
        nargs="?",
        default=".",
        help="project root to inspect; defaults to the current directory",
    )
    runtime_plan_corpus.add_argument(
        "--examples-dir",
        default="examples",
        help="directory containing .ax files, relative to the project root unless absolute",
    )
    runtime_plan_corpus.add_argument(
        "--snapshot-dir",
        default="tests/snapshots/runtime_plan/examples",
        help="directory containing runtime-plan snapshots, relative to the project root unless absolute",
    )
    runtime_plan_corpus.add_argument(
        "--allow-missing-snapshots",
        action="store_true",
        help="treat missing runtime-plan snapshots as warnings instead of errors",
    )
    runtime_plan_corpus.add_argument(
        "--json",
        action="store_true",
        help="print the corpus report as JSON",
    )

    runtime_plan_review = subcommands.add_parser(
        "runtime-plan-review",
        help="print or write a reviewer checklist for runtime-plan and runtime-boundary changes",
    )
    runtime_plan_review.add_argument(
        "--change",
        default="runtime-plan-adjacent change",
        help="short description of the change under review",
    )
    runtime_plan_review.add_argument(
        "--output",
        help="write the checklist to this file instead of stdout",
    )
    runtime_plan_review.add_argument(
        "--json",
        action="store_true",
        help="print or write the checklist as JSON",
    )

    runtime_plan_review_check = subcommands.add_parser(
        "runtime-plan-review-check",
        help="check runtime-plan review docs, RFC alignment, and corpus evidence",
    )
    runtime_plan_review_check.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    runtime_plan_review_check.add_argument(
        "--examples-dir",
        default="examples",
        help="directory containing .ax files, relative to the project root unless absolute",
    )
    runtime_plan_review_check.add_argument(
        "--snapshot-dir",
        default="tests/snapshots/runtime_plan/examples",
        help="directory containing runtime-plan snapshots, relative to the project root unless absolute",
    )
    runtime_plan_review_check.add_argument(
        "--skip-corpus",
        action="store_true",
        help="skip runtime-plan-corpus execution and check docs/checklist consistency only",
    )
    runtime_plan_review_check.add_argument(
        "--json",
        action="store_true",
        help="print the consistency report as JSON",
    )

    runtime_governance = subcommands.add_parser(
        "runtime-governance",
        help="run the runtime governance quality gate for release evidence",
    )
    runtime_governance.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    runtime_governance.add_argument(
        "--examples-dir",
        default="examples",
        help="directory containing .ax files, relative to the project root unless absolute",
    )
    runtime_governance.add_argument(
        "--snapshot-dir",
        default="tests/snapshots/runtime_plan/examples",
        help="directory containing runtime-plan snapshots, relative to the project root unless absolute",
    )
    runtime_governance.add_argument(
        "--skip-corpus",
        action="store_true",
        help="skip runtime-plan-corpus execution for a faster docs/governance check",
    )
    runtime_governance.add_argument(
        "--json",
        action="store_true",
        help="print the governance report as JSON",
    )

    runtime_governance_evidence = subcommands.add_parser(
        "runtime-governance-evidence",
        help="write or print runtime governance evidence for release handoff",
    )
    runtime_governance_evidence.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    runtime_governance_evidence.add_argument(
        "--examples-dir",
        default="examples",
        help="directory containing .ax files, relative to the project root unless absolute",
    )
    runtime_governance_evidence.add_argument(
        "--snapshot-dir",
        default="tests/snapshots/runtime_plan/examples",
        help="directory containing runtime-plan snapshots, relative to the project root unless absolute",
    )
    runtime_governance_evidence.add_argument(
        "--skip-corpus",
        action="store_true",
        help="skip runtime-plan-corpus execution for a faster governance evidence check",
    )
    runtime_governance_evidence.add_argument(
        "--output",
        help="write the evidence artifact to this file instead of stdout",
    )
    runtime_governance_evidence.add_argument(
        "--format",
        choices=["json", "markdown"],
        default=None,
        help="output file format; inferred from suffix when omitted",
    )
    runtime_governance_evidence.add_argument(
        "--json",
        action="store_true",
        help="print or write evidence as JSON",
    )

    runtime_governance_gate = subcommands.add_parser(
        "runtime-governance-gate",
        help="alias for runtime-governance",
    )
    runtime_governance_gate.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to inspect; defaults to the current directory",
    )
    runtime_governance_gate.add_argument(
        "--examples-dir",
        default="examples",
        help="directory containing .ax files, relative to the project root unless absolute",
    )
    runtime_governance_gate.add_argument(
        "--snapshot-dir",
        default="tests/snapshots/runtime_plan/examples",
        help="directory containing runtime-plan snapshots, relative to the project root unless absolute",
    )
    runtime_governance_gate.add_argument(
        "--skip-corpus",
        action="store_true",
        help="skip runtime-plan-corpus execution for a faster docs/governance check",
    )
    runtime_governance_gate.add_argument(
        "--json",
        action="store_true",
        help="print the governance report as JSON",
    )

    new = subcommands.add_parser(
        "new",
        help="create a new AXON project skeleton",
    )
    new.add_argument("path", help="directory to create for the new AXON project")
    new.add_argument(
        "--force",
        action="store_true",
        help="allow adding starter files to a non-empty directory and overwrite AXON starter files",
    )

    init = subcommands.add_parser(
        "init",
        help="initialize an AXON project skeleton in an existing directory",
    )
    init.add_argument(
        "path",
        nargs="?",
        default=".",
        help="directory to initialize; defaults to the current directory",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="overwrite AXON starter files if they already exist",
    )



    precommit = subcommands.add_parser(
        "precommit",
        help="print, install, check, or run the AXON Git pre-commit hook",
    )
    precommit.add_argument(
        "action",
        nargs="?",
        default="print",
        choices=["print", "install", "check", "run"],
        help="pre-commit action to perform; defaults to printing the hook template",
    )
    precommit.add_argument(
        "--path",
        default=".",
        help="AXON project path; defaults to the current directory",
    )
    precommit.add_argument(
        "--hook-path",
        help="explicit hook path for install/check, useful for tests or custom Git layouts",
    )
    precommit.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing hook when installing",
    )
    precommit.add_argument(
        "--full",
        action="store_true",
        help="include smoke tests in the project quality gate when running checks",
    )
    precommit.add_argument(
        "--json",
        action="store_true",
        help="print install/check/run output as JSON",
    )

    deps = subcommands.add_parser(
        "deps",
        aliases=["dependency-audit"],
        help="audit dependency and optional-extra boundaries",
    )
    deps.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to audit; defaults to the current directory",
    )
    deps.add_argument(
        "--json",
        action="store_true",
        help="print dependency audit report as JSON",
    )

    hygiene = subcommands.add_parser(
        "hygiene",
        aliases=["repo-hygiene"],
        help="audit repository hygiene and .gitignore safety rules",
    )
    hygiene.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to audit; defaults to the current directory",
    )
    hygiene.add_argument(
        "--json",
        action="store_true",
        help="print repository hygiene report as JSON",
    )
    hygiene.add_argument(
        "--write-gitignore",
        action="store_true",
        help="write the default AXON .gitignore template instead of auditing",
    )
    hygiene.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing .gitignore when used with --write-gitignore",
    )

    config = subcommands.add_parser(
        "config",
        help="inspect axon.toml provider configuration without exposing secrets",
    )
    config.add_argument(
        "action",
        nargs="?",
        choices=["show"],
        default="show",
        help="configuration action to run; currently only 'show' is supported",
    )
    config.add_argument(
        "--config",
        help="path to axon.toml; defaults to searching from the current directory",
    )
    config.add_argument(
        "--json",
        action="store_true",
        help="print safe redacted config as JSON",
    )
    config.add_argument(
        "--resolve-env",
        action="store_true",
        help="resolve ${ENV_VAR} placeholders before displaying; secret-looking fields remain redacted",
    )

    syntax_cmd = subcommands.add_parser(
        "syntax",
        help="parse an AXON .ax file and show rich syntax diagnostics",
    )
    syntax_cmd.add_argument("source", help="path to the input .ax file")
    syntax_cmd.add_argument(
        "--json",
        action="store_true",
        help="print syntax result as JSON",
    )

    validate_cmd = subcommands.add_parser(
        "validate",
        help="parse and statically validate an AXON .ax file",
    )
    validate_cmd.add_argument("source", help="path to the input .ax file")
    validate_cmd.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="return a non-zero exit code when warnings are present",
    )
    validate_cmd.add_argument(
        "--json",
        action="store_true",
        help="print diagnostics as JSON",
    )

    type_check_cmd = subcommands.add_parser(
        "type-check",
        help="type check an AXON .ax file",
    )
    type_check_cmd.add_argument("source", help="path to the input .ax file")
    type_check_cmd.add_argument(
        "--json",
        action="store_true",
        help="print type diagnostics as JSON",
    )

    token_budget_cmd = subcommands.add_parser(
        "token-budget",
        help="check token budgets for prompt templates in an AXON .ax file",
    )
    token_budget_cmd.add_argument("source", help="path to the input .ax file")
    token_budget_cmd.add_argument(
        "--json",
        action="store_true",
        help="print token budget diagnostics as JSON",
    )

    lsp_cmd = subcommands.add_parser(
        "lsp",
        help="run the Language Server Protocol server for AXON IDE integration",
    )
    lsp_cmd.add_argument(
        "--stdio",
        action="store_true",
        help="use stdin/stdout for LSP communication (default)",
    )

    docs_cmd = subcommands.add_parser(
        "docs",
        help="generate Markdown documentation from an AXON .ax file",
    )
    docs_cmd.add_argument("source", help="path to the input .ax file")
    docs_cmd.add_argument("output", help="path to write the Markdown documentation")


    ast_cmd = subcommands.add_parser(
        "ast",
        help="print, write, or check a stable JSON AST snapshot for an AXON file",
    )
    ast_cmd.add_argument("source", help="path to the input .ax file")
    ast_cmd.add_argument(
        "--no-lines",
        action="store_true",
        help="omit source line numbers from the snapshot",
    )
    ast_cmd.add_argument(
        "--write",
        help="write the AST snapshot to this JSON file",
    )
    ast_cmd.add_argument(
        "--check",
        help="compare the current AST snapshot against this JSON file",
    )

    format_cmd = subcommands.add_parser(
        "format",
        help="print, check, or rewrite canonical AXON source formatting",
    )
    format_cmd.add_argument("source", help="path to the input .ax file")
    format_cmd.add_argument(
        "--check",
        action="store_true",
        help="return non-zero when the source is not canonically formatted",
    )
    format_cmd.add_argument(
        "--write",
        action="store_true",
        help="rewrite the source file in canonical AXON formatting",
    )

    check_project_cmd = subcommands.add_parser(
        "check-project",
        aliases=["doctor"],
        help="run project-level AXON quality checks",
    )
    check_project_cmd.add_argument(
        "path",
        nargs="?",
        default=".",
        help="AXON project directory to check; defaults to the current directory",
    )
    check_project_cmd.add_argument(
        "--json",
        action="store_true",
        help="print the project check report as JSON",
    )
    check_project_cmd.add_argument(
        "--no-smoke",
        action="store_true",
        help="skip generated-server smoke tests",
    )
    check_project_cmd.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="treat validation warnings and project warnings as failures",
    )
    check_project_cmd.add_argument(
        "--snapshot-dir",
        help="directory containing AST snapshots to compare against",
    )
    check_project_cmd.add_argument(
        "--require-snapshots",
        action="store_true",
        help="fail when an AXON source file has no matching AST snapshot",
    )

    trace_preview = subcommands.add_parser(
        "trace-preview",
        help="statically extract AEL trace events from AXON agent methods",
    )
    trace_preview.add_argument("source", help="path to the input .ax file")
    trace_preview.add_argument(
        "--json",
        action="store_true",
        help="print the trace preview as a JSON array",
    )
    trace_preview.add_argument(
        "--jsonl",
        action="store_true",
        help="print the trace preview as JSONL trace events",
    )

    trace_read = subcommands.add_parser(
        "trace-read",
        aliases=["trace-log"],
        help="read, validate, filter, and summarize an AEL JSONL trace log",
    )
    trace_read.add_argument("trace_file", help="path to an AEL JSONL trace file")
    trace_read.add_argument(
        "--type",
        choices=["think", "act", "observe", "store"],
        help="only include events of this AEL event type",
    )
    trace_read.add_argument(
        "--agent",
        help="only include events from this agent name",
    )
    trace_read.add_argument(
        "--events",
        action="store_true",
        help="include formatted event lines after the summary",
    )
    trace_read.add_argument(
        "--json",
        action="store_true",
        help="print summary and filtered events as JSON",
    )
    trace_read.add_argument(
        "--jsonl",
        action="store_true",
        help="print filtered events as JSONL",
    )

    smoke = subcommands.add_parser(
        "smoke",
        help="generate and structurally smoke-test a FastMCP server without requiring fastmcp",
    )
    smoke.add_argument("source", help="path to the input .ax file")
    smoke.add_argument(
        "--name",
        help="fallback FastMCP server name when the source has no agent declaration",
    )
    smoke.add_argument(
        "--json",
        action="store_true",
        help="print the smoke-test report as JSON",
    )

    build = subcommands.add_parser(
        "build",
        help="generate a FastMCP Python server from an AXON .ax file",
    )
    build.add_argument("source", help="path to the input .ax file")
    build.add_argument(
        "-o",
        "--output",
        help="path to write the generated Python server; defaults to <source>_server.py",
    )
    build.add_argument(
        "--name",
        help="fallback FastMCP server name when the source has no agent declaration",
    )
    build.add_argument(
        "--stdout",
        action="store_true",
        help="print generated Python code instead of writing a file",
    )
    build.add_argument(
        "--config",
        help="path to axon.toml used for provider defaults",
    )

    compile_cmd = subcommands.add_parser(
        "compile",
        help="compile an AXON source file to Intermediate Representation (IR)",
    )
    compile_cmd.add_argument("source", help="path to the input .ax file")
    compile_cmd.add_argument(
        "--target",
        choices=["ir", "ts", "typescript", "governance"],
        default="ir",
        help="compilation target: ir (default), ts, typescript, governance (AgentOps Mesh)",
    )
    compile_cmd.add_argument(
        "--ir",
        action="store_true",
        dest="emit_ir",
        help="emit AXON IR as JSON to stdout (default: validate only)",
    )
    compile_cmd.add_argument(
        "--output",
        "-o",
        dest="output",
        help="write compiled output to a file",
    )

    govern_cmd = subcommands.add_parser(
        "govern",
        help="compile an AXON source file into an AgentOps Mesh governance submission",
    )
    govern_cmd.add_argument("source", help="path to the input .ax file")
    govern_cmd.add_argument(
        "--mesh-url",
        dest="mesh_url",
        default=None,
        help="AgentOps Mesh API URL to submit governance request to (e.g. http://localhost:8000)",
    )
    govern_cmd.add_argument(
        "--output",
        "-o",
        dest="output",
        default=None,
        help="write governance submission (or result if --mesh-url) to a file",
    )
    govern_cmd.add_argument(
        "--business-owner",
        dest="business_owner",
        default="TBD",
        help="business owner for the governance submission",
    )
    govern_cmd.add_argument(
        "--technical-owner",
        dest="technical_owner",
        default="TBD",
        help="technical owner for the governance submission",
    )
    govern_cmd.add_argument(
        "--target-environment",
        dest="target_environment",
        choices=["sandbox", "pilot", "production"],
        default="sandbox",
        help="target environment for the governance submission (default: sandbox)",
    )

    run_cmd = subcommands.add_parser(
        "run",
        help="execute an AXON source file (default: mock; use --no-mock for real providers)",
    )
    run_cmd.add_argument("source", help="path to the input .ax file")
    run_cmd.add_argument(
        "--arg",
        dest="args",
        action="append",
        default=[],
        help="pass a key=value argument to the agent's run() method (repeatable)",
    )
    run_cmd.add_argument(
        "--trace",
        dest="trace_output",
        help="write AEL trace events to this JSONL file",
    )
    run_cmd.add_argument(
        "--memory",
        dest="memory_path",
        help="path to a JSON memory file to load and optionally checkpoint",
    )
    run_cmd.add_argument(
        "--checkpoint",
        action="store_true",
        help="persist agent memory to the --memory file after execution",
    )
    run_cmd.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="use the mock provider (default: True, safe for testing without API keys)",
    )
    run_cmd.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="enable real provider calls (requires API keys and openai package)",
    )
    run_cmd.add_argument(
        "--live",
        dest="mock",
        action="store_false",
        help="alias for --no-mock: enable real provider calls",
    )
    run_cmd.add_argument(
        "--provider",
        dest="provider_name",
        default=None,
        choices=["openai", "anthropic", "mock"],
        help="override the provider for real provider calls (used with --no-mock)",
    )
    run_cmd.add_argument(
        "--flow",
        dest="flow_name",
        default=None,
        help="execute a named flow instead of an agent run() method",
    )
    run_cmd.add_argument(
        "--agent",
        dest="agent_name",
        default=None,
        help="execute a specific agent by name instead of the first agent",
    )
    run_cmd.add_argument(
        "--replay",
        dest="replay_path",
        default=None,
        help="replay a recorded trace JSONL file instead of executing live tools/providers",
    )
    run_cmd.add_argument(
        "--stream",
        action="store_true",
        help="execute with async streaming (yields response chunks as they arrive)",
    )
    run_cmd.add_argument(
        "--sandbox-timeout",
        type=int,
        default=None,
        help="sandbox tool dispatch timeout in milliseconds (default: 5000, or axon.toml value)",
    )
    run_cmd.add_argument(
        "--sandbox-max-depth",
        type=int,
        default=None,
        help="maximum expression evaluation depth per tool dispatch (default: 100, or axon.toml value)",
    )
    run_cmd.add_argument(
        "--sandbox-denied",
        dest="sandbox_denied_tools",
        action="append",
        default=[],
        help="deny specific tool names from executing (repeatable)",
    )
    run_cmd.add_argument(
        "--metrics",
        action="store_true",
        help="print runtime metrics (provider calls, tool dispatches, latencies) after execution",
    )
    run_cmd.add_argument(
        "--strict-types",
        action="store_true",
        help="enable runtime type validation of tool return values against declared types",
    )
    run_cmd.add_argument(
        "--via-ir",
        action="store_true",
        help="compile .ax source through IR before execution (proves IR is the contract)",
    )
    run_cmd.add_argument(
        "--json",
        action="store_true",
        help="print output as JSON",
    )

    agent_cmd = subcommands.add_parser(
        "agent",
        help="manage AXON agent lifecycle (spawn, pause, resume, terminate)",
    )
    agent_sub = agent_cmd.add_subparsers(dest="agent_command", required=True)

    agent_spawn = agent_sub.add_parser("spawn", help="spawn a new agent instance")
    agent_spawn.add_argument("source", help="path to the input .ax file")
    agent_spawn.add_argument(
        "--name",
        required=True,
        help="unique name for the agent instance",
    )
    agent_spawn.add_argument(
        "--arg",
        dest="args",
        action="append",
        default=[],
        help="pass a key=value argument to the agent's run() method (repeatable)",
    )
    agent_spawn.add_argument(
        "--trace",
        dest="trace",
        help="write AEL trace events to this JSONL file",
    )
    agent_spawn.add_argument(
        "--memory",
        dest="memory",
        help="path to a JSON memory file to load and optionally checkpoint",
    )
    agent_spawn.add_argument(
        "--checkpoint",
        action="store_true",
        help="persist agent memory to the --memory file after execution",
    )
    agent_spawn.add_argument(
        "--stream",
        action="store_true",
        help="enable streaming mode for provider responses",
    )
    agent_spawn.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="use the mock provider (default: True)",
    )
    agent_spawn.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="enable real provider calls",
    )
    agent_spawn.add_argument(
        "--live",
        dest="mock",
        action="store_false",
        help="alias for --no-mock: enable real provider calls",
    )
    agent_spawn.add_argument(
        "--provider",
        dest="provider_name",
        default=None,
        choices=["openai", "anthropic", "mock"],
        help="override the provider for real provider calls",
    )

    agent_pause = agent_sub.add_parser("pause", help="pause a running agent")
    agent_pause.add_argument("name", help="name of the agent instance")

    agent_resume = agent_sub.add_parser("resume", help="resume a paused agent")
    agent_resume.add_argument("name", help="name of the agent instance")

    agent_terminate = agent_sub.add_parser("terminate", help="terminate an agent")
    agent_terminate.add_argument("name", help="name of the agent instance")
    agent_terminate.add_argument(
        "--reason",
        default="user_request",
        help="reason for termination",
    )

    agent_status = agent_sub.add_parser("status", help="show agent status")
    agent_status.add_argument("name", help="name of the agent instance")
    agent_status.add_argument(
        "--json",
        action="store_true",
        help="print status as JSON",
    )

    agent_list = agent_sub.add_parser("list", help="list active agents")
    agent_list.add_argument(
        "--json",
        action="store_true",
        help="print list as JSON",
    )

    agent_checkpoint = agent_sub.add_parser("checkpoint", help="save a checkpoint of an agent")
    agent_checkpoint.add_argument("name", help="name of the agent instance")
    agent_checkpoint.add_argument(
        "--output",
        "-o",
        dest="output",
        help="path to write the checkpoint JSON (default: .axon_checkpoints/<name>_<timestamp>.json)",
    )

    agent_restore = agent_sub.add_parser("restore", help="restore an agent from a checkpoint")
    agent_restore.add_argument("name", help="name for the restored agent instance")
    agent_restore.add_argument(
        "--snapshot",
        required=True,
        help="path to a checkpoint JSON file",
    )
    agent_restore.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="use the mock provider (default: True)",
    )
    agent_restore.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="enable real provider calls",
    )
    agent_restore.add_argument(
        "--provider",
        dest="provider_name",
        default=None,
        choices=["openai", "anthropic", "mock"],
        help="override provider for the restored agent",
    )

    health = subcommands.add_parser(
        "health",
        help="check AXON runtime health status",
    )
    health.add_argument(
        "--json",
        action="store_true",
        help="print health check as JSON",
    )

    serve = subcommands.add_parser(
        "serve",
        help="build and run the generated FastMCP Python server",
    )
    serve.add_argument("source", help="path to the input .ax file")
    serve.add_argument(
        "-o",
        "--output",
        help="path to write the generated Python server; defaults to <source>_server.py",
    )
    serve.add_argument(
        "--name",
        help="fallback FastMCP server name when the source has no agent declaration",
    )
    serve.add_argument(
        "--config",
        help="path to axon.toml used for provider defaults",
    )
    serve.add_argument(
        "--dry-run",
        action="store_true",
        help="generate the server file but do not start it",
    )
    serve.add_argument(
        "--python",
        help="Python executable used to run the generated server; defaults to the current interpreter",
    )

    serve_api = subcommands.add_parser(
        "serve-api",
        help="start the AXON REST API server",
    )
    serve_api.add_argument(
        "--host",
        default="127.0.0.1",
        help="host to bind the API server (default: 127.0.0.1)",
    )
    serve_api.add_argument(
        "--port",
        type=int,
        default=8000,
        help="port to bind the API server (default: 8000)",
    )
    serve_api.add_argument(
        "--api-key",
        help="optional API key for authentication",
    )

    supervisor_cmd = subcommands.add_parser(
        "supervisor",
        help="manage a supervision tree for AXON agents",
    )
    supervisor_sub = supervisor_cmd.add_subparsers(dest="supervisor_command", required=True)

    sup_start = supervisor_sub.add_parser("start", help="start a supervisor group")
    sup_start.add_argument("--name", required=True, help="unique supervisor name")
    sup_start.add_argument(
        "--strategy",
        default="one_for_one",
        choices=["one_for_one", "one_for_all", "rest_for_one"],
        help="restart strategy when a child fails",
    )
    sup_start.add_argument(
        "--child",
        dest="children",
        action="append",
        default=[],
        help="child spec as source::name (repeatable)",
    )
    sup_start.add_argument(
        "--max-restarts",
        type=int,
        default=5,
        help="maximum restarts within max-seconds before shutdown",
    )
    sup_start.add_argument(
        "--max-seconds",
        type=int,
        default=60,
        help="time window for max-restarts",
    )
    sup_start.add_argument(
        "--poll-interval",
        type=int,
        default=2000,
        help="health poll interval in milliseconds",
    )
    sup_start.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="use the mock provider for children",
    )
    sup_start.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="enable real provider calls for children",
    )
    sup_start.add_argument(
        "--provider",
        dest="provider_name",
        default=None,
        choices=["openai", "anthropic", "mock"],
        help="override provider for children",
    )

    sup_stop = supervisor_sub.add_parser("stop", help="stop a supervisor group")
    sup_stop.add_argument("name", help="supervisor name")
    sup_stop.add_argument("--reason", default="user_request", help="shutdown reason")

    sup_status = supervisor_sub.add_parser("status", help="show supervisor status")
    sup_status.add_argument("name", help="supervisor name")
    sup_status.add_argument("--json", action="store_true", help="print status as JSON")

    watch_cmd = subcommands.add_parser(
        "watch",
        help="watch source files for changes and auto-reload agents",
    )
    watch_sub = watch_cmd.add_subparsers(dest="watch_command", required=True)

    watch_start = watch_sub.add_parser("start", help="watch an agent and reload on change")
    watch_start.add_argument("source", help="path to the input .ax file")
    watch_start.add_argument("--name", required=True, help="unique name for the agent instance")
    watch_start.add_argument(
        "--arg",
        dest="args",
        action="append",
        default=[],
        help="pass a key=value argument to the agent's run() method (repeatable)",
    )
    watch_start.add_argument(
        "--poll-interval",
        type=int,
        default=1000,
        help="file poll interval in milliseconds (default: 1000)",
    )
    watch_start.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="use the mock provider (default: True)",
    )
    watch_start.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="enable real provider calls",
    )
    watch_start.add_argument(
        "--provider",
        dest="provider_name",
        default=None,
        choices=["openai", "anthropic", "mock"],
        help="override provider for the agent",
    )

    watch_stop = watch_sub.add_parser("stop", help="stop a watch session")
    watch_stop.add_argument("name", help="watch session / agent name")

    metrics_cmd = subcommands.add_parser(
        "metrics",
        help="view and export AXON runtime metrics",
    )
    metrics_sub = metrics_cmd.add_subparsers(dest="metrics_command", required=True)

    metrics_show = metrics_sub.add_parser("show", help="display collected metrics")
    metrics_show.add_argument(
        "--json",
        action="store_true",
        help="print metrics as JSON",
    )

    metrics_export = metrics_sub.add_parser("export", help="export metrics to a file")
    metrics_export.add_argument(
        "--output",
        "-o",
        required=True,
        help="destination file path",
    )
    metrics_export.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="export format (default: json)",
    )

    metrics_reset = metrics_sub.add_parser("reset", help="reset the global metrics collector")

    # Eval / benchmark command
    eval_cmd = subcommands.add_parser(
        "eval",
        help="run built-in performance benchmarks with regression detection",
    )
    eval_cmd.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="number of iterations per benchmark (default: 5)",
    )
    eval_cmd.add_argument(
        "--baseline",
        help="path to a JSON baseline file for regression detection",
    )
    eval_cmd.add_argument(
        "--json",
        action="store_true",
        help="output results as JSON",
    )

    # Secret management command
    secret_cmd = subcommands.add_parser(
        "secret",
        help="manage secrets and credentials",
    )
    secret_sub = secret_cmd.add_subparsers(dest="secret_command", required=True)

    secret_list = secret_sub.add_parser("list", help="list secret keys (values redacted)")
    secret_list.add_argument(
        "--file",
        "-f",
        help="path to secrets file (JSON or .env) instead of env vars",
    )

    secret_get = secret_sub.add_parser("get", help="retrieve a secret value")
    secret_get.add_argument("key", help="secret key name")
    secret_get.add_argument(
        "--reveal",
        action="store_true",
        help="show the actual value (default: redacted)",
    )
    secret_get.add_argument(
        "--file",
        "-f",
        help="path to secrets file (JSON or .env)",
    )

    secret_set = secret_sub.add_parser("set", help="store a secret")
    secret_set.add_argument("key", help="secret key name")
    secret_set.add_argument("value", help="secret value")
    secret_set.add_argument(
        "--file",
        "-f",
        help="path to secrets file (JSON or .env) instead of env vars",
    )

    secret_delete = secret_sub.add_parser("delete", help="remove a secret")
    secret_delete.add_argument("key", help="secret key name")
    secret_delete.add_argument(
        "--file",
        "-f",
        help="path to secrets file (JSON or .env)",
    )

    secret_audit = secret_sub.add_parser("audit", help="view secret access audit log")
    secret_audit.add_argument(
        "--key",
        help="filter audit entries by key",
    )

    # Package management
    add_cmd = subcommands.add_parser(
        "add",
        help="install an AXON package from GitHub or a local path",
    )
    add_cmd.add_argument("source", help="GitHub repo (user/repo) or local path")
    add_cmd.add_argument(
        "--branch",
        help="git branch or tag to checkout (default: default branch)",
    )

    remove_cmd = subcommands.add_parser(
        "remove",
        help="remove an installed AXON package",
    )
    remove_cmd.add_argument("name", help="package name to remove")

    # Deploy command
    deploy_cmd = subcommands.add_parser(
        "deploy",
        help="build and deploy an AXON app as a Docker image or to cloud",
    )
    deploy_cmd.add_argument("name", help="application name (used for image tag)")
    deploy_cmd.add_argument(
        "--target",
        choices=["docker", "fly"],
        default="docker",
        help="deployment target (default: docker)",
    )
    deploy_cmd.add_argument(
        "--image-tag",
        help="Docker image tag (default: axon-app:<name>)",
    )
    deploy_cmd.add_argument(
        "--file",
        "-f",
        help="path to Dockerfile (default: ./Dockerfile)",
    )

    # Debug command
    debug_cmd = subcommands.add_parser(
        "debug",
        help="interactive AEL trace debugger",
    )
    debug_cmd.add_argument("trace", help="path to a JSONL trace file")
    debug_cmd.add_argument(
        "--non-interactive",
        action="store_true",
        help="print summary and first events without entering REPL",
    )

    # Profile command
    profile_cmd = subcommands.add_parser(
        "profile",
        help="profile an AEL trace for execution time breakdown",
    )
    profile_cmd.add_argument("trace", help="path to a JSONL trace file")
    profile_cmd.add_argument(
        "--json",
        action="store_true",
        help="output profile as JSON",
    )

    # CI template command
    ci_template_cmd = subcommands.add_parser(
        "ci-template",
        help="generate a CI/CD workflow file for AXON projects",
    )
    ci_template_cmd.add_argument(
        "--platform",
        choices=["github-actions", "gitlab-ci"],
        default="github-actions",
        help="CI platform to generate for (default: github-actions)",
    )
    ci_template_cmd.add_argument(
        "--output",
        "-o",
        default=None,
        help="write the workflow file to this path (default: stdout)",
    )
    ci_template_cmd.add_argument(
        "--mesh-url",
        dest="mesh_url",
        default=None,
        help="include a governance submission step to this AgentOps Mesh URL",
    )

    # Explain command
    explain_cmd = subcommands.add_parser(
        "explain",
        help="explain validation errors in plain English with fix suggestions",
    )
    explain_cmd.add_argument("source", help="path to the .ax file to explain")

    return parser


def _all_command_names(*, include_aliases: bool = True) -> list[str]:
    """Return the current argparse command surface for release documentation."""
    parser = _make_arg_parser()
    commands: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for command in action.choices:
                if include_aliases or command not in {"doctor", "trace-log", "changelog"}:
                    commands.add(command)
            break
    return sorted(commands)


def _parse_cli_arg_value(value: str) -> Any:
    """Parse a CLI argument value: try int, float, bool, then fallback to string."""
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    # Strip surrounding quotes if present
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def _default_output_path(source: Path) -> Path:
    return source.with_name(f"{source.stem}_server.py")


def _generate_ci_template(platform: str, mesh_url: str | None = None) -> str:
    """Generate a CI/CD workflow template for an AXON project."""
    if platform == "github-actions":
        lines = [
            "name: AXON CI",
            "",
            "on:",
            "  push:",
            "    branches: [main]",
            "  pull_request:",
            "    branches: [main]",
            "  workflow_dispatch:",
            "",
            "permissions:",
            "  contents: read",
            "",
            "jobs:",
            "  test:",
            "    name: Python ${{ matrix.python-version }}",
            "    runs-on: ubuntu-latest",
            "    strategy:",
            "      fail-fast: false",
            "      matrix:",
            "        python-version: [\"3.11\", \"3.12\"]",
            "",
            "    steps:",
            "      - name: Check out repository",
            "        uses: actions/checkout@v4",
            "",
            "      - name: Set up Python",
            "        uses: actions/setup-python@v5",
            "        with:",
            "          python-version: ${{ matrix.python-version }}",
            "          cache: pip",
            "",
            "      - name: Install AXON with development extras",
            "        run: |",
            "          python -m pip install --upgrade pip",
            "          python -m pip install -e \".[dev]\"",
            "",
            "      - name: Compile Python sources",
            "        run: python -m compileall -q src tests",
            "",
            "      - name: Audit dependency boundaries",
            "        run: axon deps .",
            "",
            "      - name: Audit repository hygiene",
            "        run: axon hygiene .",
            "",
            "      - name: Validate AXON sources",
            "        run: axon validate examples/hello.ax",
            "",
            "      - name: Type-check AXON sources",
            "        run: axon type-check examples/hello.ax",
            "",
            "      - name: Check formatting",
            "        run: |",
            "          axon format examples/hello.ax > /tmp/formatted.ax",
            "          axon format /tmp/formatted.ax --check",
            "",
            "      - name: Smoke test generated server",
            "        run: axon smoke examples/hello.ax",
            "",
            "      - name: Run pytest suite",
            "        run: python -m pytest",
            "",
        ]
        if mesh_url:
            lines.extend([
                "      - name: Submit governance request to AgentOps Mesh",
                f"        run: axon govern examples/hello.ax --mesh-url {mesh_url}",
                "        continue-on-error: true",
                "",
            ])
        return "\n".join(lines)

    if platform == "gitlab-ci":
        lines = [
            "stages:",
            "  - lint",
            "  - test",
            "  - governance",
            "",
            "variables:",
            "  PIP_CACHE_DIR: \"$CI_PROJECT_DIR/.pip-cache\"",
            "",
            "cache:",
            "  paths:",
            "    - .pip-cache/",
            "    - .pytest_cache/",
            "",
            "lint:",
            "  stage: lint",
            "  image: python:3.12",
            "  script:",
            "    - pip install -e \".[dev]\"",
            "    - axon deps .",
            "    - axon hygiene .",
            "    - axon validate examples/hello.ax",
            "    - axon type-check examples/hello.ax",
            "",
            "test:",
            "  stage: test",
            "  image: python:3.12",
            "  script:",
            "    - pip install -e \".[dev]\"",
            "    - python -m compileall -q src tests",
            "    - axon smoke examples/hello.ax",
            "    - python -m pytest",
            "",
        ]
        if mesh_url:
            lines.extend([
                "governance:",
                "  stage: governance",
                "  image: python:3.12",
                "  script:",
                "    - pip install -e \".[dev]\"",
                f"    - axon govern examples/hello.ax --mesh-url {mesh_url}",
                "  allow_failure: true",
                "",
            ])
        return "\n".join(lines)

    return f"# Unsupported platform: {platform}\n"


def _explain_diagnostics(errors: list, warnings: list, filename: str) -> str:
    """Explain validation diagnostics in plain English with fix suggestions."""
    lines = [f"=== AXON Explanation for {filename} ===", ""]

    if errors:
        lines.append(f"❌ {len(errors)} error(s):")
        lines.append("")
        for i, diag in enumerate(errors, 1):
            lines.append(f"  Error {i}: {diag.message}")
            if hasattr(diag, 'line') and diag.line:
                lines.append(f"    Location: line {diag.line}")
            if hasattr(diag, 'code') and diag.code:
                lines.append(f"    Code: {diag.code}")
            suggestion = _diagnostic_fix_suggestion(diag)
            if suggestion:
                lines.append(f"    Fix: {suggestion}")
            if hasattr(diag, 'hint') and diag.hint:
                lines.append(f"    Hint: {diag.hint}")
            lines.append("")

    if warnings:
        lines.append(f"⚠️  {len(warnings)} warning(s):")
        lines.append("")
        for i, diag in enumerate(warnings, 1):
            lines.append(f"  Warning {i}: {diag.message}")
            if hasattr(diag, 'line') and diag.line:
                lines.append(f"    Location: line {diag.line}")
            suggestion = _diagnostic_fix_suggestion(diag)
            if suggestion:
                lines.append(f"    Fix: {suggestion}")
            lines.append("")

    if not errors and warnings:
        lines.append("✅ No blocking errors. Warnings should be reviewed but won't prevent compilation.")
    elif errors:
        lines.append("❌ Fix the errors above before proceeding. Run `axon validate` to re-check.")

    return "\n".join(lines)


def _diagnostic_fix_suggestion(diag) -> str:
    """Generate a plain-English fix suggestion for a diagnostic."""
    code = getattr(diag, 'code', '') or ''
    msg = getattr(diag, 'message', '') or ''

    suggestions = {
        'tool-docstring': 'Add a /// docstring line inside the tool body, e.g.: /// "Does something useful."',
        'agent-missing-run': 'Add a `fn run(...)` method to the agent declaration. Every agent needs a run() entry point.',
        'duplicate-declaration': 'Rename one of the duplicate declarations. Each tool, agent, and type must have a unique name.',
        'unknown-type': 'Check the type spelling or add a `type` declaration for the custom type.',
        'type-mismatch': 'Ensure the return type matches the declared type. Check for Result<T, E> wrapping.',
        'missing-tool': 'Declare the tool before referencing it in the agent tools list, or remove it from the list.',
        'invalid-model': 'Use a valid model reference like @anthropic/claude-4, @openai/gpt-4, or @mock/model.',
        'empty-agent': 'Add at least one method to the agent, or add tools to the tools list.',
    }

    for key, suggestion in suggestions.items():
        if key in code or key in msg.lower():
            return suggestion

    if 'parse' in msg.lower():
        return "Check the syntax at the indicated line. Common issues: missing braces, unclosed strings, wrong keywords."
    if 'type' in msg.lower():
        return "Verify that all type references are declared and spelled correctly."
    if 'tool' in msg.lower():
        return "Ensure the tool is declared before use and has the correct signature."

    return "Review the AXON syntax reference with `axon syntax` for the correct declaration format."


if __name__ == "__main__":  # pragma: no cover - exercised through python -m axon
    raise SystemExit(main())
