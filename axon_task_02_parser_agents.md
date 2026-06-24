# AXON Task #02 — Agent Declaration Parser
> Depends on Task #01 being complete. Hand this ticket to any capable coding model.

---

## BACKGROUND

AXON is a new AI-native programming language. We are building a Python transpiler for it.
Task #01 produced `ast_nodes.py` (dataclasses) and `parser.py` (parses `tool` blocks).
This task extends the parser to also handle `agent` declarations.

---

## WHAT TO BUILD

Extend `src/axon/ast_nodes.py` with new dataclasses, and extend `src/axon/parser.py`
to parse `agent` declaration blocks.

Do NOT modify existing dataclasses or parser functions — only add new ones.

---

## INTERFACE

### New dataclasses to add to ast_nodes.py

```python
@dataclass
class MemoryDecl:
    kind: str                        # "ShortTerm", "Semantic", "Episodic"
    options: dict[str, str] = field(default_factory=dict)
    # e.g. Memory<ShortTerm>(capacity: 2000) → kind="ShortTerm", options={"capacity": "2000"}

@dataclass
class MethodDecl:
    name: str
    params: list[Param]              # reuse Param from Task #01
    return_type: str
    annotations: list[Annotation]   # reuse Annotation from Task #01
    body: str                        # raw body text

@dataclass
class AgentDecl:
    name: str
    model: str                       # e.g. "@anthropic/claude-haiku"
    tools: list[str]                 # e.g. ["FetchIssues", "AddLabel"]
    memory: Optional[MemoryDecl]
    annotations: list[Annotation]
    methods: list[MethodDecl]
    line: int = 0
```

### New function to add to parser.py

```python
def parse_agent(source: str, start: int) -> tuple[AgentDecl, int]:
    """
    Parse one agent declaration starting at position `start`.
    `start` points to the 'a' of 'agent'.
    Returns (AgentDecl, position_after_closing_brace).
    """
    ...
```

Also update `parse()` to return `AgentDecl` instances alongside `ToolDecl` and `ImportDecl`.

---

## AXON AGENT SYNTAX

```axon
agent AgentName {
    model: @provider/model-name
    tools: [Tool1, Tool2, Tool3.retrieve]
    memory: Memory<ShortTerm>
    memory: Memory<ShortTerm>(capacity: 2000)
    memory: Memory<Semantic>(store: VectorDB::postgres(env.PG_URL))

    @schedule(every: 5.minutes)
    @trace
    fn method_name(param1: Str, param2: Int = 0) -> Result<(), AgentError> {
        // method body — capture as raw text
        let x = act SomeTool(param: param1)?
        store memory.working["key"] = x
        Ok(())
    }

    fn another_method(input: Str) -> Result<Report, AgentError> {
        @plan(input)
    }
}
```

### Model field variants
```axon
model: @anthropic/claude-4
model: @anthropic/claude-haiku
model: @openai/gpt-4o
model: @ollama/llama3
model: env.DEFAULT_MODEL
```

### Tools field variants
```axon
tools: [FetchIssues, AddLabel, AssignIssue]
tools: [ProductDocs.retrieve, CreateTicket]   // dot-access allowed
tools: []                                      // empty list allowed
```

### Memory field variants
```axon
memory: Memory<ShortTerm>
memory: Memory<ShortTerm>(capacity: 2000)
memory: Memory<ShortTerm>(capacity: 2000.tokens)
memory: Memory<Semantic>
memory: Memory<Episodic>(max_events: 10000)
```

### Annotations on agent (before the `agent` keyword)
```axon
@managed
agent LongRunningAgent { ... }
```

### Annotations on methods (before the `fn` keyword)
```axon
@schedule(every: 5.minutes)
@trace
@budget(tokens: 4000)
fn watch(repo: Str) -> Result<(), AgentError> { ... }
```

---

## INPUT → OUTPUT EXAMPLES

### Example 1 — Minimal agent

Input:
```axon
agent SimpleAgent {
    model: @anthropic/claude-4
    tools: [WebSearch]

    fn run(query: Str) -> Result<Str, AgentError> {
        let result = act WebSearch(query: query)?
        Ok(result)
    }
}
```

Expected:
```python
AgentDecl(
    name="SimpleAgent",
    model="@anthropic/claude-4",
    tools=["WebSearch"],
    memory=None,
    annotations=[],
    methods=[
        MethodDecl(
            name="run",
            params=[Param(name="query", type_str="Str", default=None)],
            return_type="Result<Str, AgentError>",
            annotations=[],
            body="let result = act WebSearch(query: query)?\nOk(result)"
        )
    ],
    line=1
)
```

### Example 2 — Agent with memory and annotations on method

Input:
```axon
agent MonitorAgent {
    model: @anthropic/claude-haiku
    tools: [FetchMetrics, SendAlert]
    memory: Memory<ShortTerm>(capacity: 500)

    @schedule(every: 5.minutes)
    @trace
    fn watch(endpoint: Str) -> Result<(), AgentError> {
        let metrics = act FetchMetrics(endpoint: endpoint)?
        store memory.append(metrics)
        Ok(())
    }
}
```

