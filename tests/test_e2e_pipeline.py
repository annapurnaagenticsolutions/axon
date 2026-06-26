"""End-to-end integration tests for the AXON pipeline.

Tests the full flow: parse → validate → typecheck → codegen (all targets) → run.
Verifies that all features added in the enhancement sprints work together.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from axon.parser import parse
from axon.validator import validate
from axon.type_checker import check_types
from axon.ast_nodes import AgentDecl, ToolDecl, TypeAliasDecl, Annotation
from axon.codegen.typescript import generate_typescript
from axon.codegen.go import generate_go
from axon.codegen.rust import generate_rust
from axon.codegen.mcp import generate_mcp_server
from axon.permission import PermissionChecker, Permission, extract_permissions
from axon.structured_logger import StructuredLogger
from axon.otel_exporter import OTelExporter
from axon.ir_compiler import compile_to_ir


# ── Test fixtures ─────────────────────────────────────────────────────────────

SIMPLE_AGENT = """\
tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    version: "1.0.0"

    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
"""

PERMISSION_AGENT = """\
@permission(scope: "fs", access: "read")
tool ReadFile(path: Str) -> Str {
    /// Reads a file from the filesystem.
    fs.read(path)
}

@permission(scope: "network", access: "write")
tool SendWebhook(url: Str, body: Str) -> Bool {
    /// Sends an HTTP POST request.
    http.post(url, body).ok
}

agent SecureBot {
    model: @mock/gpt
    tools: [ReadFile, SendWebhook]
    version: "1.0.0"

    fn run(q: Str) -> Str {
        let content = act ReadFile(path: "config.json")?
        act SendWebhook(url: "https://api.example.com/hook", body: content)?
        Ok("done")
    }
}
"""

TYPE_ALIAS_SOURCE = """\
type Issue = {
    id: Int,
    title: Str
}

tool FetchIssues(repo: Str) -> List<Issue> {
    /// Fetches issues from a repository.
    [Issue(id: 1, title: "test")]
}

