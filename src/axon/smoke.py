"""Generated-server smoke testing for AXON Phase 1.

The FastMCP code generator emits normal Python source, but Phase 1 tests should
not require ``fastmcp`` to be installed. This module compiles and loads generated
servers with a tiny in-memory FastMCP stub, then inspects the resulting module
namespace for expected tools and metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import sys
import types
from pathlib import Path
from typing import Iterable, Literal

from axon.ast_nodes import ToolDecl
from axon.codegen.mcp import generate_mcp_server, to_snake_case
from axon.parser import parse
from axon.validator import validate_or_raise

SmokeSeverity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class SmokeDiagnostic:
    """One generated-server smoke-test finding."""

    severity: SmokeSeverity
    message: str
    code: str = ""

    def format(self) -> str:
        code = f" [{self.code}]" if self.code else ""
        return f"{self.severity}: {self.message}{code}"

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "message": self.message,
            "code": self.code,
        }


@dataclass
class SmokeReport:
    """Structured result for a generated-server smoke test."""

    passed: bool
    diagnostics: list[SmokeDiagnostic] = field(default_factory=list)
    server_name: str | None = None
    registered_tools: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def format(self) -> str:
        """Return stable human-readable output for the CLI."""
        if self.passed:
            parts = ["OK: generated server passed AXON smoke test"]
        else:
            parts = ["FAILED: generated server failed AXON smoke test"]

        if self.server_name:
            parts.append(f"server: {self.server_name}")
        if self.registered_tools:
            parts.append(f"tools: {', '.join(self.registered_tools)}")
        if self.diagnostics:
            parts.extend(diagnostic.format() for diagnostic in self.diagnostics)
        return "\n".join(parts)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "server_name": self.server_name,
            "registered_tools": list(self.registered_tools),
            "metadata": dict(self.metadata),
        }


class SmokeTestError(Exception):
    """Raised when a smoke test fails and a caller requests exception mode."""

    def __init__(self, report: SmokeReport):
        self.report = report
        super().__init__(report.format())


class _FakeFastMCP:
    """Minimal FastMCP stand-in used only by the smoke harness."""

    instances: list["_FakeFastMCP"] = []

    def __init__(self, name: str):
        self.name = name
        self.tools: dict[str, object] = {}
        self.run_called = False
        _FakeFastMCP.instances.append(self)

    def tool(self, *args: object, **kwargs: object):
        """Return a decorator compatible with ``@mcp.tool()``."""
        if args and callable(args[0]) and not kwargs:
            func = args[0]
            self.tools[getattr(func, "__name__", repr(func))] = func
            return func

        def decorator(func):
            self.tools[getattr(func, "__name__", repr(func))] = func
            return func

        return decorator

    def run(self) -> None:
        self.run_called = True


def smoke_test_source_file(source_path: str | Path, output_name: str | None = None) -> SmokeReport:
    """Parse, validate, generate, and smoke-test one AXON source file."""
    source = Path(source_path)
    declarations = parse(source.read_text(encoding="utf-8"))
    validate_or_raise(declarations)
    return smoke_test_declarations(declarations, output_name=output_name or source.stem)


def smoke_test_declarations(declarations: list, output_name: str = "axon_server") -> SmokeReport:
    """Generate a FastMCP server from declarations and smoke-test it."""
    code = generate_mcp_server(declarations, output_name=output_name)
    expected_tools = [to_snake_case(tool.name) for tool in declarations if isinstance(tool, ToolDecl)]
    return smoke_test_generated_code(code, expected_tools=expected_tools)


def smoke_test_generated_code(
    code: str,
    expected_tools: Iterable[str] | None = None,
    filename: str = "<axon-generated-server>",
) -> SmokeReport:
    """Compile and load generated Python server code using a fake FastMCP module.

    The generated server is executed with ``__name__`` set to a non-main value,
    so the ``if __name__ == "__main__": mcp.run()`` entry point is not triggered.
    """
    diagnostics: list[SmokeDiagnostic] = []
    expected = list(expected_tools or [])

    try:
        compiled = compile(code, filename, "exec")
    except SyntaxError as exc:
        diagnostics.append(
            SmokeDiagnostic(
                severity="error",
                message=f"generated Python has invalid syntax: {exc}",
                code="generated-python-syntax-error",
            )
        )
        return SmokeReport(passed=False, diagnostics=diagnostics)

    fake_module = types.ModuleType("fastmcp")
    fake_module.FastMCP = _FakeFastMCP

    previous_fastmcp = sys.modules.get("fastmcp")
    _FakeFastMCP.instances = []
    namespace: dict[str, object] = {"__name__": "axon_smoke_generated"}

    try:
        sys.modules["fastmcp"] = fake_module
        exec(compiled, namespace)
    except Exception as exc:  # pragma: no cover - exact exception varies by generated code
        diagnostics.append(
            SmokeDiagnostic(
                severity="error",
                message=f"generated Python failed to load: {type(exc).__name__}: {exc}",
                code="generated-python-load-error",
            )
        )
        return SmokeReport(passed=False, diagnostics=diagnostics)
    finally:
        if previous_fastmcp is None:
            sys.modules.pop("fastmcp", None)
        else:
            sys.modules["fastmcp"] = previous_fastmcp

    mcp = namespace.get("mcp")
    if not isinstance(mcp, _FakeFastMCP):
        diagnostics.append(
            SmokeDiagnostic(
                severity="error",
                message="generated server did not create a FastMCP instance named 'mcp'",
                code="missing-mcp-instance",
            )
        )
        registered_tools: list[str] = []
        server_name = None
    else:
        registered_tools = sorted(mcp.tools.keys())
        server_name = mcp.name
        if mcp.run_called:
            diagnostics.append(
                SmokeDiagnostic(
                    severity="error",
                    message="generated server called mcp.run() during import/load",
                    code="run-called-during-load",
                )
            )

    for tool_name in expected:
        if tool_name not in namespace:
            diagnostics.append(
                SmokeDiagnostic(
                    severity="error",
                    message=f"expected generated function '{tool_name}' was not found",
                    code="missing-generated-function",
                )
            )
        if tool_name not in registered_tools:
            diagnostics.append(
                SmokeDiagnostic(
                    severity="error",
                    message=f"expected FastMCP tool '{tool_name}' was not registered",
                    code="missing-registered-tool",
                )
            )

    metadata = _collect_metadata(namespace)
    for key in ("AXON_AGENT_TOOLS", "AXON_AGENT_MEMORY", "AXON_AGENT_MODEL"):
        if key not in namespace:
            diagnostics.append(
                SmokeDiagnostic(
                    severity="warning",
                    message=f"generated metadata constant '{key}' is missing",
                    code="missing-metadata",
                )
            )

    return SmokeReport(
        passed=not any(d.severity == "error" for d in diagnostics),
        diagnostics=diagnostics,
        server_name=server_name,
        registered_tools=registered_tools,
        metadata=metadata,
    )


def smoke_test_or_raise(report: SmokeReport) -> None:
    """Raise SmokeTestError when a report has errors."""
    if not report.passed:
        raise SmokeTestError(report)


def report_to_json(report: SmokeReport) -> str:
    """Serialize a smoke report for CLI/tooling output."""
    return json.dumps(report.to_dict(), indent=2)


def _collect_metadata(namespace: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in namespace.items()
        if key.startswith("AXON_") and isinstance(value, (str, int, float, bool, list, dict, type(None)))
    }