Expected:
```python
AgentDecl(
    name="MonitorAgent",
    model="@anthropic/claude-haiku",
    tools=["FetchMetrics", "SendAlert"],
    memory=MemoryDecl(kind="ShortTerm", options={"capacity": "500"}),
    annotations=[],
    methods=[
        MethodDecl(
            name="watch",
            params=[Param(name="endpoint", type_str="Str")],
            return_type="Result<(), AgentError>",
            annotations=[
                Annotation(name="schedule", args={"every": "5.minutes"}),
                Annotation(name="trace", args={})
            ],
            body="let metrics = act FetchMetrics(endpoint: endpoint)?\nstore memory.append(metrics)\nOk(())"
        )
    ]
)
```

### Example 3 — Agent with dot-access tool reference and env model

Input:
```axon
agent SupportAgent {
    model: env.DEFAULT_MODEL
    tools: [ProductDocs.retrieve, CreateTicket]

    fn handle(question: Str) -> Result<Str, AgentError> {
        Ok("answer")
    }
}
```

Expected:
```python
AgentDecl(
    name="SupportAgent",
    model="env.DEFAULT_MODEL",
    tools=["ProductDocs.retrieve", "CreateTicket"],
    memory=None,
    ...
)
```

---

## RULES & CONSTRAINTS

1. **No external libraries.** Python stdlib only. Reuse helpers from Task #01.
2. **Brace counting for method bodies.** Method bodies may contain nested `{}`.
3. **Tools list:** preserve dot-access notation as-is e.g. `"ProductDocs.retrieve"`.
4. **Method body:** capture as raw stripped text. Do not parse expressions inside.
5. **Memory options:** parse key-value pairs inside `(capacity: 2000)` into a dict. Values are strings.
6. **Annotations on methods:** collect ALL `@annotation` lines immediately before `fn` as that method's annotations list.
7. **Annotations on agent:** collect ALL `@annotation` lines immediately before `agent` as the agent's annotations list.
8. **Multiple methods:** an agent can have zero or more `fn` declarations.
9. **Raise SyntaxError** with line number when malformed.
10. **`parse()` now returns** a list that may contain `ImportDecl`, `ToolDecl`, and `AgentDecl` — all mixed.

---

## DEPENDENCIES

None beyond Python 3.11+ stdlib and the output of Task #01.

---

## TEST CASES

Add to `tests/test_parser.py`:

```python
def test_simple_agent():
    source = '''
agent Bot {
    model: @anthropic/claude-4
    tools: [Search]

    fn run(q: Str) -> Result<Str, AgentError> {
        Ok(q)
    }
}
'''
    decls = parse(source)
    assert len(decls) == 1
    a = decls[0]
    assert isinstance(a, AgentDecl)
    assert a.name == "Bot"
    assert a.model == "@anthropic/claude-4"
    assert a.tools == ["Search"]
    assert a.memory is None
    assert len(a.methods) == 1
    assert a.methods[0].name == "run"

def test_agent_with_memory():
    source = '''
agent Mem {
    model: @openai/gpt-4o
    tools: []
    memory: Memory<ShortTerm>(capacity: 1000)

    fn go() -> Result<(), AgentError> { Ok(()) }
}
'''
    decls = parse(source)
    assert decls[0].memory.kind == "ShortTerm"
    assert decls[0].memory.options["capacity"] == "1000"

def test_method_annotations():
    source = '''
agent Sched {
    model: @anthropic/claude-haiku
    tools: []

    @schedule(every: 10.minutes)
    @trace
    fn watch(ep: Str) -> Result<(), AgentError> { Ok(()) }
}
'''
    decls = parse(source)
    method = decls[0].methods[0]
    assert len(method.annotations) == 2
    assert method.annotations[0].name == "schedule"
    assert method.annotations[0].args["every"] == "10.minutes"
    assert method.annotations[1].name == "trace"

def test_agent_multiple_methods():
    source = '''
agent Multi {
    model: @anthropic/claude-4
    tools: [T1, T2]

    fn a(x: Str) -> Str { x }
    fn b(y: Int) -> Int { y }
}
'''
    decls = parse(source)
    assert len(decls[0].methods) == 2

def test_tools_dot_access():
    source = '''
agent Doc {
    model: @anthropic/claude-4
    tools: [KnowledgeBase.retrieve, CreateTicket]

    fn run(q: Str) -> Str { q }
}
'''
    decls = parse(source)
    assert "KnowledgeBase.retrieve" in decls[0].tools

def test_mixed_file():
    source = '''
import { Search } from "axon:tools/web"

tool Fetch(url: Str) -> Str {
    /// Fetches a URL.
    http.get(url)
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Fetch, Search]

    fn run(q: Str) -> Result<Str, AgentError> { Ok(q) }
}
'''
    decls = parse(source)
    assert len(decls) == 3
    assert isinstance(decls[0], ImportDecl)
    assert isinstance(decls[1], ToolDecl)
    assert isinstance(decls[2], AgentDecl)
```

---

## DELIVERABLES

- Updated `src/axon/ast_nodes.py` (new dataclasses added)
- Updated `src/axon/parser.py` (parse_agent + updated parse)
- Updated `tests/test_parser.py` (new tests added)

All tests (Task #01 + Task #02) must pass with `pytest tests/`.
