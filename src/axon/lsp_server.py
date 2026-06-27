"""Language Server Protocol (LSP) server for AXON.

This module provides LSP support for AXON files, enabling IDE features like:
- Syntax highlighting
- Diagnostics (errors, warnings)
- Autocomplete/suggestions
- Go to definition
- Document symbols

The LSP server uses the existing parser, validator, type checker, and token budget
estimator to provide rich IDE support without requiring runtime execution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from axon.parser import parse
from axon.validator import validate
from axon.type_checker import check_types
from axon.token_budget import check_token_budgets
from axon.syntax import check_syntax


@dataclass
class Position:
    """LSP position (0-indexed)."""
    line: int
    character: int


@dataclass
class Range:
    """LSP range."""
    start: Position
    end: Position


@dataclass
class Diagnostic:
    """LSP diagnostic."""
    range: Range
    severity: int  # 1=Error, 2=Warning, 3=Info, 4=Hint
    code: str
    source: str
    message: str


@dataclass
class CompletionItem:
    """LSP completion item."""
    label: str
    kind: int
    detail: str = ""
    documentation: str = ""


@dataclass
class TextDocumentItem:
    """LSP text document item."""
    uri: str
    languageId: str
    version: int
    text: str


@dataclass
class CompletionItemKind:
    """LSP completion item kinds."""
    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18
    Folder = 19
    EnumMember = 20
    Constant = 21
    Struct = 22
    Event = 23
    Operator = 24
    TypeParameter = 25


class AxonLanguageServer:
    """Language Server Protocol server for AXON."""
    
    def __init__(self):
        self.documents: dict[str, TextDocumentItem] = {}
        self._keywords = [
            "agent", "tool", "prompt", "memory", "flow", "rag",
            "fn", "import", "type", "model", "tools", "return",
            "if", "else", "match", "for", "while", "let", "in",
            "think", "act", "observe", "store", "Ok", "Err",
            "Option", "Result", "List", "Map", "Set", "Stream",
            "Str", "Int", "Float", "Bool", "Any", "Bytes",
        ]
    
    def handle_did_open(self, params: dict[str, Any]) -> None:
        """Handle textDocument/didOpen notification."""
        text_doc = params["textDocument"]
        self.documents[text_doc["uri"]] = TextDocumentItem(
            uri=text_doc["uri"],
            languageId=text_doc["languageId"],
            version=text_doc["version"],
            text=text_doc["text"],
        )
    
    def handle_did_change(self, params: dict[str, Any]) -> None:
        """Handle textDocument/didChange notification."""
        text_doc = params["textDocument"]
        changes = params["contentChanges"]
        
        if text_doc["uri"] in self.documents:
            doc = self.documents[text_doc["uri"]]
            for change in changes:
                # For full document sync
                if "range" not in change:
                    doc.text = change["text"]
                    doc.version = text_doc["version"]
    
    def handle_did_close(self, params: dict[str, Any]) -> None:
        """Handle textDocument/didClose notification."""
        text_doc = params["textDocument"]
        if text_doc["uri"] in self.documents:
            del self.documents[text_doc["uri"]]
    
    def handle_completion(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle textDocument/completion request."""
        text_doc = params["textDocument"]
        position = params["position"]
        
        uri = text_doc["uri"]
        if uri not in self.documents:
            return {"items": []}
        
        doc = self.documents[uri]
        line = position["line"]
        char = position["character"]
        
        # Get line text
        lines = doc.text.split("\n")
        if line >= len(lines):
            return {"items": []}
        
        line_text = lines[line]
        word_before = self._get_word_before_cursor(line_text, char)

        items = self._get_completions(word_before, line_text, char, doc)

        return {"items": [self._completion_item_to_dict(item) for item in items]}
    
    def _get_word_before_cursor(self, line: str, char: int) -> str:
        """Get the word before the cursor position."""
        if char > len(line):
            char = len(line)
        
        if char == 0:
            return ""
        
        # If the character before cursor is not a word character, return empty string
        if not (line[char - 1].isalnum() or line[char - 1] in "_"):
            return ""
        
        word_start = char
        while word_start > 0 and (line[word_start - 1].isalnum() or line[word_start - 1] in "_"):
            word_start -= 1
        
        return line[word_start:char]
    
    def _get_completions(self, word: str, line: str, char: int, doc: TextDocumentItem) -> list[CompletionItem]:
        """Get completion items for the current context."""
        items: list[CompletionItem] = []

        # Keywords
        for keyword in self._keywords:
            if keyword.lower().startswith(word.lower()):
                items.append(CompletionItem(
                    label=keyword,
                    kind=CompletionItemKind.Keyword,
                    detail="AXON keyword",
                ))

        # Type names
        type_names = ["Str", "Int", "Float", "Bool", "Any", "Bytes", "List", "Map", "Set", "Option", "Result", "Stream"]
        for type_name in type_names:
            if type_name.startswith(word):
                items.append(CompletionItem(
                    label=type_name,
                    kind=CompletionItemKind.Class,
                    detail="AXON type",
                ))

        # Annotations
        if "@" in line[:char]:
            annotations = ["budget", "schedule", "trace", "managed", "retry", "timeout", "cache"]
            for annotation in annotations:
                if annotation.startswith(word):
                    items.append(CompletionItem(
                        label=annotation,
                        kind=CompletionItemKind.Snippet,
                        detail="AXON annotation",
                    ))

        # Document-aware completions: parse the document and offer declared names
        try:
            declarations = parse(doc.text)
            tool_names = [d.name for d in declarations if type(d).__name__ == "ToolDecl"]
            agent_names = [d.name for d in declarations if type(d).__name__ == "AgentDecl"]
            prompt_names = [d.name for d in declarations if type(d).__name__ == "PromptDecl"]
            flow_names = [d.name for d in declarations if type(d).__name__ == "FlowDecl"]
            type_aliases = [d.name for d in declarations if type(d).__name__ == "TypeAliasDecl"]

            for name in tool_names:
                if name.lower().startswith(word.lower()):
                    items.append(CompletionItem(
                        label=name,
                        kind=CompletionItemKind.Function,
                        detail="AXON tool",
                    ))
            for name in agent_names:
                if name.lower().startswith(word.lower()):
                    items.append(CompletionItem(
                        label=name,
                        kind=CompletionItemKind.Class,
                        detail="AXON agent",
                    ))
            for name in prompt_names:
                if name.lower().startswith(word.lower()):
                    items.append(CompletionItem(
                        label=name,
                        kind=CompletionItemKind.Property,
                        detail="AXON prompt",
                    ))
            for name in flow_names:
                if name.lower().startswith(word.lower()):
                    items.append(CompletionItem(
                        label=name,
                        kind=CompletionItemKind.Class,
                        detail="AXON flow",
                    ))
            for name in type_aliases:
                if name.lower().startswith(word.lower()):
                    items.append(CompletionItem(
                        label=name,
                        kind=CompletionItemKind.Interface,
                        detail="AXON type alias",
                    ))
        except Exception:
            pass  # If parsing fails, fall back to keyword/type completions only

        return items
    
    def _completion_item_to_dict(self, item: CompletionItem) -> dict[str, Any]:
        """Convert completion item to LSP dict format."""
        return {
            "label": item.label,
            "kind": item.kind,
            "detail": item.detail,
            "documentation": item.documentation,
        }
    
    def handle_diagnostics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle textDocument/diagnostic request."""
        text_doc = params["textDocument"]
        uri = text_doc["uri"]

        if uri not in self.documents:
            return {"diagnostics": []}

        doc = self.documents[uri]
        lsp_diagnostics: list[dict[str, Any]] = []

        # Step 1: Syntax check (non-raising, precise line/column)
        syntax_result = check_syntax(doc.text, filename=uri)
        for sd in syntax_result.diagnostics:
            lsp_diagnostics.append({
                "range": {
                    "start": {"line": max(sd.line - 1, 0), "character": max(sd.column - 1, 0)},
                    "end": {"line": max(sd.line - 1, 0), "character": max(sd.column - 1, 0) + 1},
                },
                "severity": 1,
                "code": "syntax-error",
                "source": "axon-lsp",
                "message": sd.message,
            })

        # Step 2: Semantic validation only when parsing succeeded
        if syntax_result.ok and syntax_result.declarations is not None:
            declarations = syntax_result.declarations
            try:
                validator_diagnostics = validate(declarations)
                type_diagnostics = check_types(declarations)
                token_diagnostics = check_token_budgets(declarations)

                for diag in validator_diagnostics + type_diagnostics + token_diagnostics:
                    lsp_diagnostics.append({
                        "range": {
                            "start": {"line": max(diag.line - 1, 0), "character": 0},
                            "end": {"line": max(diag.line - 1, 0), "character": 100},
                        },
                        "severity": 1 if diag.severity == "error" else 2,
                        "code": diag.code or "",
                        "source": "axon-lsp",
                        "message": diag.message,
                    })
            except Exception as e:
                lsp_diagnostics.append({
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 0},
                    },
                    "severity": 1,
                    "code": "validation-error",
                    "source": "axon-lsp",
                    "message": str(e),
                })

        return {"diagnostics": lsp_diagnostics}
    
    def handle_document_symbols(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle textDocument/documentSymbol request."""
        text_doc = params["textDocument"]
        uri = text_doc["uri"]
        
        if uri not in self.documents:
            return {"symbols": []}
        
        doc = self.documents[uri]
        
        try:
            declarations = parse(doc.text)
        except Exception:
            return {"symbols": []}
        
        symbols = []
        for decl in declarations:
            kind = self._get_symbol_kind(decl)
            if kind:
                symbols.append({
                    "name": getattr(decl, "name", "unknown"),
                    "kind": kind,
                    "range": {
                        "start": {"line": getattr(decl, "line", 0) - 1, "character": 0},
                        "end": {"line": getattr(decl, "line", 0) - 1, "character": 100},
                    },
                    "selectionRange": {
                        "start": {"line": getattr(decl, "line", 0) - 1, "character": 0},
                        "end": {"line": getattr(decl, "line", 0) - 1, "character": len(getattr(decl, "name", ""))},
                    },
                })
        
        return {"symbols": symbols}
    
    def _get_symbol_kind(self, decl: Any) -> Optional[int]:
        """Get LSP symbol kind for a declaration."""
        decl_type = type(decl).__name__
        
        if decl_type == "ToolDecl":
            return CompletionItemKind.Function
        elif decl_type == "AgentDecl":
            return CompletionItemKind.Class
        elif decl_type == "PromptDecl":
            return CompletionItemKind.Function
        elif decl_type == "RagDecl":
            return CompletionItemKind.Class
        elif decl_type == "FlowDecl":
            return CompletionItemKind.Class
        elif decl_type == "TypeAliasDecl":
            return CompletionItemKind.Interface
        elif decl_type == "ImportDecl":
            return CompletionItemKind.Module
        
        return None


