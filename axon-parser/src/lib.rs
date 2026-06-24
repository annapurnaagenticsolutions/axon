//! AXON Parser — `.ax` source to portable IR JSON.
//!
//! This crate implements the AXON parser in Rust that produces
//! IR JSON identical to the Python reference implementation.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub mod expression;
pub mod fuzz;
pub mod bench;

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct Annotation {
    pub name: String,
    #[serde(default)]
    pub args: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct Param {
    pub name: String,
    pub type_str: String,
        pub default: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct MethodDef {
    pub name: String,
    #[serde(default)]
    pub params: Vec<Param>,
    pub return_type: String,
    pub body: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub body_ast: Option<crate::expression::Expr>,
    #[serde(default)]
    pub annotations: Vec<Annotation>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct MemoryDecl {
    pub kind: String,
    #[serde(default)]
    pub options: HashMap<String, String>,
}

// ---------------------------------------------------------------------------
// Import & Type Alias
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct ImportDef {
    #[serde(default = "default_import_kind")]
    pub kind: String,
    pub names: Vec<String>,
    pub source: String,
}

fn default_import_kind() -> String { "import".to_string() }

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct TypeAliasDef {
    #[serde(default = "default_type_alias_kind")]
    pub kind: String,
    pub name: String,
    #[serde(default)]
    pub type_params: Vec<String>,
    pub value: String,
    #[serde(default)]
    pub fields: Vec<Param>,
}

fn default_type_alias_kind() -> String { "type_alias".to_string() }

// ---------------------------------------------------------------------------
// RAG
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct RagDef {
    #[serde(default = "default_rag_kind")]
    pub kind: String,
    pub name: String,
    pub source: String,
    pub chunker: String,
    pub embedder: String,
    pub store: String,
    #[serde(default)]
    pub methods: Vec<MethodDef>,
    #[serde(default)]
    pub annotations: Vec<Annotation>,
}

fn default_rag_kind() -> String { "rag".to_string() }

// ---------------------------------------------------------------------------
// Prompt
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct PromptDef {
    #[serde(default = "default_prompt_kind")]
    pub kind: String,
    pub name: String,
    #[serde(default)]
    pub params: Vec<Param>,
    pub return_type: String,
    pub template: String,
    #[serde(default)]
    pub annotations: Vec<Annotation>,
}

fn default_prompt_kind() -> String { "prompt".to_string() }

// ---------------------------------------------------------------------------
// Tool
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct ToolDef {
    #[serde(default = "default_tool_kind")]
    pub kind: String,
    pub name: String,
    #[serde(default)]
    pub params: Vec<Param>,
    pub return_type: String,
    #[serde(default)]
    pub docstrings: Vec<String>,
    pub body: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub body_ast: Option<crate::expression::Expr>,
    #[serde(default)]
    pub annotations: Vec<Annotation>,
}

fn default_tool_kind() -> String { "tool".to_string() }

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct AgentDef {
    #[serde(default = "default_agent_kind")]
    pub kind: String,
    pub name: String,
    pub model: String,
    #[serde(default)]
    pub tools: Vec<String>,
        pub memory: Option<MemoryDecl>,
    #[serde(default)]
    pub methods: Vec<MethodDef>,
    #[serde(default)]
    pub annotations: Vec<Annotation>,
        pub workers: Option<String>,
}

fn default_agent_kind() -> String { "agent".to_string() }

// ---------------------------------------------------------------------------
// Flow
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct StageDef {
    pub name: String,
    #[serde(default)]
    pub params: Vec<Param>,
    pub return_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct FlowEdge {
    pub from_stage: String,
    pub to_stage: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct FlowDef {
    #[serde(default = "default_flow_kind")]
    pub kind: String,
    pub name: String,
    #[serde(default)]
    pub params: Vec<Param>,
    pub return_type: String,
    #[serde(default)]
    pub stages: Vec<StageDef>,
    #[serde(default)]
    pub edges: Vec<FlowEdge>,
    #[serde(default)]
    pub annotations: Vec<Annotation>,
}

fn default_flow_kind() -> String { "flow".to_string() }

// ---------------------------------------------------------------------------
// Security
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct CapabilityRule {
    pub resource: String,
    pub action: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct ApprovalGate {
    pub tool_id: String,
    #[serde(default = "default_timeout")]
    pub timeout_seconds: i32,
        pub approver_role: Option<String>,
}

fn default_timeout() -> i32 { 300 }

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct SecurityPolicy {
    #[serde(default)]
    pub capabilities: Vec<CapabilityRule>,
    #[serde(default)]
    pub approval_gates: Vec<ApprovalGate>,
    pub max_token_budget: Option<i32>,
    pub max_cost_budget_usd: Option<f64>,
}

// ---------------------------------------------------------------------------
// Top-level IR Document
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct AxonIR {
    #[serde(default = "default_version")]
    pub version: String,
    #[serde(default)]
    pub imports: Vec<ImportDef>,
    #[serde(default)]
    pub type_aliases: Vec<TypeAliasDef>,
    #[serde(default)]
    pub rags: Vec<RagDef>,
    #[serde(default)]
    pub prompts: Vec<PromptDef>,
    #[serde(default)]
    pub tools: Vec<ToolDef>,
    #[serde(default)]
    pub agents: Vec<AgentDef>,
    #[serde(default)]
    pub flows: Vec<FlowDef>,
    #[serde(default)]
    pub global_security: SecurityPolicy,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

fn default_version() -> String { "0.2.0".to_string() }

/// Python-style textwrap.dedent: strip common leading whitespace from all non-empty lines.
fn dedent(text: &str) -> String {
    let lines: Vec<&str> = text.lines().collect();
    let non_empty: Vec<&&str> = lines.iter().filter(|s| !s.trim().is_empty()).collect();
    let prefix = non_empty.iter()
        .filter_map(|s| {
            let ws = s.chars().take_while(|c| c.is_whitespace()).count();
            if ws < s.len() { Some(ws) } else { None }
        })
        .min()
        .unwrap_or(0);
    lines.iter()
        .map(|s| {
            if s.trim().is_empty() { "" } else { &s[prefix.min(s.len())..] }
        })
        .collect::<Vec<_>>()
        .join("\n")
        .trim()
        .to_string()
}

impl Default for AxonIR {
    fn default() -> Self {
        Self {
            version: default_version(),
            imports: Vec::new(),
            type_aliases: Vec::new(),
            rags: Vec::new(),
            prompts: Vec::new(),
            tools: Vec::new(),
            agents: Vec::new(),
            flows: Vec::new(),
            global_security: SecurityPolicy::default(),
            metadata: HashMap::new(),
        }
    }
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
pub enum ParseErrorKind {
    UnexpectedToken,
    UnclosedBlock,
    InvalidSyntax,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ParseError {
    pub kind: ParseErrorKind,
    pub line: usize,
    pub col: usize,
    pub msg: String,
    pub context: Vec<String>,
    pub suggestion: Option<String>,
}

impl ParseError {
    pub fn at(source: &str, pos: usize, line: usize, kind: ParseErrorKind, msg: String) -> Self {
        let lines: Vec<&str> = source.lines().collect();
        let start = line.saturating_sub(2).max(1);
        let end = (line + 1).min(lines.len());
        let context = lines[start - 1..end].iter().map(|s| s.to_string()).collect();
        let suggestion = Self::suggest(&msg, source, pos);
        Self { kind, line, col: 0, msg, context, suggestion }
    }

    fn suggest(msg: &str, _source: &str, _pos: usize) -> Option<String> {
        if msg.contains("Expected keyword") {
            Some("check for typos or missing declarations".to_string())
        } else if msg.contains("Expected identifier") {
            Some("identifiers must start with a letter or underscore".to_string())
        } else if msg.contains("Expected '") {
            Some("check for missing brackets, quotes, or delimiters".to_string())
        } else {
            None
        }
    }
}

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let title = match self.kind {
            ParseErrorKind::UnexpectedToken => "Unexpected token",
            ParseErrorKind::UnclosedBlock => "Unclosed block",
            ParseErrorKind::InvalidSyntax => "Invalid syntax",
        };
        writeln!(f, "{} at line {}: {}", title, self.line, self.msg)?;
        if !self.context.is_empty() {
            writeln!(f)?;
            let offset = self.line.saturating_sub(self.context.len().saturating_sub(1)).max(1);
            for (i, line_text) in self.context.iter().enumerate() {
                let line_no = offset + i;
                let marker = if line_no == self.line { "-->" } else { "   " };
                writeln!(f, "{} {:>3} | {}", marker, line_no, line_text)?;
            }
        }
        if let Some(ref s) = self.suggestion {
            writeln!(f)?;
            writeln!(f, "help: {}", s)?;
        }
        Ok(())
    }
}

impl std::error::Error for ParseError {}

/// Parse AXON source text into IR.
pub fn parse_source(source: &str) -> Result<AxonIR, ParseError> {
    let mut parser = Parser::new(source);
    parser.parse()
}

struct Parser<'a> {
    source: &'a str,
    pos: usize,
    line: usize,
}

impl<'a> Parser<'a> {
    fn new(source: &'a str) -> Self {
        Self { source, pos: 0, line: 1 }
    }

    fn parse(&mut self) -> Result<AxonIR, ParseError> {
        let mut ir = AxonIR::default();
        let mut annotations: Vec<Annotation> = Vec::new();
        self.skip_ws_and_comments();
        while self.pos < self.source.len() {
            self.skip_ws_and_comments();
            if self.pos >= self.source.len() { break; }
            if self.starts_with("@") {
                annotations.push(self.parse_annotation()?);
                continue;
            }
            if self.starts_with("import") {
                if !annotations.is_empty() {
                    return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, "Annotations are not valid before import".to_string()));
                }
                ir.imports.push(self.parse_import()?);
            } else if self.starts_with("type") {
                if !annotations.is_empty() {
                    return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, "Annotations are not valid before type alias".to_string()));
                }
                ir.type_aliases.push(self.parse_type_alias()?);
            } else if self.starts_with("rag") {
                ir.rags.push(self.parse_rag(annotations)?);
                annotations = Vec::new();
            } else if self.starts_with("prompt") {
                ir.prompts.push(self.parse_prompt(annotations)?);
                annotations = Vec::new();
            } else if self.starts_with("tool") {
                ir.tools.push(self.parse_tool(annotations)?);
                annotations = Vec::new();
            } else if self.starts_with("agent") {
                ir.agents.push(self.parse_agent(annotations)?);
                annotations = Vec::new();
            } else if self.starts_with("flow") {
                ir.flows.push(self.parse_flow(annotations)?);
                annotations = Vec::new();
            } else {
                let peek = self.peek(20);
                return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, format!("Unexpected token: {}", peek)));
            }
            self.skip_ws_and_comments();
        }
        Ok(ir)
    }

    // --- Import ---
    fn parse_import(&mut self) -> Result<ImportDef, ParseError> {
        self.expect_keyword("import")?;
        self.skip_ws();
        self.expect_char('{')?;
        let names_str = self.take_until('}');
        let names: Vec<String> = names_str.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
        self.advance();
        self.skip_ws();
        self.expect_keyword("from")?;
        self.skip_ws();
        let source = self.parse_string()?;
        Ok(ImportDef { kind: "import".to_string(), names, source })
    }

    // --- Type Alias ---
    fn parse_type_alias(&mut self) -> Result<TypeAliasDef, ParseError> {
        self.expect_keyword("type")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        let mut type_params: Vec<String> = Vec::new();
        if self.peek_char() == Some('<') {
            self.advance(); // skip <
            let params_str = self.take_until('>');
            type_params = params_str.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
            self.advance(); // skip >
            self.skip_ws();
        }
        self.expect_char('=')?;
        self.skip_ws();
        let mut value_parts: Vec<char> = Vec::new();
        let mut depth = 0;
        while self.pos < self.source.len() {
            if self.peek_char() == Some('{') {
                depth += 1;
                value_parts.push('{');
                self.advance();
                continue;
            }
            if self.peek_char() == Some('}') {
                depth -= 1;
                value_parts.push('}');
                self.advance();
                if depth == 0 {
                    break;
                }
                continue;
            }
            if (self.peek_char() == Some('\n') || self.peek_char() == Some('\r')) && depth == 0 {
                break;
            }
            if let Some(c) = self.peek_char() {
                value_parts.push(c);
                self.advance();
            }
        }
        let value = value_parts.into_iter().collect::<String>().trim().to_string();
        let fields = Self::extract_record_fields(&value);
        Ok(TypeAliasDef { kind: "type_alias".to_string(), name, type_params, value, fields })
    }

    /// Extract fields from a record type value like `{ id: Int, title: Str }`.
    fn extract_record_fields(value: &str) -> Vec<Param> {
        let trimmed = value.trim();
        if !trimmed.starts_with('{') || !trimmed.ends_with('}') {
            return Vec::new();
        }
        let inner = &trimmed[1..trimmed.len()-1];
        let mut fields: Vec<Param> = Vec::new();
        let mut depth = 0;
        let mut current = String::new();
        for c in inner.chars() {
            if c == '<' || c == '(' { depth += 1; }
            if c == '>' || c == ')' { depth -= 1; }
            if c == ',' && depth == 0 {
                if let Some(field) = Self::parse_field_decl(&current) {
                    fields.push(field);
                }
                current = String::new();
                continue;
            }
            current.push(c);
        }
        if let Some(field) = Self::parse_field_decl(&current) {
            fields.push(field);
        }
        fields
    }

    fn parse_field_decl(text: &str) -> Option<Param> {
        let trimmed = text.trim();
        if trimmed.is_empty() { return None; }
        let colon_pos = trimmed.find(':')?;
        let name = trimmed[..colon_pos].trim().to_string();
        let type_str = trimmed[colon_pos + 1..].trim().to_string();
        Some(Param { name, type_str, default: None })
    }

    // --- RAG ---
    fn parse_rag(&mut self, annotations: Vec<Annotation>) -> Result<RagDef, ParseError> {
        self.expect_keyword("rag")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('{')?;
        let mut source = String::new();
        let mut chunker = String::new();
        let mut embedder = String::new();
        let mut store = String::new();
        let mut methods: Vec<MethodDef> = Vec::new();
        self.skip_ws_and_comments();
        while !self.starts_with("}") && self.pos < self.source.len() {
            self.skip_ws_and_comments();
            if self.starts_with("fn") {
                methods.push(self.parse_method(Vec::new())?);
            } else if self.starts_with("@") {
                let mut method_annotations: Vec<Annotation> = Vec::new();
                while self.starts_with("@") {
                    method_annotations.push(self.parse_annotation()?);
                    self.skip_ws_and_comments();
                }
                if self.starts_with("fn") {
                    methods.push(self.parse_method(method_annotations)?);
                } else {
                    self.take_until_any(&['\n', '\r']);
                }
            } else {
                let key = self.parse_identifier()?;
                self.skip_ws();
                self.expect_char(':')?;
                self.skip_ws();
                let val = self.take_until_any(&['\n', '\r']).trim().to_string();
                match key.as_str() {
                    "source" => source = val,
                    "chunker" => chunker = val,
                    "embedder" => embedder = val,
                    "store" => store = val,
                    _ => {}
                }
            }
            self.skip_ws_and_comments();
        }
        self.expect_char('}')?;
        Ok(RagDef { kind: "rag".to_string(), name, source, chunker, embedder, store, methods, annotations })
    }

    // --- Prompt ---
    fn parse_prompt(&mut self, mut annotations: Vec<Annotation>) -> Result<PromptDef, ParseError> {
        self.expect_keyword("prompt")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('(')?;
        let (params, inline_annotations) = self.parse_prompt_params()?;
        annotations.extend(inline_annotations);
        self.advance();
        self.skip_ws();
        self.expect_str("->")?;
        self.skip_ws();
        let return_type = self.parse_type_str();
        self.skip_ws();
        self.expect_char('{')?;
        self.skip_ws_and_comments();
        let template = self.parse_triple_quoted_string()?;
        self.skip_ws_and_comments();
        self.expect_char('}')?;
        Ok(PromptDef { kind: "prompt".to_string(), name, params, return_type, template, annotations })
    }

    fn parse_prompt_params(&mut self) -> Result<(Vec<Param>, Vec<Annotation>), ParseError> {
        let mut params: Vec<Param> = Vec::new();
        let mut annotations: Vec<Annotation> = Vec::new();
        self.skip_ws();
        while self.peek_char() != Some(')') && self.pos < self.source.len() {
            self.skip_ws();
            if self.starts_with("@") {
                annotations.push(self.parse_annotation()?);
                self.skip_ws();
                if self.peek_char() == Some(',') { self.advance(); }
                continue;
            }
            let name = self.parse_identifier()?;
            self.skip_ws();
            self.expect_char(':')?;
            self.skip_ws();
            let type_str = self.parse_type_str();
            self.skip_ws();
            let default = if self.peek_char() == Some('=') {
                self.advance();
                self.skip_ws();
                let val = self.take_until_any(&[',', ')']).trim().to_string();
                Some(val)
            } else {
                None
            };
            params.push(Param { name, type_str, default });
            self.skip_ws();
            if self.peek_char() == Some(',') { self.advance(); }
            self.skip_ws();
        }
        Ok((params, annotations))
    }

    // --- Tool ---
    fn parse_tool(&mut self, annotations: Vec<Annotation>) -> Result<ToolDef, ParseError> {
        self.expect_keyword("tool")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('(')?;
        let params = self.parse_params(')')?;
        self.advance();
        self.skip_ws();
        self.expect_str("->")?;
        self.skip_ws();
        let return_type = self.parse_type_str();
        self.skip_ws();
        self.expect_char('{')?;
        let mut docstrings: Vec<String> = Vec::new();
        let mut body_lines: Vec<String> = Vec::new();
        self.skip_ws_and_comments();
        let mut brace_depth = 0;
        let mut current_line = String::new();
        while self.pos < self.source.len() {
            if self.starts_with("///") && brace_depth == 0 && current_line.trim().is_empty() {
                self.advance_by(3);
                let line = self.take_until_any(&['\n', '\r']).trim().to_string();
                docstrings.push(line);
                continue;
            }
            if self.starts_with("//") && brace_depth == 0 && current_line.trim().is_empty() {
                self.take_until_any(&['\n', '\r']);
                continue;
            }
            if self.starts_with("{") {
                brace_depth += 1;
                current_line.push('{');
                self.advance();
                continue;
            }
            if self.starts_with("}") {
                if brace_depth == 0 {
                    break;
                }
                brace_depth -= 1;
                current_line.push('}');
                self.advance();
                continue;
            }
            if self.peek_char() == Some('\n') || self.peek_char() == Some('\r') {
                if !current_line.trim().is_empty() {
                    body_lines.push(current_line.trim().to_string());
                }
                current_line = String::new();
                self.advance();
                continue;
            }
            if let Some(c) = self.peek_char() {
                current_line.push(c);
                self.advance();
            }
        }
        if !current_line.trim().is_empty() {
            body_lines.push(current_line.trim().to_string());
        }
        self.expect_char('}')?;
        let body = body_lines.join("\n");
        let body_ast = crate::expression::parse_expression(&body).ok();
        Ok(ToolDef { kind: "tool".to_string(), name, params, return_type, docstrings, body, body_ast, annotations })
    }

    // --- Agent ---
    fn parse_agent(&mut self, annotations: Vec<Annotation>) -> Result<AgentDef, ParseError> {
        self.expect_keyword("agent")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('{')?;
        let mut model = String::new();
        let mut tools: Vec<String> = Vec::new();
        let mut memory: Option<MemoryDecl> = None;
        let mut methods: Vec<MethodDef> = Vec::new();
        self.skip_ws_and_comments();
        while !self.starts_with("}") && self.pos < self.source.len() {
            self.skip_ws_and_comments();
            if self.starts_with("fn") {
                methods.push(self.parse_method(Vec::new())?);
            } else if self.starts_with("@") {
                let mut method_annotations: Vec<Annotation> = Vec::new();
                while self.starts_with("@") {
                    method_annotations.push(self.parse_annotation()?);
                    self.skip_ws_and_comments();
                }
                if self.starts_with("fn") {
                    methods.push(self.parse_method(method_annotations)?);
                } else {
                    // annotations not followed by fn — treat as agent-level
                    self.take_until_any(&['\n', '\r']);
                }
            } else {
                let key = self.parse_identifier()?;
                self.skip_ws();
                self.expect_char(':')?;
                self.skip_ws();
                match key.as_str() {
                    "model" => {
                        let val = self.take_until_any(&['\n', '\r']).trim().to_string();
                        model = val.trim_start_matches('@').to_string();
                    }
                    "tools" => {
                        self.expect_char('[')?;
                        let list = self.take_until(']');
                        tools = list.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
                        self.advance();
                    }
                    "memory" => {
                        let val = self.take_until_any(&['\n', '\r']).trim().to_string();
                        memory = Some(self.parse_memory_decl(&val));
                    }
                    _ => { self.take_until_any(&['\n', '\r']); }
                }
            }
            self.skip_ws_and_comments();
        }
        self.expect_char('}')?;
        Ok(AgentDef { kind: "agent".to_string(), name, model, tools, memory, methods, annotations, workers: None })
    }

    fn parse_memory_decl(&self, text: &str) -> MemoryDecl {
        let mut kind = String::new();
        let mut options: HashMap<String, String> = HashMap::new();
        if let Some(start) = text.find('<') {
            if let Some(end) = text.find('>') {
                kind = text[start + 1..end].trim().to_string();
            }
        }
        if let Some(start) = text.find('(') {
            if let Some(end) = text.rfind(')') {
                let inner = &text[start + 1..end];
                for part in inner.split(',') {
                    let part = part.trim();
                    if let Some(idx) = part.find(':') {
                        let k = part[..idx].trim().to_string();
                        let v = part[idx + 1..].trim().to_string();
                        options.insert(k, v);
                    }
                }
            }
        }
        MemoryDecl { kind, options }
    }

    // --- Flow ---
    fn parse_flow(&mut self, annotations: Vec<Annotation>) -> Result<FlowDef, ParseError> {
        self.expect_keyword("flow")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('(')?;
        let params = self.parse_params(')')?;
        self.advance();
        self.skip_ws();
        self.expect_str("->")?;
        self.skip_ws();
        let return_type = self.parse_type_str();
        self.skip_ws();
        self.expect_char('{')?;
        let mut stages: Vec<StageDef> = Vec::new();
        let mut edges: Vec<FlowEdge> = Vec::new();
        self.skip_ws_and_comments();
        while !self.starts_with("}") && self.pos < self.source.len() {
            self.skip_ws_and_comments();
            if self.starts_with("stage") {
                stages.push(self.parse_stage()?);
            } else {
                let line = self.take_until_any(&['\n', '\r']).trim().to_string();
                if line.contains("->") {
                    let parts: Vec<&str> = line.split("->").collect();
                    if parts.len() == 2 {
                        edges.push(FlowEdge { from_stage: parts[0].trim().to_string(), to_stage: parts[1].trim().to_string() });
                    }
                }
            }
            self.skip_ws_and_comments();
        }
        self.expect_char('}')?;
        Ok(FlowDef { kind: "flow".to_string(), name, params, return_type, stages, edges, annotations })
    }

    fn parse_stage(&mut self) -> Result<StageDef, ParseError> {
        self.expect_keyword("stage")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('(')?;
        let params = self.parse_params(')')?;
        self.advance();
        self.skip_ws();
        self.expect_str("->")?;
        self.skip_ws();
        let return_type = self.parse_type_str();
        Ok(StageDef { name, params, return_type })
    }

    // --- Annotation ---
    fn parse_annotation(&mut self) -> Result<Annotation, ParseError> {
        self.expect_char('@')?;
        let name = self.parse_identifier()?;
        self.skip_ws();
        let mut args = HashMap::new();
        if self.peek_char() == Some('(') {
            self.advance(); // skip (
            let inner = self.take_until(')');
            self.advance(); // skip )
            // parse key: val, key: val
            for part in inner.split(',') {
                let part = part.trim();
                if let Some(idx) = part.find(':') {
                    let k = part[..idx].trim().to_string();
                    let v = part[idx + 1..].trim().to_string();
                    args.insert(k, v);
                }
            }
        }
        Ok(Annotation { name, args })
    }

    // --- Method (shared by agent, rag) ---
    fn parse_method(&mut self, annotations: Vec<Annotation>) -> Result<MethodDef, ParseError> {
        self.expect_keyword("fn")?;
        self.skip_ws();
        let name = self.parse_identifier()?;
        self.skip_ws();
        self.expect_char('(')?;
        let params = self.parse_params(')')?;
        self.advance();
        self.skip_ws();
        self.expect_str("->")?;
        self.skip_ws();
        let return_type = self.parse_type_str();
        self.skip_ws();
        self.expect_char('{')?;
        let mut body_lines: Vec<String> = Vec::new();
        let mut brace_depth = 0;
        let mut current_line = String::new();
        while self.pos < self.source.len() {
            if (self.starts_with("///") || self.starts_with("//")) && brace_depth == 0 && current_line.trim().is_empty() {
                self.take_until_any(&['\n', '\r']);
                continue;
            }
            if self.starts_with("{") {
                brace_depth += 1;
                current_line.push('{');
                self.advance();
                continue;
            }
            if self.starts_with("}") {
                if brace_depth == 0 {
                    break;
                }
                brace_depth -= 1;
                current_line.push('}');
                self.advance();
                continue;
            }
            if self.peek_char() == Some('\n') || self.peek_char() == Some('\r') {
                body_lines.push(current_line.clone());
                current_line = String::new();
                self.advance();
                continue;
            }
            if let Some(c) = self.peek_char() {
                current_line.push(c);
                self.advance();
            }
        }
        body_lines.push(current_line);
        self.expect_char('}')?;
        // Python-style dedent: strip common leading whitespace
        let raw_body = body_lines.join("\n");
        let body = dedent(&raw_body);
        let body_ast = crate::expression::parse_expression(&body).ok();
        Ok(MethodDef { name, params, return_type, body, body_ast, annotations })
    }

    // --- Params ---
    fn parse_params(&mut self, end_char: char) -> Result<Vec<Param>, ParseError> {
        let mut params: Vec<Param> = Vec::new();
        self.skip_ws();
        while self.peek_char().is_none_or(|c| c != end_char) {
            self.skip_ws();
            if self.starts_with("@") {
                self.advance(); // skip @
                self.parse_identifier()?; // annotation name
                self.skip_ws();
                if self.peek_char() == Some('(') {
                    self.advance(); // skip (
                    self.take_until(')');
                    self.advance(); // skip )
                }
                self.skip_ws();
                if self.peek_char() == Some(',') { self.advance(); }
                continue;
            }
            let name = self.parse_identifier()?;
            self.skip_ws();
            self.expect_char(':')?;
            self.skip_ws();
            let type_str = self.parse_type_str();
            self.skip_ws();
            let default = if self.peek_char() == Some('=') {
                self.advance();
                self.skip_ws();
                let val = self.take_until_any(&[',', end_char]).trim().to_string();
                Some(val)
            } else {
                None
            };
            params.push(Param { name, type_str, default });
            self.skip_ws();
            if self.peek_char() == Some(',') { self.advance(); }
            self.skip_ws();
        }
        Ok(params)
    }

    // --- Helpers ---
    fn starts_with(&self, s: &str) -> bool { self.source[self.pos..].starts_with(s) }
    fn peek(&self, n: usize) -> String { self.source[self.pos..].chars().take(n).collect() }
    fn peek_char(&self) -> Option<char> { self.source[self.pos..].chars().next() }
    fn advance(&mut self) {
        if let Some(c) = self.source[self.pos..].chars().next() {
            if c == '\n' { self.line += 1; }
            self.pos += c.len_utf8();
        }
    }
    fn advance_by(&mut self, n: usize) { for _ in 0..n { self.advance(); } }

    fn skip_ws(&mut self) {
        while let Some(c) = self.peek_char() {
            if c.is_whitespace() { self.advance(); } else { break; }
        }
    }

    fn skip_ws_and_comments(&mut self) {
        loop {
            self.skip_ws();
            if self.starts_with("//") && !self.starts_with("///") {
                self.take_until_any(&['\n', '\r']);
            } else { break; }
        }
    }

    fn expect_keyword(&mut self, kw: &str) -> Result<(), ParseError> {
        if !self.starts_with(kw) {
            return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, format!("Expected keyword '{}'", kw)));
        }
        self.advance_by(kw.len());
        Ok(())
    }

    fn expect_char(&mut self, expected: char) -> Result<(), ParseError> {
        if self.peek_char() != Some(expected) {
            return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, format!("Expected '{}'", expected)));
        }
        self.advance();
        Ok(())
    }

    fn expect_str(&mut self, s: &str) -> Result<(), ParseError> {
        if !self.starts_with(s) {
            return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, format!("Expected '{}'", s)));
        }
        self.advance_by(s.len());
        Ok(())
    }

    fn parse_identifier(&mut self) -> Result<String, ParseError> {
        let start = self.pos;
        if let Some(c) = self.peek_char() {
            if !c.is_alphabetic() && c != '_' {
                return Err(ParseError::at(self.source, self.pos, self.line, ParseErrorKind::UnexpectedToken, "Expected identifier".to_string()));
            }
            self.advance();
            while let Some(c) = self.peek_char() {
                if c.is_alphanumeric() || c == '_' { self.advance(); } else { break; }
            }
        }
        Ok(self.source[start..self.pos].to_string())
    }

    fn parse_string(&mut self) -> Result<String, ParseError> {
        self.expect_char('"')?;
        let start = self.pos;
        while let Some(c) = self.peek_char() {
            if c == '"' { break; }
            self.advance();
        }
        let val = self.source[start..self.pos].to_string();
        self.expect_char('"')?;
        Ok(val)
    }

    fn parse_triple_quoted_string(&mut self) -> Result<String, ParseError> {
        self.expect_str("\"\"\"")?;
        let start = self.pos;
        while !self.starts_with("\"\"\"") && self.pos < self.source.len() { self.advance(); }
        let val = self.source[start..self.pos].to_string();
        if self.starts_with("\"\"\"") { self.advance_by(3); }
        Ok(dedent(&val))
    }

    fn parse_type_str(&mut self) -> String {
        let start = self.pos;
        let mut depth = 0;
        while let Some(c) = self.peek_char() {
            if c == '<' || c == '(' { depth += 1; self.advance(); }
            else if c == '>' || c == ')' {
                if depth > 0 { depth -= 1; self.advance(); }
                else { break; }
            }
            else if c == '{' || c == ',' || c == '\n' || c == '\r' || c == '=' {
                if depth == 0 { break; } else { self.advance(); }
            }
            else { self.advance(); }
        }
        self.source[start..self.pos].trim().to_string()
    }

    fn take_until(&mut self, c: char) -> String {
        let start = self.pos;
        while let Some(ch) = self.peek_char() {
            if ch == c { break; }
            self.advance();
        }
        self.source[start..self.pos].to_string()
    }

    fn take_until_any(&mut self, chars: &[char]) -> String {
        let start = self.pos;
        while let Some(ch) = self.peek_char() {
            if chars.contains(&ch) { break; }
            self.advance();
        }
        self.source[start..self.pos].to_string()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_source() {
        let ir = parse_source("").unwrap();
        assert_eq!(ir.version, "0.2.0");
        assert!(ir.agents.is_empty());
        assert!(ir.tools.is_empty());
    }

    #[test]
    fn test_tool_and_agent() {
        let src = r#"
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.tools.len(), 1);
        assert_eq!(ir.tools[0].name, "Greet");
        assert_eq!(ir.tools[0].docstrings, vec!["Says hello."]);
        assert_eq!(ir.tools[0].body, "\"Hello, {name}!\"");
        assert_eq!(ir.agents.len(), 1);
        assert_eq!(ir.agents[0].name, "Bot");
        assert_eq!(ir.agents[0].model, "mock/gpt");
        assert_eq!(ir.agents[0].tools, vec!["Greet"]);
        assert_eq!(ir.agents[0].methods.len(), 1);
        assert_eq!(ir.agents[0].methods[0].name, "run");
    }

    #[test]
    fn test_import_and_type_alias() {
        let src = r#"
import { Chunk } from "axon:types"
type Response = { msg: Str }
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.imports.len(), 1);
        assert_eq!(ir.imports[0].names, vec!["Chunk"]);
        assert_eq!(ir.imports[0].source, "axon:types");
        assert_eq!(ir.type_aliases.len(), 1);
        assert_eq!(ir.type_aliases[0].name, "Response");
        assert_eq!(ir.type_aliases[0].value, "{ msg: Str }");
    }

    #[test]
    fn test_flow() {
        let src = "flow Pipeline(q: Str) -> Str {\n    stage A(q: Str) -> Str\n    stage B(q: Str) -> Str\n    A -> B\n}\n";
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.flows.len(), 1);
        assert_eq!(ir.flows[0].name, "Pipeline");
        assert_eq!(ir.flows[0].stages.len(), 2);
        assert_eq!(ir.flows[0].edges.len(), 1);
        assert_eq!(ir.flows[0].edges[0].from_stage, "A");
        assert_eq!(ir.flows[0].edges[0].to_stage, "B");
    }

    #[test]
    fn test_memory() {
        let src = r#"
agent Bot {
    model: @mock/gpt
    memory: Memory<ShortTerm>(capacity: 100)
    fn run() -> Str { "ok" }
}
"#;
        let ir = parse_source(src).unwrap();
        let mem = ir.agents[0].memory.as_ref().unwrap();
        assert_eq!(mem.kind, "ShortTerm");
        assert_eq!(mem.options.get("capacity"), Some(&"100".to_string()));
    }

    #[test]
    fn test_method_annotations() {
        let src = r#"
agent Bot {
    model: @mock/gpt

    @schedule(every: 5.minutes)
    @trace
    fn run() -> Str { "ok" }
}
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.agents.len(), 1);
        assert_eq!(ir.agents[0].methods.len(), 1);
        let m = &ir.agents[0].methods[0];
        assert_eq!(m.name, "run");
        assert_eq!(m.annotations.len(), 2);
        assert_eq!(m.annotations[0].name, "schedule");
        assert_eq!(m.annotations[0].args.get("every"), Some(&"5.minutes".to_string()));
        assert_eq!(m.annotations[1].name, "trace");
        assert!(m.annotations[1].args.is_empty());
    }

    #[test]
    fn test_empty_tools_list() {
        let src = r#"
agent Bot {
    model: @mock/gpt
    tools: []
    fn run() -> Str { "ok" }
}
"#;
        let ir = parse_source(src).unwrap();
        assert!(ir.agents[0].tools.is_empty());
    }

    #[test]
    fn test_top_level_annotations() {
        let src = r#"
@managed
agent Bot {
    model: @mock/gpt
    tools: []
    fn run() -> Str { "ok" }
}

@cache(ttl: 300)
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.agents[0].annotations.len(), 1);
        assert_eq!(ir.agents[0].annotations[0].name, "managed");
        assert_eq!(ir.tools[0].annotations.len(), 1);
        assert_eq!(ir.tools[0].annotations[0].name, "cache");
        assert_eq!(ir.tools[0].annotations[0].args.get("ttl"), Some(&"300".to_string()));
    }

    #[test]
    fn test_annotation_reset_between_decls() {
        let src = r#"
@managed
agent Bot {
    model: @mock/gpt
    tools: []
    fn run() -> Str { "ok" }
}

tool Plain(x: Str) -> Str { x }
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.agents[0].annotations.len(), 1);
        assert!(ir.tools[0].annotations.is_empty());
    }

    #[test]
    fn test_type_alias_rejects_annotation() {
        let src = "@trace\ntype Bad = Str";
        assert!(parse_source(src).is_err());
    }

    #[test]
    fn test_record_type_alias_fields() {
        let src = r#"
type Issue = {
    id: Int,
    title: Str,
    priority: Priority,
    labels: List<Str>
}
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.type_aliases.len(), 1);
        let ta = &ir.type_aliases[0];
        assert_eq!(ta.name, "Issue");
        assert_eq!(ta.fields.len(), 4);
        assert_eq!(ta.fields[0].name, "id");
        assert_eq!(ta.fields[0].type_str, "Int");
        assert_eq!(ta.fields[1].name, "title");
        assert_eq!(ta.fields[2].name, "priority");
        assert_eq!(ta.fields[3].name, "labels");
        assert_eq!(ta.fields[3].type_str, "List<Str>");
    }

    #[test]
    fn test_non_record_type_alias_no_fields() {
        let src = "type UserName = Str\n";
        let ir = parse_source(src).unwrap();
        assert!(ir.type_aliases[0].fields.is_empty());
    }

    #[test]
    fn test_nested_generics_in_record_fields() {
        let src = r#"
type Config = {
    mapping: Map<Str, List<Int>>,
    nested: Result<Option<Str>, Error>
}
"#;
        let ir = parse_source(src).unwrap();
        let ta = &ir.type_aliases[0];
        assert_eq!(ta.fields.len(), 2);
        assert_eq!(ta.fields[0].name, "mapping");
        assert_eq!(ta.fields[0].type_str, "Map<Str, List<Int>>");
        assert_eq!(ta.fields[1].type_str, "Result<Option<Str>, Error>");
    }

    #[test]
    fn test_comments_ignored_everywhere() {
        let src = r#"
// top-level comment
agent Bot {
    // inline before property
    model: @mock/gpt
    tools: [] // inline comment
    fn run() -> Str { "ok" }
}
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.agents[0].name, "Bot");
        // @ is stripped to match Python IR compiler behavior
        assert_eq!(ir.agents[0].model, "mock/gpt");
    }

    #[test]
    fn test_unicode_in_string_literal() {
        let src = r#"
tool Greet(name: Str) -> Str {
    /// Says hello in Japanese.
    "Hello, {name}!"
}
"#;
        let ir = parse_source(src).unwrap();
        assert!(ir.tools[0].docstrings[0].contains("Japanese"));
    }

    #[test]
    fn test_multiple_type_params() {
        let src = "type Pair<A, B> = { first: A, second: B }\n";
        let ir = parse_source(src).unwrap();
        let ta = &ir.type_aliases[0];
        assert_eq!(ta.name, "Pair");
        assert_eq!(ta.fields.len(), 2);
        assert_eq!(ta.fields[0].type_str, "A");
        assert_eq!(ta.fields[1].type_str, "B");
    }

    #[test]
    fn test_tool_with_multiple_docstrings() {
        let src = r#"
tool Sum(a: Int, b: Int) -> Int {
    /// Computes the sum.
    /// Second line of docs.
    a + b
}
"#;
        let ir = parse_source(src).unwrap();
        assert_eq!(ir.tools[0].docstrings.len(), 2);
        assert_eq!(ir.tools[0].docstrings[0], "Computes the sum.");
        assert_eq!(ir.tools[0].docstrings[1], "Second line of docs.");
    }

    #[test]
    fn test_empty_ir_from_empty_source() {
        let ir = parse_source("").unwrap();
        assert!(ir.imports.is_empty());
        assert!(ir.type_aliases.is_empty());
        assert!(ir.agents.is_empty());
    }

}

