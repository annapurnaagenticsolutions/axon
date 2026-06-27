"""AXON Playground server — serves the web playground and provides API endpoints.

When the WASM parser isn't built yet, this server provides the same
parse/validate/codegen functionality via HTTP endpoints. The playground
frontend automatically detects whether WASM is available and falls back
to the server API.

Usage:
    python -m axon.playground_server [--port 8080] [--host localhost]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from axon.parser import parse
from axon.validator import validate
from axon.type_checker import check_types
from axon.ast_snapshot import declarations_to_json
from axon.codegen.typescript import generate_typescript
from axon.codegen.go import generate_go
from axon.codegen.rust import generate_rust
from axon.codegen.mcp import generate_mcp_server
from axon.codegen.governance import generate_governance_submission


PLAYGROUND_DIR = Path(__file__).parent.parent.parent / "axon-parser" / "playground"


try:
    from pydantic import BaseModel

    class SourceBody(BaseModel):
        source: str = ""

    class CodegenBody(BaseModel):
        source: str = ""
        target: str = "typescript"

    class EvalExprBody(BaseModel):
        expr: str = ""
        scope: str = "{}"
        max_depth: int = 100

    class GovernBody(BaseModel):
        source: str = ""
        mesh_url: str = ""
except ImportError:
    SourceBody = None  # type: ignore
    CodegenBody = None  # type: ignore
    EvalExprBody = None  # type: ignore
    GovernBody = None  # type: ignore


def _parse_endpoint(source: str) -> dict[str, Any]:
    """Parse AXON source and return IR-like JSON."""
    try:
        declarations = parse(source)
        from axon.ir_compiler import _extract_imports, _extract_type_aliases, _extract_rags, _extract_prompts, _extract_tools, _extract_agents, _extract_flows
        from axon.ir_schema import AxonIR
        from dataclasses import asdict
        ir = AxonIR(version="0.2.0")
        _extract_imports(declarations, ir)
        _extract_type_aliases(declarations, ir)
        _extract_rags(declarations, ir)
        _extract_prompts(declarations, ir)
        _extract_tools(declarations, ir)
        _extract_agents(declarations, ir)
        _extract_flows(declarations, ir)
        return json.loads(json.dumps(asdict(ir), default=str))
    except Exception as e:
        return {"error": str(e)}


def _validate_endpoint(source: str) -> dict[str, Any]:
    """Validate AXON source and return diagnostics."""
    try:
        declarations = parse(source)
        diagnostics = validate(declarations)
        type_diagnostics = check_types(declarations)
        all_diags = diagnostics + type_diagnostics
        return {
            "diagnostics": [
                {
                    "severity": d.severity,
                    "message": d.message,
                    "line": d.line,
                    "code": d.code,
                }
                for d in all_diags
            ],
            "error_count": sum(1 for d in all_diags if d.severity == "error"),
            "warning_count": sum(1 for d in all_diags if d.severity == "warning"),
        }
    except SyntaxError as e:
        return {
            "diagnostics": [{"severity": "error", "message": str(e), "line": 0, "code": "parse-error"}],
            "error_count": 1,
            "warning_count": 0,
        }
    except Exception as e:
        return {
            "diagnostics": [{"severity": "error", "message": str(e), "line": 0, "code": "internal"}],
            "error_count": 1,
            "warning_count": 0,
        }


def _codegen_endpoint(source: str, target: str) -> dict[str, Any]:
    """Generate code from AXON source."""
    try:
        declarations = parse(source)
        if target == "typescript":
            code = generate_typescript(declarations)
        elif target == "go":
            code = generate_go(declarations)
        elif target == "rust":
            code = generate_rust(declarations)
        elif target == "mcp":
            code = generate_mcp_server(declarations)
        else:
            return {"error": f"Unknown target: {target}"}
        return {"code": code, "target": target}
    except Exception as e:
        return {"error": str(e)}


def _ast_endpoint(source: str) -> dict[str, Any]:
    """Parse AXON source and return AST snapshot JSON."""
    try:
        declarations = parse(source)
        return {"ast": json.loads(declarations_to_json(declarations))}
    except Exception as e:
        return {"error": str(e)}


def _eval_expr_endpoint(expr: str, scope_json: str, max_depth: int) -> dict[str, Any]:
    """Evaluate an AXON expression with a scope."""
    try:
        from axon.expression_parser import parse_expression
        from axon.evaluator import evaluate
        import json as _json
        ast = parse_expression(expr)
        scope = _json.loads(scope_json) if scope_json else {}
        result = evaluate(ast, scope, max_depth=max_depth)
        if hasattr(result, 'is_ok') and result.is_ok():
            value = result.unwrap()
        elif hasattr(result, 'is_err') and result.is_err():
            return {"error": str(result.unwrap_err())}
        else:
            value = result
        return {"result": _json.dumps(value, default=str), "ast": _json.loads(_json.dumps(ast, default=str))}
    except Exception as e:
        return {"error": str(e)}


def _govern_endpoint(source: str, mesh_url: str) -> dict[str, Any]:
    """Generate a governance submission from AXON source and optionally submit to Mesh."""
    try:
        declarations = parse(source)
        errors = [d for d in validate(declarations) if d.severity == "error"]
        if errors:
            return {"error": f"Validation failed: {len(errors)} error(s)", "validation_errors": [str(e) for e in errors]}
        submission = generate_governance_submission(declarations, source_filename="playground.ax")
        result: dict[str, Any] = {"submission": submission}
        if mesh_url:
            import urllib.request
            url = f"{mesh_url.rstrip('/')}/governance/run"
            req = urllib.request.Request(
                url,
                data=json.dumps(submission).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                governance_response = json.loads(resp.read().decode("utf-8"))
            result["governance_response"] = governance_response
        return result
    except Exception as e:
        return {"error": str(e)}


def create_app():
    """Create the playground web app."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

    app = FastAPI(title="AXON Playground", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return FileResponse(PLAYGROUND_DIR / "index.html")

    @app.post("/api/parse", response_class=JSONResponse)
    async def api_parse(body: SourceBody):
        return _parse_endpoint(body.source)

    @app.post("/api/validate", response_class=JSONResponse)
    async def api_validate(body: SourceBody):
        return _validate_endpoint(body.source)

    @app.post("/api/codegen", response_class=JSONResponse)
    async def api_codegen(body: CodegenBody):
        return _codegen_endpoint(body.source, body.target)

    @app.post("/api/ast", response_class=JSONResponse)
    async def api_ast(body: SourceBody):
        return _ast_endpoint(body.source)

    @app.post("/api/eval-expr", response_class=JSONResponse)
    async def api_eval_expr(body: EvalExprBody):
        return _eval_expr_endpoint(body.expr, body.scope, body.max_depth)

    @app.post("/api/govern", response_class=JSONResponse)
    async def api_govern(body: GovernBody):
        return _govern_endpoint(body.source, body.mesh_url)

    # Serve static files
    @app.get("/playground.css")
    async def css():
        return FileResponse(PLAYGROUND_DIR / "playground.css")

    @app.get("/playground.js")
    async def js():
        return FileResponse(PLAYGROUND_DIR / "playground.js", media_type="application/javascript")

    return app


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="AXON Playground server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="localhost")
    args = parser.parse_args()

    import uvicorn
    app = create_app()
    print(f"AXON Playground running at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