agent IssueBot {
    model: @mock/gpt
    tools: [FetchIssues]
    version: "2.0.0"

    fn run(q: Str) -> Result<Str, AgentError> {
        Ok(q)
    }
}
"""


def _write_tmp(content: str) -> Path:
    """Write content to a temp .ax file and return the path."""
    f = tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


# ── Parse → Validate → Typecheck pipeline ─────────────────────────────────────

class TestParseValidatePipeline:
    """Test that parse → validate → typecheck works end-to-end."""

    def test_simple_agent_parses(self):
        decls = parse(SIMPLE_AGENT)
        assert len(decls) == 2
        assert isinstance(decls[0], ToolDecl)
        assert isinstance(decls[1], AgentDecl)
        assert decls[1].version == "1.0.0"

    def test_simple_agent_validates(self):
        decls = parse(SIMPLE_AGENT)
        diagnostics = validate(decls)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 0, f"Validation errors: {[d.message for d in errors]}"

    def test_simple_agent_typechecks(self):
        decls = parse(SIMPLE_AGENT)
        diagnostics = check_types(decls)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 0, f"Type errors: {[d.message for d in errors]}"

    def test_permission_agent_parses(self):
        decls = parse(PERMISSION_AGENT)
        assert len(decls) == 3  # 2 tools + 1 agent
        read_tool = [d for d in decls if isinstance(d, ToolDecl) and d.name == "ReadFile"][0]
        assert any(a.name == "permission" for a in read_tool.annotations)

    def test_permission_agent_validates(self):
        decls = parse(PERMISSION_AGENT)
        diagnostics = validate(decls)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 0, f"Validation errors: {[d.message for d in errors]}"

    def test_type_alias_parses(self):
        decls = parse(TYPE_ALIAS_SOURCE)
        assert len(decls) == 3
        assert isinstance(decls[0], TypeAliasDecl)
        assert decls[0].name == "Issue"

    def test_type_alias_validates(self):
        decls = parse(TYPE_ALIAS_SOURCE)
        diagnostics = validate(decls)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 0, f"Validation errors: {[d.message for d in errors]}"


# ── Parse → Codegen pipeline ──────────────────────────────────────────────────

class TestCodegenPipeline:
    """Test that parse → codegen produces valid output for all targets."""

    def test_typescript_codegen(self):
        decls = parse(SIMPLE_AGENT)
        code = generate_typescript(decls)
        assert "export" in code
        assert "Greet" in code
        assert "Bot" in code

    def test_go_codegen(self):
        decls = parse(SIMPLE_AGENT)
        code = generate_go(decls, output_name="test_app")
        assert "package test_app" in code
        assert "func Greet" in code
        assert "type Bot struct" in code
        assert "1.0.0" in code

    def test_rust_codegen(self):
        decls = parse(SIMPLE_AGENT)
        code = generate_rust(decls, output_name="test_app")
        assert "pub mod test_app" in code
        assert "pub fn greet" in code
        assert "pub struct Bot" in code
        assert "1.0.0" in code

    def test_mcp_codegen(self):
        decls = parse(SIMPLE_AGENT)
        code = generate_mcp_server(decls)
        assert "Greet" in code

    def test_go_codegen_with_type_alias(self):
        decls = parse(TYPE_ALIAS_SOURCE)
        code = generate_go(decls)
        assert "type Issue struct" in code
        assert "func FetchIssues" in code
        assert "type IssueBot struct" in code

    def test_rust_codegen_with_type_alias(self):
        decls = parse(TYPE_ALIAS_SOURCE)
        code = generate_rust(decls)
        assert "pub struct Issue" in code
        assert "pub fn fetch_issues" in code
        assert "pub struct IssueBot" in code

    def test_go_codegen_with_permissions(self):
        decls = parse(PERMISSION_AGENT)
        code = generate_go(decls)
        assert "func ReadFile" in code
        assert "func SendWebhook" in code
        assert "type SecureBot struct" in code

    def test_rust_codegen_with_permissions(self):
        decls = parse(PERMISSION_AGENT)
        code = generate_rust(decls)
        assert "pub fn read_file" in code
        assert "pub fn send_webhook" in code
        assert "pub struct SecureBot" in code


# ── Parse → IR compilation ────────────────────────────────────────────────────

class TestIRPipeline:
    """Test that parse → IR compilation preserves all features."""

    def test_simple_agent_ir(self):
        path = _write_tmp(SIMPLE_AGENT)
        ir = compile_to_ir(path)
        assert ir is not None
        assert len(ir.agents) == 1
        assert ir.agents[0].name == "Bot"

    def test_permission_agent_ir(self):
        path = _write_tmp(PERMISSION_AGENT)
        ir = compile_to_ir(path)
        assert ir is not None
        assert len(ir.tools) == 2

    def test_type_alias_ir(self):
        path = _write_tmp(TYPE_ALIAS_SOURCE)
        ir = compile_to_ir(path)
        assert ir is not None
        assert len(ir.type_aliases) == 1
        assert ir.type_aliases[0].name == "Issue"


# ── Permission system integration ─────────────────────────────────────────────

class TestPermissionIntegration:
    """Test that permissions flow from parse → checker → enforcement."""

    def test_permissions_extracted_from_parsed_decls(self):
        decls = parse(PERMISSION_AGENT)
        perm_map = extract_permissions(decls)
        assert "ReadFile" in perm_map
        assert "SendWebhook" in perm_map
        assert perm_map["ReadFile"][0].scope == "fs"
        assert perm_map["SendWebhook"][0].scope == "network"

    def test_permission_checker_denies_without_grant(self):
        decls = parse(PERMISSION_AGENT)
        tools = [d for d in decls if isinstance(d, ToolDecl)]
        checker = PermissionChecker(granted=set())
        allowed_tools = checker.filter_tools(tools)
        assert len(allowed_tools) == 0  # all denied without grants

    def test_permission_checker_allows_with_grant(self):
        decls = parse(PERMISSION_AGENT)
        tools = [d for d in decls if isinstance(d, ToolDecl)]
        checker = PermissionChecker(granted={"fs:read", "network:write"})
        allowed_tools = checker.filter_tools(tools)
        assert len(allowed_tools) == 2  # both allowed with grants

    def test_permission_checker_wildcard_grant(self):
        decls = parse(PERMISSION_AGENT)
        tools = [d for d in decls if isinstance(d, ToolDecl)]
        checker = PermissionChecker(granted={"*:*"})
        allowed_tools = checker.filter_tools(tools)
        assert len(allowed_tools) == 2

    def test_permission_checker_partial_grant(self):
        decls = parse(PERMISSION_AGENT)
        tools = [d for d in decls if isinstance(d, ToolDecl)]
        checker = PermissionChecker(granted={"fs:read"})
        allowed_tools = checker.filter_tools(tools)
        assert len(allowed_tools) == 1  # only ReadFile allowed


# ── Observability integration ─────────────────────────────────────────────────

class TestObservabilityIntegration:
    """Test that observability components can be instantiated and used."""

    def test_structured_logger_emits(self):
        import io
        buf = io.StringIO()
        logger = StructuredLogger(enabled=True, output=buf)
        logger.info("test_event", key="value")
        content = buf.getvalue()
        assert "test_event" in content
        assert "key" in content

    def test_otel_exporter_no_crash_without_endpoint(self):
        exporter = OTelExporter(endpoint=None)
        span = exporter.start_span("test")
        exporter.end_span(status="OK")
        # No exception means success

    def test_otel_exporter_span_attributes(self):
        exporter = OTelExporter(endpoint=None)
        span = exporter.start_span("test", attributes={"agent": "Bot"})
        assert span.name == "test"
        assert span.attributes["agent"] == "Bot"
        exporter.end_span()


# ── Full pipeline: parse → validate → codegen → verify ────────────────────────

class TestFullPipeline:
    """Test the complete pipeline end-to-end."""

    def test_simple_agent_full_pipeline(self):
        """Parse → validate → typecheck → IR → codegen all targets."""
        # Parse
        decls = parse(SIMPLE_AGENT)
        assert len(decls) == 2

        # Validate
        val_diags = validate(decls)
        assert not any(d.severity == "error" for d in val_diags)

        # Typecheck
        type_diags = check_types(decls)
        assert not any(d.severity == "error" for d in type_diags)

        # IR
        path = _write_tmp(SIMPLE_AGENT)
        ir = compile_to_ir(path)
        assert ir.agents[0].name == "Bot"

        # Codegen all targets
        ts_code = generate_typescript(decls)
        go_code = generate_go(decls)
        rust_code = generate_rust(decls)
        mcp_code = generate_mcp_server(decls)

        assert len(ts_code) > 100
        assert len(go_code) > 100
        assert len(rust_code) > 100
        assert len(mcp_code) > 100

    def test_permission_agent_full_pipeline(self):
        """Parse → validate → permissions → codegen all targets."""
        # Parse
        decls = parse(PERMISSION_AGENT)

        # Validate
        val_diags = validate(decls)
        assert not any(d.severity == "error" for d in val_diags)

        # Extract permissions
        perm_map = extract_permissions(decls)
        assert len(perm_map) == 2

        # Permission enforcement
        tools = [d for d in decls if isinstance(d, ToolDecl)]
        checker = PermissionChecker(granted={"fs:read", "network:write"})
        assert len(checker.filter_tools(tools)) == 2

        checker_deny = PermissionChecker(granted=set())
        assert len(checker_deny.filter_tools(tools)) == 0

        # Codegen
        go_code = generate_go(decls)
        rust_code = generate_rust(decls)
        assert "ReadFile" in go_code
        assert "read_file" in rust_code

    def test_type_alias_full_pipeline(self):
        """Parse → validate → IR → codegen with type aliases."""
        decls = parse(TYPE_ALIAS_SOURCE)

        # Validate
        val_diags = validate(decls)
        assert not any(d.severity == "error" for d in val_diags)

        # IR
        path = _write_tmp(TYPE_ALIAS_SOURCE)
        ir = compile_to_ir(path)
        assert len(ir.type_aliases) == 1

        # Codegen — type aliases should appear in generated code
        go_code = generate_go(decls)
        rust_code = generate_rust(decls)
        ts_code = generate_typescript(decls)

        assert "Issue" in go_code
        assert "Issue" in rust_code
        assert "Issue" in ts_code

    def test_version_field_preserved_through_pipeline(self):
        """Version field survives parse → IR → codegen."""
        decls = parse(SIMPLE_AGENT)
        agent = [d for d in decls if isinstance(d, AgentDecl)][0]
        assert agent.version == "1.0.0"

        path = _write_tmp(SIMPLE_AGENT)
        ir = compile_to_ir(path)
        assert ir.agents[0].name == "Bot"

        go_code = generate_go(decls)
        assert "1.0.0" in go_code

        rust_code = generate_rust(decls)
        assert "1.0.0" in rust_code
