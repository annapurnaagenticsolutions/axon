"""Tests for the sandbox tool module — restricted Python execution."""

from __future__ import annotations

import pytest

from axon.sandbox_client import SandboxClient, SandboxResult, sandbox_builtins


# ── Basic execution ─────────────────────────────────────────────────────────


class TestRun:
    def test_run_simple_print(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('print("hello world")')
        assert result.success
        assert "hello world" in result.stdout

    def test_run_arithmetic(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('print(2 + 3)')
        assert result.success
        assert "5" in result.stdout

    def test_run_returns_exit_code(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('print("ok")')
        assert result.returncode == 0

    def test_run_syntax_error(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('print("unterminated')
        assert not result.success
        assert result.returncode != 0

    def test_run_runtime_error(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('x = 1 / 0')
        assert not result.success
        assert result.returncode != 0

    def test_run_with_variables(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('x = 10\ny = 20\nprint(x + y)')
        assert result.success
        assert "30" in result.stdout

    def test_run_list_comprehension(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('print([i*i for i in range(5)])')
        assert result.success
        assert "[0, 1, 4, 9, 16]" in result.stdout


# ── Blocked modules ─────────────────────────────────────────────────────────


class TestBlockedModules:
    def test_os_blocked(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('import os\nprint(os.getcwd())')
        assert not result.success

    def test_subprocess_blocked(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('import subprocess\nsubprocess.run(["echo", "hi"])')
        assert not result.success

    def test_socket_blocked(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('import socket\nsocket.socket()')
        assert not result.success

    def test_math_allowed(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('import math\nprint(math.sqrt(16))')
        assert result.success
        assert "4" in result.stdout

    def test_json_allowed(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('import json\nprint(json.dumps({"a": 1}))')
        assert result.success
        assert '{"a": 1}' in result.stdout

    def test_re_allowed(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('import re\nprint(re.findall(r"\\d+", "abc123def456"))')
        assert result.success
        assert "123" in result.stdout


# ── Timeout ─────────────────────────────────────────────────────────────────


class TestTimeout:
    def test_timeout_raises(self):
        client = SandboxClient(timeout_seconds=1)
        result = client.run('import time\ntime.sleep(10)')
        assert result.timed_out
        assert not result.success

    def test_completes_within_timeout(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.run('print("fast")')
        assert not result.timed_out
        assert result.success


# ── Eval ────────────────────────────────────────────────────────────────────


class TestEval:
    def test_eval_simple_expression(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.eval("1 + 2")
        assert result == 3

    def test_eval_string(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.eval('"hello".upper()')
        assert result == "HELLO"

    def test_eval_list(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.eval("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_eval_dict(self):
        client = SandboxClient(timeout_seconds=5)
        result = client.eval('{"a": 1, "b": 2}')
        assert result == {"a": 1, "b": 2}


# ── SandboxResult ───────────────────────────────────────────────────────────


class TestSandboxResult:
    def test_success_true(self):
        r = SandboxResult(stdout="ok", stderr="", returncode=0)
        assert r.success is True

    def test_success_false_on_error(self):
        r = SandboxResult(stdout="", stderr="error", returncode=1)
        assert r.success is False

    def test_success_false_on_timeout(self):
        r = SandboxResult(stdout="", stderr="", returncode=-1, timed_out=True)
        assert r.success is False

    def test_to_dict(self):
        r = SandboxResult(stdout="out", stderr="err", returncode=0)
        d = r.to_dict()
        assert d["stdout"] == "out"
        assert d["stderr"] == "err"
        assert d["returncode"] == 0
        assert d["success"] is True
        assert d["timed_out"] is False


# ── Builtins ────────────────────────────────────────────────────────────────


class TestBuiltins:
    def test_sandbox_builtins_returns_client(self):
        builtins = sandbox_builtins(timeout_seconds=3)
        assert "sandbox" in builtins
        assert isinstance(builtins["sandbox"], SandboxClient)

    def test_sandbox_builtins_custom_timeout(self):
        builtins = sandbox_builtins(timeout_seconds=10)
        assert builtins["sandbox"]._timeout == 10
