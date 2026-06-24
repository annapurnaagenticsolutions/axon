import json

from axon.parser import parse
from axon.trace import ActEvent, ObserveEvent, StoreEvent, ThinkEvent
from axon.trace_extract import (
    TraceExtractionOptions,
    extract_trace_events_from_body,
    extract_trace_preview,
    extract_trace_preview_from_source,
    format_trace_preview,
    trace_preview_to_json,
)


def test_extract_think_act_observe_store_from_body():
    body = '''
think "Need current information"
let results = act WebSearch(query: topic, max_results: 5)?
observe results: [{ title: "A" }, { title: "B" }]
store memory.working["results"] = results
'''

    events = extract_trace_events_from_body(body, agent="ResearchAgent", method="run", declaration_kind="agent")

    assert [event.t for event in events] == ["think", "act", "observe", "store"]
    assert isinstance(events[0], ThinkEvent)
    assert events[0].content == "Need current information"
    assert isinstance(events[1], ActEvent)
    assert events[1].tool == "WebSearch"
    assert events[1].args == {"query": "topic", "max_results": "5"}
    assert isinstance(events[2], ObserveEvent)
    assert events[2].name == "results"
    assert events[2].count == 2
    assert isinstance(events[3], StoreEvent)
    assert events[3].key == 'memory.working["results"]'
    assert events[3].value == "results"
    assert all(event.agent == "ResearchAgent" for event in events)
    assert all(event.metadata["method"] == "run" for event in events)


def test_extract_trace_preview_from_agent_declaration():
    source = '''
tool WebSearch(query: Str) -> List<Any> {
    /// Searches the web.
    http.get(query)
}

agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch]

    fn run(topic: Str) -> Result<(), AgentError> {
        think "Plan the search"
        let results = act WebSearch(query: topic)?
        store memory.working["results"] = results
        Ok(())
    }
}
'''

    log = extract_trace_preview_from_source(source)

    assert [event.t for event in log.events] == ["think", "act", "store"]
    assert log.events[1].tool == "WebSearch"
    assert log.events[1].agent == "ResearchAgent"


def test_comments_and_string_urls_do_not_confuse_extractor():
    body = '''
// act IgnoredTool(x: y)
think "http://example.com is just text"
let value = "// not a comment"
let results = act Fetch(url: "https://example.com/a,b", headers: { token: env.TOKEN })? // trailing
'''

    events = extract_trace_events_from_body(body)

    assert [event.t for event in events] == ["think", "act"]
    assert events[1].args["url"] == '"https://example.com/a,b"'
    assert events[1].args["headers"] == "{ token: env.TOKEN }"


def test_multiple_act_calls_on_one_line_preserve_order():
    body = 'let a = act First(x: 1)?; let b = act Second(y: act Nested(z: 3))?'

    events = extract_trace_events_from_body(body)

    assert [event.tool for event in events] == ["First", "Second"]
    assert events[1].args == {"y": "act Nested(z: 3)"}


def test_positional_act_args_are_preserved_with_generated_names():
    body = 'let x = act Complete(task, mode: "fast")?'

    events = extract_trace_events_from_body(body)

    assert events[0].args == {"_$1": "task", "mode": '"fast"'}


def test_extract_trace_preview_ignores_rag_methods_by_default():
    source = '''
rag Docs {
    source: "./docs/*.md"
    chunker: Chunker::paragraph()
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")

    fn retrieve(query: Str) -> List<Chunk> {
        let chunks = act Search(query: query)?
        chunks
    }
}
'''
    decls = parse(source)

    assert extract_trace_preview(decls).events == []
    with_rag = extract_trace_preview(decls, options=TraceExtractionOptions(include_rag_methods=True))
    assert len(with_rag.events) == 1
    assert with_rag.events[0].tool == "Search"
    assert with_rag.events[0].metadata["declaration"] == "rag"


def test_format_trace_preview_and_json():
    log = extract_trace_preview_from_source('''
tool Search(q: Str) -> Str { /// Searches. q }
agent Bot {
    model: @anthropic/claude-4
    tools: [Search]
    fn run(q: Str) -> Str {
        think "Plan"
        let r = act Search(q: q)?
        r
    }
}
''')

    text = format_trace_preview(log)
    assert "AEL trace preview: 2 event" in text
    assert "think [Bot.run]: Plan" in text
    assert "act [Bot.run]: Search(q=q)" in text

    data = json.loads(trace_preview_to_json(log))
    assert data[0]["t"] == "think"
    assert data[1]["tool"] == "Search"


def test_empty_preview_formats_cleanly():
    assert format_trace_preview(extract_trace_preview([])) == "No AEL trace events found."
