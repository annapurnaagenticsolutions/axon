from axon.ast_nodes import AgentDecl, ImportDecl, PromptDecl, ToolDecl
from axon.parser import parse


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


# Task #02 tests

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


# Extra edge cases beyond the ticket

def test_agent_annotation_resets_before_next_decl():
    source = '''
@managed
agent LongRunningAgent {
    model: env.DEFAULT_MODEL
    tools: []
    fn run(q: Str) -> Str { q }
}

tool Plain(x: Str) -> Str {
    /// Plain tool.
    x
}
'''
    decls = parse(source)
    assert decls[0].annotations[0].name == "managed"
    assert decls[1].annotations == []


def test_memory_option_with_nested_call():
    source = '''
agent Mem {
    model: @anthropic/claude-4
    tools: []
    memory: Memory<Semantic>(store: VectorDB::postgres(env.PG_URL))
    fn run(q: Str) -> Str { q }
}
'''
    decls = parse(source)
    assert decls[0].memory.kind == "Semantic"
    assert decls[0].memory.options["store"] == "VectorDB::postgres(env.PG_URL)"


def test_method_body_with_nested_braces():
    source = '''
agent Nest {
    model: @anthropic/claude-4
    tools: []
    fn run(q: Str) -> Result<Report, AgentError> {
        let report = Report { summary: q, findings: [] }
        Ok(report)
    }
}
'''
    decls = parse(source)
    assert "Report { summary: q" in decls[0].methods[0].body
    assert decls[0].methods[0].body.endswith("Ok(report)")


# Task #06 tests: type aliases

def test_simple_type_alias():
    source = 'type IssueId = Int\n'
    decls = parse(source)
    assert len(decls) == 1
    t = decls[0]
    from axon.ast_nodes import TypeAliasDecl
    assert isinstance(t, TypeAliasDecl)
    assert t.name == "IssueId"
    assert t.type_params == []
    assert t.value == "Int"
    assert t.fields == []


def test_literal_union_type_alias():
    source = 'type Priority = "low" | "medium" | "high"\n'
    decls = parse(source)
    t = decls[0]
    assert t.name == "Priority"
    assert t.value == '"low" | "medium" | "high"'
    assert t.fields == []


def test_record_type_alias_multiline():
    source = '''
type Issue = {
    id: Int,
    number: Int,
    title: Str,
    labels: List<Str>,
    priority: "low" | "medium" | "high"
}
'''
    decls = parse(source)
    t = decls[0]
    assert t.name == "Issue"
    assert t.value.startswith("{")
    assert len(t.fields) == 5
    assert t.fields[0].name == "id"
    assert t.fields[0].type_str == "Int"
    assert t.fields[3].name == "labels"
    assert t.fields[3].type_str == "List<Str>"
    assert t.fields[4].type_str == '"low" | "medium" | "high"'


def test_generic_record_type_alias():
    source = 'type PagedList<T> = { items: List<T>, total: Int, page: Int }\n'
    decls = parse(source)
    t = decls[0]
    assert t.name == "PagedList"
    assert t.type_params == ["T"]
    assert t.fields[0].name == "items"
    assert t.fields[0].type_str == "List<T>"


def test_generic_alias_multiple_type_params():
    source = 'type PairResult<T, E> = Result<Tuple<T, E>, AgentError>\n'
    decls = parse(source)
    t = decls[0]
    assert t.name == "PairResult"
    assert t.type_params == ["T", "E"]
    assert t.value == "Result<Tuple<T, E>, AgentError>"


def test_type_alias_in_mixed_file_order():
    source = '''
import { Search } from "axon:tools/web"

type Query = Str

tool Echo(q: Query) -> Query {
    /// Echoes query.
    q
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Echo, Search]
    fn run(q: Query) -> Query { q }
}
'''
    decls = parse(source)
    from axon.ast_nodes import TypeAliasDecl
    assert isinstance(decls[0], ImportDecl)
    assert isinstance(decls[1], TypeAliasDecl)
    assert isinstance(decls[2], ToolDecl)
    assert isinstance(decls[3], AgentDecl)
    assert decls[2].params[0].type_str == "Query"
    assert decls[3].methods[0].return_type == "Query"


