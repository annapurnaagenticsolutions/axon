"""Tests for AXON LSP server."""

from axon.lsp_server import (
    AxonLanguageServer,
    Position,
    Range,
    CompletionItem,
    CompletionItemKind,
    TextDocumentItem,
)


def test_lsp_server_initialization():
    server = AxonLanguageServer()
    assert server.documents == {}
    assert len(server._keywords) > 0


def test_handle_did_open():
    server = AxonLanguageServer()
    params = {
        "textDocument": {
            "uri": "file:///test.ax",
            "languageId": "axon",
            "version": 1,
            "text": "agent Bot { model: @anthropic/claude-4 tools: [] fn run(q: Str) -> Str { q } }",
        }
    }
    server.handle_did_open(params)
    assert "file:///test.ax" in server.documents
    doc = server.documents["file:///test.ax"]
    assert doc.uri == "file:///test.ax"
    assert doc.languageId == "axon"
    assert doc.version == 1


def test_handle_did_change():
    server = AxonLanguageServer()
    # First open
    params = {
        "textDocument": {
            "uri": "file:///test.ax",
            "languageId": "axon",
            "version": 1,
            "text": "agent Bot { }",
        }
    }
    server.handle_did_open(params)
    
    # Then change
    change_params = {
        "textDocument": {
            "uri": "file:///test.ax",
            "languageId": "axon",
            "version": 2,
        },
        "contentChanges": [
            {"text": "agent Bot { model: @anthropic/claude-4 tools: [] fn run(q: Str) -> Str { q } }"}
        ],
    }
    server.handle_did_change(change_params)
    doc = server.documents["file:///test.ax"]
    assert doc.version == 2
    assert "model" in doc.text


def test_handle_did_close():
    server = AxonLanguageServer()
    params = {
        "textDocument": {
            "uri": "file:///test.ax",
            "languageId": "axon",
            "version": 1,
            "text": "agent Bot { }",
        }
    }
    server.handle_did_open(params)
    assert "file:///test.ax" in server.documents
    
    close_params = {"textDocument": {"uri": "file:///test.ax"}}
    server.handle_did_close(close_params)
    assert "file:///test.ax" not in server.documents


def test_handle_completion_keywords():
    server = AxonLanguageServer()
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text="agen",
    )
    
    params = {
        "textDocument": {"uri": "file:///test.ax"},
        "position": {"line": 0, "character": 4},
    }
    result = server.handle_completion(params)
    
    items = result["items"]
    assert any(item["label"] == "agent" for item in items)
    assert any(item["kind"] == CompletionItemKind.Keyword for item in items)


def test_handle_completion_types():
    server = AxonLanguageServer()
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text="Str",
    )
    
    params = {
        "textDocument": {"uri": "file:///test.ax"},
        "position": {"line": 0, "character": 3},
    }
    result = server.handle_completion(params)
    
    items = result["items"]
    assert any(item["label"] == "Str" for item in items)
    assert any(item["kind"] == CompletionItemKind.Class for item in items)


def test_handle_completion_annotations():
    server = AxonLanguageServer()
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text="@bud",
    )
    
    params = {
        "textDocument": {"uri": "file:///test.ax"},
        "position": {"line": 0, "character": 4},
    }
    result = server.handle_completion(params)
    
    items = result["items"]
    assert any(item["label"] == "budget" for item in items)
    assert any(item["kind"] == CompletionItemKind.Snippet for item in items)


def test_handle_diagnostics_valid_file():
    server = AxonLanguageServer()
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text='''
agent Bot {
    model: @anthropic/claude-4
    tools: []
    fn run(q: Str) -> Str { q }
}
''',
    )
    
    params = {"textDocument": {"uri": "file:///test.ax"}}
    result = server.handle_diagnostics(params)
    
    diagnostics = result["diagnostics"]
    # Should have no errors for valid file
    errors = [d for d in diagnostics if d["severity"] == 1]
    assert len(errors) == 0


