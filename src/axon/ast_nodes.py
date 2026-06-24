from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from axon.expression_ast import Expr


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
    parsed_body: Optional["Expr"] = None  # parsed expression AST (optional, for static analysis)


@dataclass
class ImportDecl:
    names: list[str]                 # e.g. ["WebSearch", "WebFetch"]
    source: str                      # e.g. "axon:tools/web"


@dataclass
class TypeAliasDecl:
    name: str                        # e.g. "Issue", "PagedList"
    type_params: list[str]           # e.g. ["T"] for type PagedList<T>
    value: str                       # raw AXON right-hand side e.g. "Int", "{ id: Int }"
    fields: list[Param] = field(default_factory=list)  # parsed record fields when value is {...}
    line: int = 0                    # source line number




@dataclass
class PromptDecl:
    name: str
    params: list[Param]              # typed prompt inputs
    return_type: str                 # raw AXON return type string
    template: str                    # dedented template body from triple-quoted prompt block
    annotations: list[Annotation] = field(default_factory=list)
    line: int = 0                    # source line number

@dataclass
class MemoryDecl:
    kind: str                        # "ShortTerm", "Semantic", "Episodic"
    options: dict[str, str] = field(default_factory=dict)
    # e.g. Memory<ShortTerm>(capacity: 2000) -> kind="ShortTerm", options={"capacity": "2000"}


@dataclass
class MethodDecl:
    name: str
    params: list[Param]              # reuse Param from Task #01
    return_type: str
    annotations: list[Annotation]    # reuse Annotation from Task #01
    body: str                        # raw body text
    parsed_body: Optional["Expr"] = None  # parsed expression AST (optional, for static analysis)


@dataclass
class RagDecl:
    name: str
    source: str                       # raw AXON source expression, e.g. "./docs/**/*.md"
    chunker: str                      # raw AXON chunker expression
    embedder: str                     # raw AXON embedder expression
    store: str                        # raw AXON vector-store expression
    annotations: list[Annotation] = field(default_factory=list)
    methods: list[MethodDecl] = field(default_factory=list)
    line: int = 0




@dataclass
class StageDecl:
    name: str
    params: list[Param]
    return_type: str
    line: int = 0


@dataclass
class FlowDecl:
    name: str
    params: list[Param]
    return_type: str
    annotations: list[Annotation] = field(default_factory=list)
    stages: list[StageDecl] = field(default_factory=list)
    body: str = ""                   # raw non-stage orchestration body
    parsed_body: Optional["Expr"] = None  # parsed expression AST (optional, for static analysis)
    line: int = 0

@dataclass
class AgentDecl:
    name: str
    model: str                       # e.g. "@anthropic/claude-haiku"
    tools: list[str]                 # e.g. ["FetchIssues", "AddLabel"]
    memory: Optional[MemoryDecl]
    annotations: list[Annotation] = field(default_factory=list)
    methods: list[MethodDecl] = field(default_factory=list)
    workers: Optional[str] = None
    line: int = 0
