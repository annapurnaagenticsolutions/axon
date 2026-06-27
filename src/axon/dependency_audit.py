"""Dependency and optional-extra audit utilities for AXON.

The Phase 1 compiler is intentionally stdlib-only at runtime. Optional runtime
capabilities, such as running generated FastMCP servers, stay behind extras. This
module makes that boundary testable and available through the CLI.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import tomllib
from typing import Any, Iterable


SECRET_FIELD_NAMES = {"api_key", "token", "secret", "password", "credential", "credentials"}
REQUIRED_EXTRAS = {
    "serve": "fastmcp",
    "dev": "pytest",
}
PROVIDER_SDK_MODULES = {"anthropic", "openai", "cohere", "google", "google_ai", "googleai"}

# Optional runtime extension modules that are allowed in src/axon but not
# required by the compiler core.  These back optional capabilities (API
# server, distributed bus, OTel exporters, Postgres store, secret manager,\# service registry) and are imported behind try/except or extras guards.
OPTIONAL_RUNTIME_MODULES = {
    "fastapi",
    "uvicorn",
    "pydantic",
    "redis",
    "nats",
    "requests",
    "opentelemetry",
    "psycopg",
    "psycopg2",
    "keyring",
    "hvac",
    "sentence_transformers",
    "chromadb",
    "axon_parser",
}

# Keep a small fallback for interpreters where sys.stdlib_module_names is absent.
_FALLBACK_STDLIB = {
    "__future__",
    "argparse",
    "ast",
    "base64",
    "collections",
    "contextlib",
    "dataclasses",
    "datetime",
    "enum",
    "fnmatch",
    "functools",
    "importlib",
    "inspect",
    "io",
    "itertools",
    "json",
    "math",
    "os",
    "pathlib",
    "platform",
    "re",
    "shutil",
    "subprocess",
    "sys",
    "tempfile",
    "textwrap",
    "time",
    "tomllib",
    "types",
    "typing",
    "unittest",
    "uuid",
    "zipfile",
}

STDLIB_MODULES = set(getattr(sys, "stdlib_module_names", ())) | _FALLBACK_STDLIB | {"result"}


@dataclass(frozen=True)
class DependencyFinding:
    """One dependency audit finding."""

    severity: str  # "error" or "warning"
    code: str
    message: str
    path: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "detail": self.detail,
        }

    def format(self) -> str:
        location = f" [{self.path}]" if self.path else ""
        detail = f"\n  {self.detail}" if self.detail else ""
        return f"{self.severity}: {self.code}: {self.message}{location}{detail}"


@dataclass(frozen=True)
class DependencyAuditReport:
    """Structured dependency audit result."""

    project_path: str
    pyproject_path: str | None
    core_dependencies: list[str] = field(default_factory=list)
    optional_dependencies: dict[str, list[str]] = field(default_factory=dict)
    scanned_source_files: list[str] = field(default_factory=list)
    findings: list[DependencyFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "pyproject_path": self.pyproject_path,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "core_dependencies": list(self.core_dependencies),
            "optional_dependencies": {key: list(value) for key, value in sorted(self.optional_dependencies.items())},
            "scanned_source_files": list(self.scanned_source_files),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def format(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"AXON dependency audit: {status}",
            f"Project: {self.project_path}",
            f"pyproject.toml: {self.pyproject_path or '<not found>'}",
            f"Core dependencies: {len(self.core_dependencies)}",
            f"Optional extras: {', '.join(sorted(self.optional_dependencies)) if self.optional_dependencies else '<none>'}",
            f"Source files scanned: {len(self.scanned_source_files)}",
            f"Findings: {self.error_count} error(s), {self.warning_count} warning(s)",
        ]
        if self.findings:
            lines.append("")
            lines.extend(finding.format() for finding in self.findings)
        return "\n".join(lines)


def audit_dependencies(project_path: str | Path = ".") -> DependencyAuditReport:
    """Audit AXON dependency boundaries for a project tree.

    The audit is intentionally conservative:
    - compiler core dependencies in `[project].dependencies` must remain empty;
    - `fastmcp` must live in the `serve` extra, not the core dependency list;
    - `pytest` must live in the `dev` extra;
    - source files under `src/axon` may import only stdlib or `axon.*` modules;
    - provider SDKs must not be imported by the compiler core;
    - generated FastMCP import text in codegen must be backed by the `serve` extra.
    """
    project = Path(project_path).expanduser().resolve()
    findings: list[DependencyFinding] = []
    pyproject_path = project / "pyproject.toml"
    core_dependencies: list[str] = []
    optional_dependencies: dict[str, list[str]] = {}

    if not pyproject_path.exists():
        findings.append(
            DependencyFinding(
                severity="error",
                code="pyproject-missing",
                message="pyproject.toml was not found",
                path=str(pyproject_path),
            )
        )
    else:
        try:
            pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            findings.append(
                DependencyFinding(
                    severity="error",
                    code="pyproject-invalid-toml",
                    message="pyproject.toml is not valid TOML",
                    path=str(pyproject_path),
                    detail=str(exc),
                )
            )
            pyproject_data = {}

        project_data = pyproject_data.get("project", {}) if isinstance(pyproject_data, dict) else {}
        core_dependencies = list(project_data.get("dependencies", []) or [])
        optional_dependencies = {
            str(name): list(values or [])
            for name, values in (project_data.get("optional-dependencies", {}) or {}).items()
        }
        findings.extend(_audit_pyproject_dependencies(core_dependencies, optional_dependencies, pyproject_path))

    src_dir = project / "src" / "axon"
    scanned_source_files: list[str] = []
    if not src_dir.exists():
        findings.append(
            DependencyFinding(
                severity="warning",
                code="src-axon-missing",
                message="src/axon was not found; source import boundary could not be checked",
                path=str(src_dir),
            )
        )
    else:
        for source_file in sorted(src_dir.rglob("*.py")):
            rel = source_file.relative_to(project)
            # Provider plugins are allowed to import provider SDKs
            if "providers" in rel.parts:
                continue
            scanned_source_files.append(str(rel))
            findings.extend(_audit_source_imports(project, source_file, rel))

    findings.extend(_audit_fastmcp_codegen_boundary(project, optional_dependencies))
    findings.extend(_audit_docs_dependency_boundary(project))

    return DependencyAuditReport(
        project_path=str(project),
        pyproject_path=str(pyproject_path) if pyproject_path.exists() else None,
        core_dependencies=core_dependencies,
        optional_dependencies=optional_dependencies,
        scanned_source_files=scanned_source_files,
        findings=findings,
    )


def dependency_audit_to_json(report: DependencyAuditReport) -> str:
    """Render a dependency audit report as JSON."""
    return report.to_json()


def format_dependency_audit(report: DependencyAuditReport) -> str:
    """Render a dependency audit report for humans."""
    return report.format()


def has_dependency_errors(report: DependencyAuditReport) -> bool:
    """Return whether the audit has one or more errors."""
    return report.error_count > 0


def _audit_pyproject_dependencies(
    core_dependencies: list[str],
    optional_dependencies: dict[str, list[str]],
    pyproject_path: Path,
) -> list[DependencyFinding]:
    findings: list[DependencyFinding] = []
    if core_dependencies:
        findings.append(
            DependencyFinding(
                severity="error",
                code="core-dependencies-not-empty",
                message="compiler core must remain stdlib-only; move runtime dependencies to optional extras",
                path=str(pyproject_path),
                detail=", ".join(core_dependencies),
            )
        )

    lowered_core = [_package_name(dep) for dep in core_dependencies]
    for disallowed in ("fastmcp", "pytest", *sorted(PROVIDER_SDK_MODULES)):
        if disallowed in lowered_core:
            findings.append(
                DependencyFinding(
                    severity="error",
                    code="disallowed-core-dependency",
                    message=f"{disallowed} must not be listed as a core dependency",
                    path=str(pyproject_path),
                )
            )

    for extra_name, required_package in REQUIRED_EXTRAS.items():
        dependencies = optional_dependencies.get(extra_name)
        if dependencies is None:
            findings.append(
                DependencyFinding(
                    severity="error",
                    code="required-extra-missing",
                    message=f"optional dependency group '{extra_name}' is required",
                    path=str(pyproject_path),
                    detail=f"expected package: {required_package}",
                )
            )
            continue
        package_names = [_package_name(dep) for dep in dependencies]
        if required_package not in package_names:
            findings.append(
                DependencyFinding(
                    severity="error",
                    code="required-extra-package-missing",
                    message=f"optional dependency group '{extra_name}' must include {required_package}",
                    path=str(pyproject_path),
                )
            )

    serve_names = [_package_name(dep) for dep in optional_dependencies.get("serve", [])]
    if "fastmcp" not in serve_names:
        findings.append(
            DependencyFinding(
                severity="error",
                code="fastmcp-extra-missing",
                message="generated-server runtime dependency fastmcp must remain in the 'serve' extra",
                path=str(pyproject_path),
            )
        )

    return findings


def _audit_source_imports(project: Path, source_file: Path, rel_path: Path) -> list[DependencyFinding]:
    findings: list[DependencyFinding] = []
    text = source_file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(source_file))
    except SyntaxError as exc:
        findings.append(
            DependencyFinding(
                severity="error",
                code="source-python-syntax-error",
                message="source file could not be parsed as Python for dependency audit",
                path=str(source_file.relative_to(project)),
                detail=str(exc),
            )
        )
        return findings

    # Optional runtime extension files may import their backing libraries.
    optional_files = {
        "api_server.py",
        "cli.py",
        "dashboard.py",
        "distributed_bus.py",
        "lsp_server.py",
        "native_evaluator.py",
        "otel_exporter.py",
        "otlp_exporter.py",
        "playground_server.py",
        "postgres_store.py",
        "rag_embedder.py",
        "runtime.py",
        "runtime_cache.py",
        "secret_manager.py",
        "service_registry.py",
        "vector_store.py",
    }
    is_optional_file = rel_path.name in optional_files

    for imported_module in _iter_imported_modules(tree):
        root_module = imported_module.split(".", 1)[0]
        if root_module in {"axon", *STDLIB_MODULES}:
            continue
        if is_optional_file and root_module in OPTIONAL_RUNTIME_MODULES:
            continue

        severity = "error"
        code = "external-source-import"
        message = "compiler source imports a non-stdlib external module"
        if root_module in PROVIDER_SDK_MODULES:
            code = "provider-sdk-import-in-core"
            message = "provider SDK imports must stay out of the compiler core"

        findings.append(
            DependencyFinding(
                severity=severity,
                code=code,
                message=message,
                path=str(source_file.relative_to(project)),
                detail=imported_module,
            )
        )

    return findings


def _audit_fastmcp_codegen_boundary(
    project: Path,
    optional_dependencies: dict[str, list[str]],
) -> list[DependencyFinding]:
    findings: list[DependencyFinding] = []
    codegen_file = project / "src" / "axon" / "codegen" / "mcp.py"
    if not codegen_file.exists():
        return findings

    text = codegen_file.read_text(encoding="utf-8")
    mentions_fastmcp_generated_import = "from fastmcp import FastMCP" in text
    serve_names = [_package_name(dep) for dep in optional_dependencies.get("serve", [])]

    if mentions_fastmcp_generated_import and "fastmcp" not in serve_names:
        findings.append(
            DependencyFinding(
                severity="error",
                code="generated-fastmcp-unbacked-by-extra",
                message="code generator emits FastMCP imports but pyproject.toml does not expose a serve extra with fastmcp",
                path=str(codegen_file.relative_to(project)),
            )
        )

    return findings


def _audit_docs_dependency_boundary(project: Path) -> list[DependencyFinding]:
    findings: list[DependencyFinding] = []
    readme = project / "README.md"
    if not readme.exists():
        findings.append(
            DependencyFinding(
                severity="warning",
                code="readme-missing",
                message="README.md was not found; install boundary documentation could not be checked",
                path=str(readme),
            )
        )
        return findings

    text = readme.read_text(encoding="utf-8")
    expected_phrases = [
        'python -m pip install -e ".[dev]"',
        'python -m pip install -e ".[serve]"',
        "The compiler itself does not require FastMCP",
    ]
    for phrase in expected_phrases:
        if phrase not in text:
            findings.append(
                DependencyFinding(
                    severity="warning",
                    code="readme-install-boundary-missing",
                    message="README does not document the expected dependency boundary phrase",
                    path=str(readme),
                    detail=phrase,
                )
            )

    return findings


def _iter_imported_modules(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                continue
            if node.module:
                yield node.module


def _package_name(requirement: str) -> str:
    name_chars = []
    for char in requirement.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            name_chars.append(char)
            continue
        break
    return "".join(name_chars).lower().replace("_", "-")
