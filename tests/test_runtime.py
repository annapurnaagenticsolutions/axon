"""Tests for AXON runtime executor."""

from pathlib import Path

from result import Ok, Err

from axon.runtime import RuntimeConfig, execute_runtime, RuntimeExecutor


def _write_temp(source: str, tmp_path: Path, name: str = "test.ax") -> Path:
    p = tmp_path / name
    p.write_text(source, encoding="utf-8")
    return p


def test_execute_simple_return(tmp_path: Path):
    """Agent method just returns the parameter."""
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p, args={"q": "World"})
    result = execute_runtime(cfg)
    assert isinstance(result, Ok)
    assert result.ok_value == "World"


def test_execute_missing_agent(tmp_path: Path):
    source = '''tool Greet(name: Str) -> Str { "hi" }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p)
    result = execute_runtime(cfg)
    assert isinstance(result, Err)
    assert "No agent declaration" in result.err_value


def test_execute_missing_run_method(tmp_path: Path):
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn other() -> () {}
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p)
    result = execute_runtime(cfg)
    assert isinstance(result, Err)
    assert "no run() method" in result.err_value


def test_execute_missing_argument(tmp_path: Path):
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p, args={})
    result = execute_runtime(cfg)
    assert isinstance(result, Err)
    assert "Missing argument: q" in result.err_value


def test_execute_act_tool_dispatch(tmp_path: Path):
    """Agent calls a tool via ``act``."""
    source = '''tool Greet(name: Str) -> Str {
        "Hello, {name}!"
    }

    agent Bot {
        model: @mock/model
        tools: [Greet]
        fn run(q: Str) -> Str {
            act Greet(name: q)
        }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p, args={"q": "World"})
    result = execute_runtime(cfg)
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, World!"


def test_execute_act_with_literal_arg(tmp_path: Path):
    """Tool called with a literal argument."""
    source = '''tool Greet(name: Str) -> Str {
        "Hello, {name}!"
    }

    agent Bot {
        model: @mock/model
        tools: [Greet]
        fn run() -> Str {
            act Greet(name: "Universe")
        }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p)
    result = execute_runtime(cfg)
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello, Universe!"


def test_execute_tool_not_found(tmp_path: Path):
    """``act`` references a tool that does not exist."""
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run() -> Str {
            act MissingTool()
        }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p)
    result = execute_runtime(cfg)
    assert isinstance(result, Err)
    assert "Tool dispatch failed" in result.err_value


def test_execute_trace_output(tmp_path: Path):
    """Trace JSONL is written when trace_output is set."""
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = _write_temp(source, tmp_path)
    trace_path = tmp_path / "trace.jsonl"
    cfg = RuntimeConfig(
        source_path=p,
        args={"q": "hi"},
        trace_output=trace_path,
    )
    result = execute_runtime(cfg)
    assert isinstance(result, Ok)

    assert trace_path.exists()
    lines = trace_path.read_text().strip().split("\n")
    assert len(lines) == 4  # agent_start, method_start, method_return, agent_end
    import json
    events = [json.loads(line) for line in lines]
    assert events[0]["event_type"] == "agent_start"
    assert events[1]["event_type"] == "method_start"
    assert events[2]["event_type"] == "method_return"
    assert events[3]["event_type"] == "agent_end"


def test_execute_numeric_expression(tmp_path: Path):
    """Method body evaluates a numeric expression."""
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(x: Int) -> Int { x + 1 }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p, args={"x": 5})
    result = execute_runtime(cfg)
    assert isinstance(result, Ok)
    assert result.ok_value == "6"


def test_execute_tool_env_access(tmp_path: Path, monkeypatch):
    """Tool body can read environment variables via ``env.VAR``."""
    monkeypatch.setenv("TEST_API_URL", "http://test.local/api")

    source = '''tool GetEndpoint() -> Str {
        env.TEST_API_URL
    }

    agent Bot {
        model: @mock/model
        tools: [GetEndpoint]
        fn run() -> Str {
            act GetEndpoint()
        }
    }'''
    p = _write_temp(source, tmp_path)
    cfg = RuntimeConfig(source_path=p)
    result = execute_runtime(cfg)
    assert isinstance(result, Ok)
    assert result.ok_value == "http://test.local/api"


def test_execute_tool_http_get(tmp_path: Path):
    """Tool body can call ``http.get`` and return parsed JSON."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "hi"}).encode())

        def log_message(self, *args):
            pass  # silence logs

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        source = f'''tool Fetch(url: Str) -> Str {{
            http.get(url)
        }}

        agent Bot {{
            model: @mock/model
            tools: [Fetch]
            fn run() -> Str {{
                act Fetch(url: "http://127.0.0.1:{port}/api")
            }}
        }}'''
        p = _write_temp(source, tmp_path)
        cfg = RuntimeConfig(source_path=p)
        result = execute_runtime(cfg)
        assert isinstance(result, Ok)
        # http.get auto-parses JSON, so result is the parsed dict
        assert result.ok_value == "{'message': 'hi'}"
    finally:
        server.shutdown()