def test_handle_diagnostics_invalid_file():
    server = AxonLanguageServer()
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text='''
tool T(x: Str) -> Str { x }
''',
    )
    
    params = {"textDocument": {"uri": "file:///test.ax"}}
    result = server.handle_diagnostics(params)
    
    diagnostics = result["diagnostics"]
    # Should have error for missing docstring
    errors = [d for d in diagnostics if d["severity"] == 1]
    assert len(errors) > 0
    assert any("docstring" in d["message"].lower() for d in errors)


def test_handle_document_symbols():
    server = AxonLanguageServer()
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text='''
agent Bot {
    model: @anthropic/claude-4
    tools: []
    fn run(q: Str) -> Str { q }
}

tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}
''',
    )
    
    params = {"textDocument": {"uri": "file:///test.ax"}}
    result = server.handle_document_symbols(params)
    
    symbols = result["symbols"]
    assert len(symbols) >= 2
    symbol_names = [s["name"] for s in symbols]
    assert "Bot" in symbol_names
    assert "Greet" in symbol_names


def test_get_word_before_cursor():
    server = AxonLanguageServer()
    
    assert server._get_word_before_cursor("agen", 4) == "agen"
    assert server._get_word_before_cursor("agent ", 5) == "agent"  # cursor at space, return word before
    assert server._get_word_before_cursor("agent Bot", 5) == "agent"
    assert server._get_word_before_cursor("", 0) == ""
    assert server._get_word_before_cursor("agen", 3) == "age"
    assert server._get_word_before_cursor("  agent", 2) == ""  # cursor at space after space


def test_completion_item_to_dict():
    item = CompletionItem(
        label="test",
        kind=CompletionItemKind.Keyword,
        detail="test detail",
        documentation="test docs",
    )
    
    server = AxonLanguageServer()
    result = server._completion_item_to_dict(item)
    
    assert result["label"] == "test"
    assert result["kind"] == CompletionItemKind.Keyword
    assert result["detail"] == "test detail"
    assert result["documentation"] == "test docs"


def test_get_symbol_kinds():
    server = AxonLanguageServer()
    
    # Test that we can get symbol kinds for different declaration types
    # This is tested indirectly through handle_document_symbols
    assert server._get_symbol_kind(None) is None


def test_document_aware_completion_offers_tool_name():
    server = AxonLanguageServer()
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/model
    tools: [Greet]
    fn run(q: Str) -> Str { q }
}
'''
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text=source,
    )
    params = {
        "textDocument": {"uri": "file:///test.ax"},
        "position": {"line": 7, "character": 12},  # inside tools: [Gre]
    }
    result = server.handle_completion(params)
    labels = [item["label"] for item in result["items"]]
    assert "Greet" in labels
    assert "Bot" in labels


def test_document_aware_completion_offers_agent_name():
    server = AxonLanguageServer()
    source = '''
agent Bot {
    model: @mock/model
    tools: []
    fn run(q: Str) -> Str { q }
}

agent Helper {
    model: @mock/model
    tools: []
    fn run(q: Str) -> Str { q }
}
'''
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text=source,
    )
    # Place cursor at line 0 col 3 inside keyword "agent" -> word="age"
    # This should still return "agent" keyword and "Bot"/"Helper" agents
    params = {
        "textDocument": {"uri": "file:///test.ax"},
        "position": {"line": 5, "character": 0},  # empty line, word=""
    }
    result = server.handle_completion(params)
    labels = [item["label"] for item in result["items"]]
    assert "Bot" in labels
    assert "Helper" in labels


def test_enhanced_diagnostics_syntax_error():
    server = AxonLanguageServer()
    source = '''agent Broken {
    model: @mock/model
    tools: []
    fn run(q: Str) -> Str { q }
'''  # missing closing brace
    server.documents["file:///test.ax"] = TextDocumentItem(
        uri="file:///test.ax",
        languageId="axon",
        version=1,
        text=source,
    )
    params = {"textDocument": {"uri": "file:///test.ax"}}
    result = server.handle_diagnostics(params)
    diagnostics = result["diagnostics"]
    assert len(diagnostics) > 0
    # Syntax diagnostic should have precise line/column
    assert diagnostics[0]["code"] == "syntax-error"
    assert "start" in diagnostics[0]["range"]
    assert "end" in diagnostics[0]["range"]