// ---------------------------------------------------------------------------
// WASM Bindings
// ---------------------------------------------------------------------------

#[cfg(feature = "wasm")]
pub mod wasm {
    use wasm_bindgen::prelude::*;
    use crate::parse_source;
    use crate::expression::parse_expression;

    /// Parse AXON source text and return IR JSON.
    #[wasm_bindgen]
    pub fn parse_axon(source: &str) -> Result<String, String> {
        match parse_source(source) {
            Ok(ir) => match serde_json::to_string_pretty(&ir) {
                Ok(json) => Ok(json),
                Err(e) => Err(format!("Serialization error: {}", e)),
            },
            Err(e) => Err(format!("Parse error: {}", e)),
        }
    }

    /// Parse a single AXON expression and return AST JSON.
    #[wasm_bindgen]
    pub fn parse_expr(source: &str) -> Result<String, String> {
        match parse_expression(source) {
            Ok(ast) => match serde_json::to_string_pretty(&ast) {
                Ok(json) => Ok(json),
                Err(e) => Err(format!("Serialization error: {}", e)),
            },
            Err(e) => Err(format!("Expression parse error: {}", e)),
        }
    }
}

// ---------------------------------------------------------------------------
// pyo3 Python Bindings
// ---------------------------------------------------------------------------