def test_type_alias_ignores_inline_comment():
    source = 'type UserId = Str // stable user identifier\n'
    decls = parse(source)
    assert decls[0].value == "Str"


def test_type_alias_rejects_annotation():
    source = '''
@trace
type Bad = Str
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "Annotations are not valid before type alias" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError")


def test_simple_prompt_declaration():
    source = '''
prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {
    """
    Summarize this text:
    {text}
    """
}
'''
    decls = parse(source)
    assert len(decls) == 1
    p = decls[0]
    assert isinstance(p, PromptDecl)
    assert p.name == "Summarize"
    assert p.params[0].name == "text"
    assert p.params[0].type_str == "Str"
    assert p.return_type == "Str"
    assert p.annotations[0].name == "budget"
    assert p.annotations[0].args["tokens"] == "300"
    assert p.template == "Summarize this text:\n{text}"


def test_prompt_with_default_param_and_list_return():
    source = '''
prompt ExtractActionItems(
    transcript: Str,
    audience: Str = "engineering",
    @budget(tokens: 500)
) -> List<ActionItem> {
    """
    Extract action items for {audience} from:
    {transcript}
    """
}
'''
    decls = parse(source)
    p = decls[0]
    assert p.params[1].name == "audience"
    assert p.params[1].default == '"engineering"'
    assert p.return_type == "List<ActionItem>"
    assert "{transcript}" in p.template


def test_prompt_accepts_top_level_and_inline_annotations():
    source = '''
@trace
prompt DraftEmail(recipient: Str, purpose: Str, @budget(tokens: 800)) -> Str {
    """
    Draft an email to {recipient} about {purpose}.
    """
}
'''
    decls = parse(source)
    p = decls[0]
    assert [a.name for a in p.annotations] == ["trace", "budget"]
    assert p.annotations[1].args["tokens"] == "800"


def test_prompt_in_mixed_file_order():
    source = '''
import { WebSearch } from "axon:tools/web"

type Topic = Str

prompt SearchPrompt(topic: Topic, @budget(tokens: 200)) -> Str {
    """
    Generate a search query for {topic}.
    """
}

tool Search(query: Str) -> Str {
    /// Searches.
    WebSearch(query)
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Search]
    fn run(q: Str) -> Str { q }
}
'''
    decls = parse(source)
    assert isinstance(decls[2], PromptDecl)
    assert decls[2].name == "SearchPrompt"
    assert isinstance(decls[3], ToolDecl)
    assert isinstance(decls[4], AgentDecl)


def test_prompt_requires_triple_quoted_template():
    source = '''
prompt Bad(text: Str) -> Str {
    text
}
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "triple-quoted" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError for prompt without triple-quoted template")


def test_prompt_rejects_trailing_body_after_template():
    source = '''
prompt Bad(text: Str) -> Str {
    """
    {text}
    """
    extra
}
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "Unexpected text after template" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError for trailing prompt body text")


# Task #08 tests: RAG declarations

def test_simple_rag_declaration():
    from axon.ast_nodes import RagDecl

    source = '''
rag ProductDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::postgres(env.PGVECTOR_URL)

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(chunk => chunk.score > 0.72)
    }
}
'''
    decls = parse(source)
    assert len(decls) == 1
    r = decls[0]
    assert isinstance(r, RagDecl)
    assert r.name == "ProductDocs"
    assert r.source == '"./knowledge_base/**/*.md"'
    assert r.chunker == "Chunker::sliding(size: 512, overlap: 64)"
    assert r.embedder == "@openai/text-embed-3"
    assert r.store == "VectorDB::postgres(env.PGVECTOR_URL)"
    assert len(r.methods) == 1
    assert r.methods[0].name == "retrieve"
    assert r.methods[0].params[1].default == "5"
    assert r.methods[0].return_type == "List<Chunk>"
    assert "store.search" in r.methods[0].body


def test_rag_source_list_and_local_embedder():
    source = '''
