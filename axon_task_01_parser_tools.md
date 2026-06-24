# AXON Task #01 — AST Nodes + Tool Declaration Parser
> Hand this ticket to any capable coding model. It is fully self-contained.

---

## BACKGROUND

AXON is a new programming language for AI agent systems. It has a `.ax` file format.
We are building a Python-based compiler/transpiler for it. This task covers the first
two modules: the data structures (AST nodes) and the parser for `tool` declarations.

---

## WHAT TO BUILD

Two Python files:

1. `src/axon/ast_nodes.py` — dataclass definitions for the AXON AST
2. `src/axon/parser.py` — a parser that reads a `.ax` source string and returns a list of AST nodes

For this ticket, the parser only needs to handle **`tool` declarations**.
Agent, flow, and RAG declarations come in later tickets.

---

## INTERFACE

### ast_nodes.py

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Param:
    name: str
    type_str: str                    # raw AXON type string e.g. "Str", "List<Int>", "Int = 5"
    default: Optional[str] = None    # default value as string, or None

@dataclass
class Annotation:
    name: str                        # e.g. "budget", "schedule", "trace"
    args: dict[str, str] = field(default_factory=dict)  # e.g. {"tokens": "600"}

@dataclass
class ToolDecl:
    name: str
    params: list[Param]
    return_type: str                 # raw AXON return type string
    docstrings: list[str]            # lines from /// comments inside the body
    body: str                        # raw body text (non-docstring lines)
    annotations: list[Annotation] = field(default_factory=list)
    line: int = 0                    # source line number

@dataclass
class ImportDecl:
    names: list[str]                 # e.g. ["WebSearch", "WebFetch"]
    source: str                      # e.g. "axon:tools/web"
```

### parser.py

```python
def parse(source: str) -> list:
    """
    Parse AXON source text. Returns a list of declaration objects.
    For this ticket: returns list of ToolDecl and ImportDecl.
    Raises SyntaxError with line number on parse failure.
    """
    ...

def parse_tool(source: str, start: int) -> tuple[ToolDecl, int]:
    """
    Parse one tool declaration starting at position `start` in `source`.
    `start` points to the 't' of 'tool'.
    Returns (ToolDecl, position_after_closing_brace).
    """
    ...

def parse_params(params_str: str) -> list[Param]:
    """
    Parse a parameter list string like:
      "repo: Str, issue_number: Int, label: \"low\"|\"high\" = \"low\""
    Returns list of Param.
    """
    ...
```

---

## AXON SYNTAX TO HANDLE

### Tool declaration syntax
```
tool ToolName(param1: Type, param2: Type = default) -> ReturnType {
    /// First docstring line.
    /// Second docstring line.
    body_expression
}
```

### Annotations before tool declarations (optional)
```
@retry(max: 3, backoff: 1000)
@cache(ttl: 300)
tool ToolName(...) -> ReturnType { ... }
```

### Import statements
```
import { WebSearch, WebFetch } from "axon:tools/web"
import WebSearch from "axon:tools/web"
```

### Type expressions you must handle
- Simple: `Str`, `Int`, `Float`, `Bool`, `Any`
- Generic: `List<Str>`, `Map<Str, Int>`, `Result<List<Any>, ToolError>`, `Option<Str>`
- Literal union: `"low" | "medium" | "high"` — treat as a string type
- Unit: `()`

### Comments to ignore
```
// This is a regular comment — skip it
/// This is a docstring — capture it (strip the ///)
```

---

## INPUT → OUTPUT EXAMPLES

### Example 1 — Simple tool

Input `.ax` text:
```
tool FetchIssues(repo: Str) -> Result<List<Any>, ToolError> {
    /// Fetches open issues from a GitHub repository.
    /// Use to find new issues that need triage.
    http.get("https://api.github.com/repos/{repo}/issues?state=open")
}
```

Expected output:
```python
ToolDecl(
    name="FetchIssues",
    params=[Param(name="repo", type_str="Str", default=None)],
    return_type="Result<List<Any>, ToolError>",
    docstrings=[
        "Fetches open issues from a GitHub repository.",
        "Use to find new issues that need triage."
    ],
    body='http.get("https://api.github.com/repos/{repo}/issues?state=open")',
    annotations=[],
    line=1
)
```

### Example 2 — Tool with defaults and annotation

Input:
```
@cache(ttl: 300)
tool WebSearch(query: Str, max_results: Int = 5) -> List<Any> {
    /// Searches the web for current information.
    http.get("https://api.search.com/v1?q={query}&n={max_results}")
}
```

Expected output:
```python
ToolDecl(
    name="WebSearch",
    params=[
        Param(name="query", type_str="Str", default=None),
        Param(name="max_results", type_str="Int", default="5")
    ],
    return_type="List<Any>",
    docstrings=["Searches the web for current information."],
    body='http.get("https://api.search.com/v1?q={query}&n={max_results}")',
    annotations=[Annotation(name="cache", args={"ttl": "300"})],
    line=1
)
```

### Example 3 — Import statement

Input:
```
import { WebSearch, WebFetch } from "axon:tools/web"
```

Expected output:
```python
ImportDecl(names=["WebSearch", "WebFetch"], source="axon:tools/web")
```

### Example 4 — Multiple declarations in one file

Input:
```
import { ReadFile } from "axon:tools/fs"