#[cfg(feature = "python")]
pub mod python {
    use pyo3::prelude::*;
    use crate::parse_source;
    use crate::expression::parse_expression;

    /// Parse AXON source text and return IR as a Python dict.
    #[pyfunction]
    fn parse_axon(source: &str) -> PyResult<Py<PyAny>> {
        match parse_source(source) {
            Ok(ir) => {
                Python::with_gil(|py| {
                    let json = serde_json::to_string(&ir)
                        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("serialization: {}", e)))?;
                    let json_mod = py.import("json")?;
                    let dict = json_mod.getattr("loads")?.call1((json,))?;
                    Ok(dict.into())
                })
            }
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string())),
        }
    }

    /// Parse a single AXON expression and return AST as a Python dict.
    #[pyfunction]
    fn parse_expr(source: &str) -> PyResult<Py<PyAny>> {
        match parse_expression(source) {
            Ok(ast) => {
                Python::with_gil(|py| {
                    let json = serde_json::to_string(&ast)
                        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("serialization: {}", e)))?;
                    let json_mod = py.import("json")?;
                    let dict = json_mod.getattr("loads")?.call1((json,))?;
                    Ok(dict.into())
                })
            }
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string())),
        }
    }

    #[pymodule]
    fn axon_parser(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(parse_axon, m)?)?;
        m.add_function(wrap_pyfunction!(parse_expr, m)?)?;
        Ok(())
    }
}