rag LocalDocs {
    source: ["./specs/*.md", "./wiki/*.txt"]
    chunker: Chunker::paragraph()
    embedder: @ollama/nomic-embed-text
    store: VectorDB::sqlite("./index.db")

    fn retrieve(query: Str) -> List<Chunk> { store.search(embed(query), 5) }
}
'''
    decls = parse(source)
    r = decls[0]
    assert r.source == '["./specs/*.md", "./wiki/*.txt"]'
    assert r.embedder == "@ollama/nomic-embed-text"
    assert r.store == 'VectorDB::sqlite("./index.db")'


def test_rag_method_annotations():
    source = '''
rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::sentence(max_tokens: 256)
    embedder: @openai/text-embed-3
    store: VectorDB::chroma(env.CHROMA_URL)

    @trace
    @budget(tokens: 2000)
    fn retrieve(query: Str, top_k: Int = 3) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}
'''
    decls = parse(source)
    method = decls[0].methods[0]
    assert [a.name for a in method.annotations] == ["trace", "budget"]
    assert method.annotations[1].args["tokens"] == "2000"


def test_rag_annotation_resets_before_next_decl():
    source = '''
@trace
rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::paragraph()
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")
    fn retrieve(query: Str) -> List<Chunk> { store.search(embed(query), 5) }
}

tool Plain(x: Str) -> Str {
    /// Plain tool.
    x
}
'''
    decls = parse(source)
    assert decls[0].annotations[0].name == "trace"
    assert decls[1].annotations == []


def test_rag_in_mixed_file_order():
    from axon.ast_nodes import RagDecl

    source = '''
import { Chunk } from "axon:types"

type Query = Str

prompt MakeQuery(topic: Query, @budget(tokens: 200)) -> Str {
    """
    Create a retrieval query for {topic}.
    """
}

rag KnowledgeBase {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::postgres(env.PGVECTOR_URL)
    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> { store.search(embed(query), top_k) }
}

tool CreateTicket(title: Str) -> Result<Str, ToolError> {
    /// Creates a ticket.
    http.post(env.TICKET_API, { title })
}

agent SupportAgent {
    model: @anthropic/claude-4
    tools: [KnowledgeBase.retrieve, CreateTicket]
    fn handle(question: Str) -> Str { question }
}
'''
    decls = parse(source)
    assert isinstance(decls[3], RagDecl)
    assert decls[3].name == "KnowledgeBase"
    assert decls[5].tools == ["KnowledgeBase.retrieve", "CreateTicket"]


def test_rag_requires_required_fields():
    source = '''
rag BadDocs {
    source: "./docs/**/*.md"
    chunker: Chunker::paragraph()
    embedder: @openai/text-embed-3
    fn retrieve(query: Str) -> List<Chunk> { [] }
}
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "Missing required field" in str(exc)
        assert "store" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError for missing RAG store field")


def test_rag_requires_method():
    source = '''
rag BadDocs {
    source: "./docs/**/*.md"
    chunker: Chunker::paragraph()
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")
}
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "must define at least one retrieve method" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError for RAG block without retrieve method")

# Task #09 tests: Flow declarations

def test_simple_flow_declaration():
    from axon.ast_nodes import FlowDecl

    source = '''