tool ReadConfig(path: Str) -> Result<Str, ToolError> {
    /// Reads a configuration file from disk.
    fs.read(path)
}

// A regular comment — ignore this
tool WriteLog(message: Str, level: "info" | "warn" | "error" = "info") -> Result<(), ToolError> {
    /// Appends a message to the application log.
    /// Use for structured logging.
    fs.append("./app.log", "{level}: {message}")
}
```

Expected: list of [ImportDecl, ToolDecl("ReadConfig"), ToolDecl("WriteLog")]
- WriteLog params: `[Param("message", "Str"), Param("level", '"info" | "warn" | "error"', default='"info"')]`

---

## RULES & CONSTRAINTS

1. **No external parsing libraries.** Use Python stdlib only (re, dataclasses, typing). No lark, no parsimonious, no antlr.
2. **Brace counting for bodies.** Tool bodies may contain nested `{}`. Use a depth counter, not regex, to find the matching `}`.
3. **Preserve raw text.** `body` and `type_str` fields store the raw AXON text — don't transform them.
4. **Line number tracking.** Set `line` to the 1-based line number where the `tool` keyword appears.
5. **Skip regular comments.** Lines starting with `//` (but not `///`) are ignored entirely.
6. **Capture docstrings.** Lines starting with `///` inside a tool body become `docstrings` entries (stripped of the `///` prefix and leading space).
7. **Handle trailing commas gracefully.** `parse_params("repo: Str,")` should not crash.
8. **Raise SyntaxError** with a helpful message and line number when the source is malformed.
9. **Generic types with nested `<>`** must parse correctly. `Result<List<Any>, ToolError>` is one type, not multiple.

---

## DEPENDENCIES

```toml
# No external dependencies for this task.
# Python 3.11+ stdlib only.
```

---

## TEST CASES

Write a `tests/test_parser.py` file with at least these tests using pytest:

```python
def test_simple_tool():
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}
'''
    decls = parse(source)
    assert len(decls) == 1
    t = decls[0]
    assert isinstance(t, ToolDecl)
    assert t.name == "Greet"
    assert len(t.params) == 1
    assert t.params[0].name == "name"
    assert t.params[0].type_str == "Str"
    assert t.return_type == "Str"
    assert t.docstrings == ["Says hello."]

def test_tool_with_default_param():
    source = '''
tool Search(query: Str, max: Int = 5) -> List<Any> {
    /// Searches.
    http.get(query)
}
'''
    decls = parse(source)
    assert decls[0].params[1].default == "5"

def test_nested_generic_return_type():
    source = '''
tool Fetch(url: Str) -> Result<List<Any>, ToolError> {
    /// Fetches data.
    http.get(url)
}
'''
    decls = parse(source)
    assert decls[0].return_type == "Result<List<Any>, ToolError>"

def test_multiple_docstring_lines():
    source = '''
tool Do(x: Int) -> Int {
    /// First line.
    /// Second line.
    /// Third line.
    x + 1
}
'''
    decls = parse(source)
    assert decls[0].docstrings == ["First line.", "Second line.", "Third line."]

def test_import_named():
    source = 'import { A, B, C } from "axon:tools/web"'
    decls = parse(source)
    assert isinstance(decls[0], ImportDecl)
    assert decls[0].names == ["A", "B", "C"]
    assert decls[0].source == "axon:tools/web"

def test_multiple_tools_in_file():
    source = '''
tool A(x: Str) -> Str { /// Doc A. x }
tool B(y: Int) -> Int { /// Doc B. y }
'''
    decls = parse(source)
    assert len(decls) == 2
    assert decls[0].name == "A"
    assert decls[1].name == "B"

def test_annotation_on_tool():
    source = '''
@cache(ttl: 300)
tool Cached(key: Str) -> Str {
    /// Gets cached value.
    cache.get(key)
}
'''
    decls = parse(source)
    assert decls[0].annotations[0].name == "cache"
    assert decls[0].annotations[0].args["ttl"] == "300"

def test_literal_union_type_param():
    source = '''
tool Log(msg: Str, level: "info" | "warn" | "error" = "info") -> () {
    /// Logs a message.
    logger.log(level, msg)
}
'''
    decls = parse(source)
    assert '"info" | "warn" | "error"' in decls[0].params[1].type_str
    assert decls[0].params[1].default == '"info"'

def test_regular_comments_ignored():
    source = '''
// This comment should be ignored
tool Thing(x: Str) -> Str {
    // This too
    /// But not this — it is a docstring.
    x
}
'''
    decls = parse(source)
    assert decls[0].docstrings == ["But not this — it is a docstring."]
    assert "This comment" not in decls[0].body
```

---

## DELIVERABLES

- `src/axon/ast_nodes.py`
- `src/axon/parser.py`
- `tests/test_parser.py`

All 9 test cases must pass with `pytest tests/test_parser.py`.

Python 3.11+. No external dependencies beyond stdlib.