def run_lsp_server() -> None:
    """Run the LSP server using stdin/stdout."""
    import sys
    
    server = AxonLanguageServer()
    
    # Read from stdin, write to stdout (JSON-RPC)
    for line in sys.stdin:
        if not line.strip():
            continue
        
        try:
            # Parse JSON-RPC message
            message = json.loads(line)
            method = message.get("method")
            params = message.get("params", {})
            msg_id = message.get("id")
            
            result = None
            error = None
            
            if method == "initialize":
                result = {
                    "capabilities": {
                        "textDocumentSync": 1,  # Full sync
                        "completionProvider": {
                            "triggerCharacters": [".", "@", ":", " "],
                        },
                        "diagnosticProvider": {},
                        "documentSymbolProvider": True,
                    }
                }
            elif method == "textDocument/didOpen":
                server.handle_did_open(params)
            elif method == "textDocument/didChange":
                server.handle_did_change(params)
            elif method == "textDocument/didClose":
                server.handle_did_close(params)
            elif method == "textDocument/completion":
                result = server.handle_completion(params)
            elif method == "textDocument/diagnostic":
                result = server.handle_diagnostics(params)
            elif method == "textDocument/documentSymbol":
                result = server.handle_document_symbols(params)
            elif method == "shutdown":
                result = None
            elif method == "exit":
                break
            else:
                error = {"code": -32601, "message": f"Unknown method: {method}"}
            
            # Send response
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
                "error": error,
            }
            print(json.dumps(response))
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            # Send error response
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id") if 'message' in locals() else None,
                "error": {"code": -32603, "message": str(e)},
            }
            print(json.dumps(response))
            sys.stdout.flush()