flow SupportFlow(question: Str) -> Str {
    stage Retrieve(query: Str) -> List<Chunk>
    stage Generate(chunks: List<Chunk>, query: Str) -> Str

    Retrieve -> Generate
}
'''
    decls = parse(source)
    assert len(decls) == 1
    flow = decls[0]
    assert isinstance(flow, FlowDecl)
    assert flow.name == "SupportFlow"
    assert flow.params[0].name == "question"
    assert flow.return_type == "Str"
    assert len(flow.stages) == 2
    assert flow.stages[0].name == "Retrieve"
    assert flow.stages[0].params[0].type_str == "Str"
    assert flow.stages[1].return_type == "Str"
    assert flow.body == "Retrieve -> Generate"


def test_flow_with_parallel_and_match_body():
    source = '''
flow RAGPipeline(query: Str) -> Response {
    stage LocalSearch(query: Str) -> List<Chunk>
    stage WebSearch(query: Str) -> List<Chunk>
    stage Merge(local: List<Chunk>, web: List<Chunk>) -> List<Chunk>

    [LocalSearch, WebSearch] -> Merge
    Merge -> match score {
        high => DirectAnswer,
        _    => EscalateToHuman
    }
}
'''
    decls = parse(source)
    flow = decls[0]
    assert [stage.name for stage in flow.stages] == ["LocalSearch", "WebSearch", "Merge"]
    assert "[LocalSearch, WebSearch] -> Merge" in flow.body
    assert "match score" in flow.body
    assert "EscalateToHuman" in flow.body


def test_flow_imperative_body_without_stages():
    source = '''
flow DebatePipeline(topic: Str, rounds: Int = 3) -> DebateTranscript {
    let pro_agent = DebaterAgent(label: "Pro: {topic}")
    let con_agent = DebaterAgent(label: "Con: {topic}")

    for round in 1..=rounds {
        let pro_future = go pro_agent.argue(position: "For: {topic}", round: round)
        let con_future = go con_agent.argue(position: "Against: {topic}", round: round)
        let [pro_arg, con_arg] = await [pro_future, con_future]?
    }

    transcript
}
'''
    decls = parse(source)
    flow = decls[0]
    assert flow.name == "DebatePipeline"
    assert flow.params[1].default == "3"
    assert flow.stages == []
    assert "for round in 1..=rounds" in flow.body
    assert "await [pro_future, con_future]?" in flow.body


def test_flow_annotations_reset_before_next_decl():
    source = '''
@trace
flow Pipeline(input: Str) -> Str {
    stage A(input: Str) -> Str
    A -> Respond
}

tool Plain(x: Str) -> Str {
    /// Plain tool.
    x
}
'''
    decls = parse(source)
    assert decls[0].annotations[0].name == "trace"
    assert decls[1].annotations == []


def test_flow_in_mixed_file_order():
    from axon.ast_nodes import FlowDecl, RagDecl

    source = '''
import { Chunk } from "axon:types"

type Query = Str

rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::paragraph()
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")
    fn retrieve(query: Str) -> List<Chunk> { store.search(embed(query), 5) }
}

flow AnswerFlow(question: Query) -> Str {
    stage Retrieve(query: Query) -> List<Chunk>
    stage Answer(chunks: List<Chunk>, question: Query) -> Str
    Retrieve -> Answer
}

tool Respond(text: Str) -> Str {
    /// Responds with text.
    text
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Docs.retrieve, Respond]
    fn run(q: Query) -> Str { q }
}
'''
    decls = parse(source)
    assert isinstance(decls[2], RagDecl)
    assert isinstance(decls[3], FlowDecl)
    assert decls[3].name == "AnswerFlow"
    assert decls[5].name == "Bot"


def test_flow_requires_arrow_after_params():
    source = '''
flow Bad(input: Str) Str {
    input
}
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "Expected '->'" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError for malformed flow header")


def test_stage_requires_return_type():
    source = '''
flow Bad(input: Str) -> Str {
    stage A(input: Str) ->
    A -> B
}
'''
    try:
        parse(source)
    except SyntaxError as exc:
        assert "Expected return type for stage A" in str(exc)
    else:
        raise AssertionError("Expected SyntaxError for stage without return type")
