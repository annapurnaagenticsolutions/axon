"""Corpus-level checks for non-executing AXON runtime plans.

This module verifies the Runtime RFC #001 boundary across a project corpus. It
parses and validates every example ``.ax`` file, builds a non-executing runtime
plan, compares runtime-plan snapshots, and confirms that all executable runtime
capabilities remain disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from axon.runtime_plan import DEFAULT_ENCODING, RuntimePlan, build_runtime_plan_from_file
from axon.runtime_plan_snapshot import check_runtime_plan_snapshot_file

EXECUTION_CAPABILITY_NAMES = [
    "method_execution",
    "provider_calls",
    "tool_dispatch",
    "memory_mutation",
    "rag_indexing",
    "rag_retrieval",
    "flow_execution",
    "trace_replay",
    "secret_resolution",
    "fastmcp_runtime_import",
]

ENABLED_CAPABILITY_NAMES = ["declaration_inspection"]


@dataclass(frozen=True)
class RuntimePlanCorpusItem:
    """Result for one AXON source file in a runtime-plan corpus check."""

    source_path: str
    snapshot_path: str
    counts: dict[str, int] = field(default_factory=dict)
    snapshot_exists: bool = False
    snapshot_matched: bool = False
    execution_boundary_ok: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "snapshot_path": self.snapshot_path,
            "counts": dict(self.counts),
            "snapshot_exists": self.snapshot_exists,
            "snapshot_matched": self.snapshot_matched,
            "execution_boundary_ok": self.execution_boundary_ok,
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class RuntimePlanCorpusReport:
    """Project-level runtime-plan corpus report."""

    root: str
    examples_dir: str
    snapshot_dir: str
    total_sources: int
    total_snapshots: int
    items: list[RuntimePlanCorpusItem]
    orphan_snapshots: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors and all(item.passed for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "examples_dir": self.examples_dir,
            "snapshot_dir": self.snapshot_dir,
            "total_sources": self.total_sources,
            "total_snapshots": self.total_snapshots,
            "passed": self.passed,
            "items": [item.to_dict() for item in self.items],
            "orphan_snapshots": list(self.orphan_snapshots),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def discover_runtime_plan_sources(examples_dir: str | Path) -> list[Path]:
    """Return sorted AXON example source files for corpus runtime-plan checks."""
    path = Path(examples_dir)
    if not path.exists():
        raise FileNotFoundError(f"examples directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"examples path is not a directory: {path}")
    return sorted(source for source in path.glob("*.ax") if source.is_file())


def expected_runtime_plan_snapshot_path(source_path: str | Path, snapshot_dir: str | Path) -> Path:
    """Return the expected runtime-plan snapshot path for one source file."""
    source = Path(source_path)
    return Path(snapshot_dir) / f"{source.stem}.runtime-plan.json"


def check_runtime_plan_corpus(
    root: str | Path = ".",
    *,
    examples_dir: str | Path = "examples",
    snapshot_dir: str | Path = "tests/snapshots/runtime_plan/examples",
    require_snapshots: bool = True,
) -> RuntimePlanCorpusReport:
    """Check runtime-plan snapshots and disabled capabilities across a corpus.

    This command is inspection-only. It does not execute AXON method bodies, call
    providers, dispatch tools, mutate memory, index/retrieve RAG data, execute
    flows, replay traces, resolve secrets, or import FastMCP.
    """
    root_path = Path(root)
    examples_path = _resolve_under_root(root_path, examples_dir)
    snapshots_path = _resolve_under_root(root_path, snapshot_dir)

    sources = discover_runtime_plan_sources(examples_path)
    snapshots = sorted(snapshots_path.glob("*.runtime-plan.json")) if snapshots_path.exists() else []

    items: list[RuntimePlanCorpusItem] = []
    report_errors: list[str] = []
    report_warnings: list[str] = []

    if not sources:
        report_errors.append(f"no .ax files found in examples directory: {examples_path}")

    for source in sources:
        snapshot = expected_runtime_plan_snapshot_path(source, snapshots_path)
        item_errors: list[str] = []
        item_warnings: list[str] = []
        counts: dict[str, int] = {}
        execution_boundary_ok = False

        try:
            plan = build_runtime_plan_from_file(source)
            counts = plan.counts()
            boundary_errors = runtime_plan_execution_boundary_errors(plan)
            execution_boundary_ok = not boundary_errors
            item_errors.extend(boundary_errors)
        except Exception as exc:  # pragma: no cover - defensive guard for CLI use
            item_errors.append(f"runtime plan failed: {exc}")

        snapshot_exists = snapshot.exists()
        snapshot_matched = False
        if snapshot_exists:
            result = check_runtime_plan_snapshot_file(source, snapshot, root=root_path)
            snapshot_matched = result.matched
            if not result.matched:
                item_errors.append(result.message)
        elif require_snapshots:
            item_errors.append(f"runtime-plan snapshot missing: {snapshot}")
        else:
            item_warnings.append(f"runtime-plan snapshot missing: {snapshot}")

        source_label = _relative_label(source, root_path)
        snapshot_label = _relative_label(snapshot, root_path)
        items.append(
            RuntimePlanCorpusItem(
                source_path=source_label,
                snapshot_path=snapshot_label,
                counts=counts,
                snapshot_exists=snapshot_exists,
                snapshot_matched=snapshot_matched,
                execution_boundary_ok=execution_boundary_ok,
                errors=item_errors,
                warnings=item_warnings,
            )
        )

    expected_snapshot_names = {f"{source.stem}.runtime-plan.json" for source in sources}
    actual_snapshot_names = {snapshot.name for snapshot in snapshots}
    orphan_snapshots = sorted(actual_snapshot_names - expected_snapshot_names)
    if orphan_snapshots:
        report_errors.append("orphan runtime-plan snapshots found: " + ", ".join(orphan_snapshots))

    for item in items:
        report_errors.extend(f"{item.source_path}: {error}" for error in item.errors)
        report_warnings.extend(f"{item.source_path}: {warning}" for warning in item.warnings)

    return RuntimePlanCorpusReport(
        root=str(root_path),
        examples_dir=_relative_label(examples_path, root_path),
        snapshot_dir=_relative_label(snapshots_path, root_path),
        total_sources=len(sources),
        total_snapshots=len(snapshots),
        items=items,
        orphan_snapshots=orphan_snapshots,
        errors=report_errors,
        warnings=report_warnings,
    )


def runtime_plan_execution_boundary_errors(plan: RuntimePlan) -> list[str]:
    """Return errors if a plan violates the current non-executing boundary."""
    errors: list[str] = []
    capabilities = {capability.name: capability.enabled for capability in plan.capabilities}

    for name in ENABLED_CAPABILITY_NAMES:
        if capabilities.get(name) is not True:
            errors.append(f"capability should be enabled but is not: {name}")

    for name in EXECUTION_CAPABILITY_NAMES:
        if capabilities.get(name) is not False:
            errors.append(f"execution capability unexpectedly enabled: {name}")

    for name in sorted(set(capabilities) - set(ENABLED_CAPABILITY_NAMES) - set(EXECUTION_CAPABILITY_NAMES)):
        if capabilities[name]:
            errors.append(f"unknown capability unexpectedly enabled: {name}")

    for tool in plan.tools:
        if tool.executable:
            errors.append(f"tool unexpectedly executable: {tool.name}")

    for agent in plan.agents:
        if agent.executable:
            errors.append(f"agent unexpectedly executable: {agent.name}")

    for rag in plan.rags:
        if rag.indexing_enabled:
            errors.append(f"RAG indexing unexpectedly enabled: {rag.name}")
        if rag.retrieval_enabled:
            errors.append(f"RAG retrieval unexpectedly enabled: {rag.name}")

    for flow in plan.flows:
        if flow.executable:
            errors.append(f"flow unexpectedly executable: {flow.name}")

    return errors


def format_runtime_plan_corpus_report(report: RuntimePlanCorpusReport) -> str:
    """Render a corpus report for humans."""
    status = "passed" if report.passed else "failed"
    lines = [
        f"AXON runtime-plan corpus check: {status}",
        f"Root: {report.root}",
        f"Examples: {report.examples_dir}",
        f"Snapshots: {report.snapshot_dir}",
        f"Sources: {report.total_sources}",
        f"Snapshots found: {report.total_snapshots}",
        "Items:",
    ]

    for item in report.items:
        item_status = "OK" if item.passed else "FAIL"
        lines.append(f"  - {item.source_path}: {item_status}")
        lines.append(
            "    counts: "
            + ", ".join(f"{key}={value}" for key, value in sorted(item.counts.items()))
        )
        lines.append(f"    snapshot: {'matched' if item.snapshot_matched else 'not matched'}")
        lines.append(f"    execution boundary: {'ok' if item.execution_boundary_ok else 'failed'}")
        for error in item.errors:
            lines.append(f"    error: {error}")
        for warning in item.warnings:
            lines.append(f"    warning: {warning}")

    if report.orphan_snapshots:
        lines.append("Orphan snapshots:")
        lines.extend(f"  - {name}" for name in report.orphan_snapshots)

    if report.errors:
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in report.errors)

    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in report.warnings)

    return "\n".join(lines)


def runtime_plan_corpus_report_to_json(report: RuntimePlanCorpusReport) -> str:
    """Render a corpus report as stable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def _resolve_under_root(root: Path, path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return root / raw


def _relative_label(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
