"""Sandbox client for AXON tool dispatch.

Provides ``sandbox.run`` and ``sandbox.eval`` builtins that AXON ``tool``
bodies can call to execute restricted Python code in a safe subprocess.

The sandbox uses ``subprocess`` with a restricted builtins environment,
timeout enforcement, and output capture.  Dangerous modules (``os``,
``subprocess``, ``socket``, ``ctypes``, etc.) are blocked by default.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from typing import Any


# Modules blocked by default in the sandbox
_DEFAULT_BLOCKED_MODULES = frozenset({
    "os",
    "subprocess",
    "socket",
    "ctypes",
    "shutil",
    "tempfile",
    "multiprocessing",
    "threading",
    "signal",
    "fcntl",
    "pty",
    "asyncio",
    "http",
    "urllib",
    "xmlrpc",
    "pickle",
    "marshal",
    "importlib",
    "builtins",
})

# Builtins allowed in the sandbox
_ALLOWED_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "getattr", "hasattr", "hash", "hex",
    "id", "int", "isinstance", "issubclass", "iter", "len", "list", "map",
    "max", "min", "next", "oct", "ord", "pow", "print", "range", "repr",
    "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple",
    "type", "zip", "True", "False", "None",
    # Exception types needed for try/except
    "BaseException", "Exception", "ValueError", "TypeError", "KeyError",
    "IndexError", "ZeroDivisionError", "StopIteration", "AttributeError",
    "NameError", "RuntimeError", "ImportError", "OverflowError",
})


@dataclass
class SandboxResult:
    """Result of a sandbox execution."""

    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """Whether the execution succeeded."""
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "success": self.success,
        }


class SandboxClient:
    """Restricted Python execution sandbox for AXON tool bodies.

    Executes Python code in a subprocess with:
    - Restricted builtins (no ``__import__``, ``exec``, ``eval``, ``open``, etc.)
    - Blocked dangerous modules
    - Timeout enforcement
    - stdout/stderr capture
    """

    def __init__(
        self,
        timeout_seconds: float = 5.0,
        max_output_chars: int = 10000,
        blocked_modules: frozenset[str] | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_output = max_output_chars
        self._blocked = blocked_modules or _DEFAULT_BLOCKED_MODULES

    def _build_script(self, code: str) -> str:
        """Wrap user code in a sandbox preamble."""
        allowed = ", ".join(f"'{b}'" for b in sorted(_ALLOWED_BUILTINS))
        blocked_checks = " or ".join(
            f"name == '{m}'" for m in sorted(self._blocked)
        )
        return (
            "import sys\n"
            "\n"
            "# --- Sandbox preamble ---\n"
            "# Save original builtins\n"
            "_orig_bi = __builtins__\n"
            "if isinstance(_orig_bi, type(sys)):\n"
            "    _bi = vars(_orig_bi)\n"
            "else:\n"
            "    _bi = dict(_orig_bi)\n"
            "\n"
            f"_allowed = {{{allowed}}}\n"
            "_safe = {k: _bi[k] for k in _allowed if k in _bi}\n"
            "\n"
            "# Safe import that blocks dangerous modules\n"
            "_real_import = _bi['__import__']\n"
            "\n"
            "def _safe_import(name, *args, **kwargs):\n"
            f"    if {blocked_checks}:\n"
            '        raise ImportError(f"Blocked module: {name}")\n'
            "    return _real_import(name, *args, **kwargs)\n"
            "\n"
            '_safe["__import__"] = _safe_import\n'
            '_safe["__name__"] = "__sandbox__"\n'
            "\n"
            "# --- User code (executed with restricted builtins) ---\n"
            "try:\n"
            f"    exec({code!r}, {{'__builtins__': _safe}})\n"
            "except Exception as e:\n"
            '    print(f"Error: {e}", file=sys.stderr)\n'
            "    sys.exit(1)\n"
        )

    def run(self, code: str) -> SandboxResult:
        """Execute Python code in the sandbox and return the result.

        Args:
            code: Python source code to execute.

        Returns:
            SandboxResult with stdout, stderr, returncode, and timed_out flag.
        """
        script = self._build_script(code)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            stdout = proc.stdout[: self._max_output]
            stderr = proc.stderr[: self._max_output]
            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                returncode=proc.returncode,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or "")[: self._max_output] if isinstance(e.stdout, str) else ""
            stderr = (e.stderr or "")[: self._max_output] if isinstance(e.stderr, str) else ""
            return SandboxResult(
                stdout=stdout,
                stderr=stderr + "\nExecution timed out",
                returncode=-1,
                timed_out=True,
            )
        finally:
            import os
            os.unlink(script_path)

    def eval(self, expr: str) -> Any:
        """Evaluate a Python expression in the sandbox and return the result.

        Unlike ``run``, this captures the value of the last expression and
        returns it as a Python value via stdout JSON.

        Args:
            expr: Python expression to evaluate.

        Returns:
            The result of the expression (parsed from stdout JSON).
        """
        import json

        code = f"""
import json as _json
_result = ({expr})
print(_json.dumps(_result, default=str))
"""
        result = self.run(code)
        if result.success and result.stdout.strip():
            try:
                return json.loads(result.stdout.strip().split("\n")[-1])
            except json.JSONDecodeError:
                return result.stdout.strip()
        return result.to_dict()


def sandbox_builtins(
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Return the ``sandbox`` builtin to inject into tool scopes."""
    return {"sandbox": SandboxClient(timeout_seconds=timeout_seconds)}
