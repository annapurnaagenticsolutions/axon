"""Syntax diagnostics for AXON source files.

Task #18 keeps parser behavior deterministic while making parser failures easier
for humans to act on. The parser still raises ``SyntaxError`` at the first hard
failure. This module wraps that failure with source location, snippet, caret,
and a small set of AXON-specific hints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import re
from typing import Any

from axon.parser import parse


@dataclass(frozen=True)
class SyntaxDiagnostic:
    """A user-facing syntax diagnostic for one AXON source problem."""

    message: str
    line: int
    column: int
    severity: str = "error"
    filename: str | None = None
    snippet: str = ""
    pointer: str = ""
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }
        if self.filename is not None:
            data["filename"] = self.filename
        if self.snippet:
            data["snippet"] = self.snippet
        if self.pointer:
            data["pointer"] = self.pointer
        if self.hint:
            data["hint"] = self.hint
        return data

    def format(self) -> str:
        location = f"{self.line}:{self.column}"
        if self.filename:
            location = f"{self.filename}:{location}"

        lines = [f"{self.severity}: {self.message} ({location})"]
        if self.snippet:
            line_no = str(self.line)
            lines.append(f" {line_no} | {self.snippet}")
            if self.pointer:
                lines.append(f" {' ' * len(line_no)} | {self.pointer}")
        if self.hint:
            lines.append(f"hint: {self.hint}")
        return "\n".join(lines)


@dataclass(frozen=True)
class SyntaxCheckResult:
    """Result of a non-throwing syntax check."""

    ok: bool
    declarations: list = field(default_factory=list)
    diagnostics: list[SyntaxDiagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def format(self) -> str:
        if self.ok:
            count = len(self.declarations)
            noun = "declaration" if count == 1 else "declarations"
            return f"OK: parsed {count} {noun}"
        return "\n".join(diagnostic.format() for diagnostic in self.diagnostics)


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int
    offset: int


def check_syntax(source: str, filename: str | None = None) -> SyntaxCheckResult:
    """Parse AXON source without raising SyntaxError.

    On success the parsed declarations are returned. On failure a single rich
    diagnostic is returned. Phase 1 still intentionally stops on the first hard
    parser error rather than attempting unsafe partial AST recovery.
    """

    try:
        declarations = parse(source)
    except SyntaxError as exc:
        diagnostic = diagnostic_from_syntax_error(source, exc, filename=filename)
        return SyntaxCheckResult(ok=False, declarations=[], diagnostics=[diagnostic])
    return SyntaxCheckResult(ok=True, declarations=declarations, diagnostics=[])


def check_syntax_file(path: str | Path) -> SyntaxCheckResult:
    """Read and syntax-check one AXON source file."""

    source_path = Path(path)
    text = source_path.read_text(encoding="utf-8")
    return check_syntax(text, filename=str(source_path))


def diagnostic_from_syntax_error(
    source: str,
    error: SyntaxError,
    filename: str | None = None,
) -> SyntaxDiagnostic:
    """Convert a parser SyntaxError into a rich source diagnostic."""

    message = str(error) or "Syntax error"
    line = _extract_line_from_message(message) or 1
    line = max(1, min(line, max(1, len(source.splitlines()) or 1)))

    column = _infer_column(source, message, line)
    snippet = _line_at(source, line)
    pointer = _caret_pointer(snippet, column)
    hint = _suggest_hint(message, snippet)

    return SyntaxDiagnostic(
        message=message,
        line=line,
        column=column,
        filename=filename,
        snippet=snippet,
        pointer=pointer,
        hint=hint,
    )


def diagnostics_to_json(diagnostics: list[SyntaxDiagnostic]) -> str:
    """Serialize syntax diagnostics as stable JSON."""

    return json.dumps([diagnostic.to_dict() for diagnostic in diagnostics], indent=2, sort_keys=True)


def result_to_json(result: SyntaxCheckResult) -> str:
    """Serialize a SyntaxCheckResult as stable JSON."""

    return result.to_json()


def _extract_line_from_message(message: str) -> int | None:
    # Prefer the last explicit "line N" mention because nested helper errors can
    # include both a declaration line and a local body line.
    matches = re.findall(r"line\s+(\d+)", message)
    if not matches:
        return None
    return int(matches[-1])


def _infer_column(source: str, message: str, line: int) -> int:
    line_text = _line_at(source, line)
    if not line_text:
        return 1

    # Messages shaped as: Unexpected token at line N: <token preview>
    token_match = re.search(r"Unexpected token(?:[^:]*):\s*(.+)$", message)
    if token_match:
        token = token_match.group(1).strip()
        if token:
            needle = token.splitlines()[0][:30].strip()
            if needle:
                idx = line_text.find(needle)
                if idx >= 0:
                    return idx + 1

    # Common field / declaration messages: place the caret on the keyword when
    # it is visible in the source line.
    keywords = [
        "agent",
        "tool",
        "prompt",
        "rag",
        "flow",
        "type",
        "stage",
        "fn",
        "model",
        "tools",
        "memory",
        "source",
        "chunker",
        "embedder",
        "store",
    ]
    lowered = message.lower()
    for keyword in keywords:
        if keyword in lowered:
            idx = _find_word(line_text, keyword)
            if idx >= 0:
                return idx + 1

    stripped_len = len(line_text) - len(line_text.lstrip())
    return stripped_len + 1


def _line_at(source: str, line: int) -> str:
    lines = source.splitlines()
    if not lines:
        return ""
    if line < 1:
        return lines[0]
    if line > len(lines):
        return lines[-1]
    return lines[line - 1]


def _caret_pointer(snippet: str, column: int) -> str:
    if not snippet:
        return "^"
    safe_column = max(1, min(column, len(snippet) + 1))
    return " " * (safe_column - 1) + "^"


def _find_word(text: str, word: str) -> int:
    match = re.search(rf"\b{re.escape(word)}\b", text)
    return match.start() if match else -1


def _suggest_hint(message: str, snippet: str) -> str | None:
    lowered = message.lower()
    stripped = snippet.strip()

    if "expected '->'" in lowered:
        return "Function-like declarations must use `-> ReturnType` before the body."
    if "expected return type" in lowered:
        return "Add an explicit AXON return type such as `Str`, `Result<Str, AgentError>`, or `()`."
    if "expected '{'" in lowered:
        return "Open the declaration body with `{` after the return type or declaration header."
    if "unclosed" in lowered:
        return "Check for a missing closing delimiter or an unmatched delimiter inside a string/body."
    if "malformed annotation" in lowered:
        return "Annotations use `@name` or `@name(key: value, other: value)` syntax."
    if "malformed parameter" in lowered or "missing type for parameter" in lowered:
        return "Parameters use `name: Type` and optional defaults use `name: Type = value`."
    if "memory" in lowered and "malformed" in lowered:
        return "Memory declarations use `memory: Memory<ShortTerm>` or `memory: Memory<ShortTerm>(capacity: 1000)`."
    if "tools" in lowered:
        return "Tool lists use square brackets, for example `tools: [WebSearch, ProductDocs.retrieve]`."
    if "missing required model" in lowered:
        return "Every agent needs `model: @provider/model-name` or `model: env.DEFAULT_MODEL`."
    if "unexpected token" in lowered:
        typo = _keyword_typo_hint(stripped)
        if typo:
            return typo
        return "Top-level AXON declarations currently start with `import`, `type`, `prompt`, `rag`, `flow`, `tool`, `agent`, or an annotation."
    return None


def _keyword_typo_hint(stripped_line: str) -> str | None:
    if not stripped_line:
        return None
    first = re.split(r"\s+", stripped_line, maxsplit=1)[0]
    known = ["agent", "tool", "prompt", "rag", "flow", "type", "import"]
    best: tuple[int, str] | None = None
    for keyword in known:
        distance = _levenshtein(first, keyword)
        if best is None or distance < best[0]:
            best = (distance, keyword)
    if best and best[0] <= 2:
        return f"Did you mean `{best[1]}`?"
    return None


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(
                min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            )
        prev = curr
    return prev[-1]
