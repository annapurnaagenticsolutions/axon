//! Static validation for AXON declarations.
//!
//! Performs lightweight semantic checks across the parsed IR before
//! code generation or runtime execution.

use serde::{Deserialize, Serialize};
use crate::{
    AgentDef, FlowDef, ImportDef, PromptDef, RagDef, ToolDef,
    Annotation, AxonIR,
};

// ---------------------------------------------------------------------------
// Diagnostic
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct Diagnostic {
    pub severity: String,
    pub message: String,
    #[serde(default)]
    pub line: i32,
    #[serde(default)]
    pub code: String,
    #[serde(default)]
    pub hint: String,
    #[serde(default)]
    pub related: Vec<String>,
}

impl Diagnostic {
    pub fn error(message: impl Into<String>, line: i32, code: &str) -> Self {
        Self { severity: "error".into(), message: message.into(), line, code: code.into(), hint: String::new(), related: Vec::new() }
    }
    pub fn warning(message: impl Into<String>, line: i32, code: &str) -> Self {
        Self { severity: "warning".into(), message: message.into(), line, code: code.into(), hint: String::new(), related: Vec::new() }
    }
    pub fn with_hint(mut self, hint: impl Into<String>) -> Self { self.hint = hint.into(); self }
    pub fn with_related(mut self, related: Vec<String>) -> Self { self.related = related; self }
    pub fn is_error(&self) -> bool { self.severity == "error" }
    pub fn format(&self) -> String {
        let loc = if self.line > 0 { format!("line {}: ", self.line) } else { String::new() };
        let code = if self.code.is_empty() { String::new() } else { format!(" [{}]", self.code) };
        let hint = if self.hint.is_empty() { String::new() } else { format!("\n  hint: {}", self.hint) };
        let related = if self.related.is_empty() { String::new() } else { format!("\n  {}", self.related.join("\n  ")) };
        format!("{}: {}{}{}{}{}", self.severity, loc, self.message, code, hint, related)
    }
}

const KNOWN_ANNOTATIONS: &[&str] = &["budget", "schedule", "trace", "managed", "retry", "timeout", "cache"];

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn validate(ir: &AxonIR) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    diags.extend(validate_duplicate_top_level(ir));
    diags.extend(validate_imports(&ir.imports));
    diags.extend(validate_tools(&ir.tools));
    diags.extend(validate_agents(&ir.agents, &ir.tools, &ir.imports, &ir.rags));
    diags.extend(validate_prompts(&ir.prompts));
    diags.extend(validate_rags(&ir.rags));
    diags.extend(validate_flows(&ir.flows));
    diags
}

pub fn validate_source(source: &str) -> Result<Vec<Diagnostic>, String> {
    let ir = crate::parse_source(source).map_err(|e| e.to_string())?;
    Ok(validate(&ir))
}

pub fn has_errors(diagnostics: &[Diagnostic]) -> bool {
    diagnostics.iter().any(|d| d.is_error())
}

// ---------------------------------------------------------------------------
// Duplicate top-level declarations
// ---------------------------------------------------------------------------

fn validate_duplicate_top_level(ir: &AxonIR) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    let mut seen: std::collections::HashMap<String, (String, i32)> = std::collections::HashMap::new();

    for t in &ir.type_aliases {
        if t.name.is_empty() { continue; }
        if let Some((prev_kind, prev_line)) = seen.get(&t.name) {
            diags.push(Diagnostic::error(
                format!("duplicate declaration '{}' conflicts with previous {} declaration at line {}", t.name, prev_kind, prev_line),
                0, "duplicate-declaration",
            ).with_hint(format!("Rename one of the '{}' declarations to avoid the conflict.", t.name)));
        } else { seen.insert(t.name.clone(), ("type_alias".to_string(), 0)); }
    }
    for r in &ir.rags {
        if r.name.is_empty() { continue; }
        if let Some((prev_kind, prev_line)) = seen.get(&r.name) {
            diags.push(Diagnostic::error(
                format!("duplicate declaration '{}' conflicts with previous {} declaration at line {}", r.name, prev_kind, prev_line),
                0, "duplicate-declaration",
            ).with_hint(format!("Rename one of the '{}' declarations to avoid the conflict.", r.name)));
        } else { seen.insert(r.name.clone(), ("rag".to_string(), 0)); }
    }
    for p in &ir.prompts {
        if p.name.is_empty() { continue; }
        if let Some((prev_kind, prev_line)) = seen.get(&p.name) {
            diags.push(Diagnostic::error(
                format!("duplicate declaration '{}' conflicts with previous {} declaration at line {}", p.name, prev_kind, prev_line),
                0, "duplicate-declaration",
            ).with_hint(format!("Rename one of the '{}' declarations to avoid the conflict.", p.name)));
        } else { seen.insert(p.name.clone(), ("prompt".to_string(), 0)); }
    }
    for t in &ir.tools {
        if t.name.is_empty() { continue; }
        if let Some((prev_kind, prev_line)) = seen.get(&t.name) {
            diags.push(Diagnostic::error(
                format!("duplicate declaration '{}' conflicts with previous {} declaration at line {}", t.name, prev_kind, prev_line),
                0, "duplicate-declaration",
            ).with_hint(format!("Rename one of the '{}' declarations to avoid the conflict.", t.name)));
        } else { seen.insert(t.name.clone(), ("tool".to_string(), 0)); }
    }
    for a in &ir.agents {
        if a.name.is_empty() { continue; }
        if let Some((prev_kind, prev_line)) = seen.get(&a.name) {
            diags.push(Diagnostic::error(
                format!("duplicate declaration '{}' conflicts with previous {} declaration at line {}", a.name, prev_kind, prev_line),
                0, "duplicate-declaration",
            ).with_hint(format!("Rename one of the '{}' declarations to avoid the conflict.", a.name)));
        } else { seen.insert(a.name.clone(), ("agent".to_string(), 0)); }
    }
    for f in &ir.flows {
        if f.name.is_empty() { continue; }
        if let Some((prev_kind, prev_line)) = seen.get(&f.name) {
            diags.push(Diagnostic::error(
                format!("duplicate declaration '{}' conflicts with previous {} declaration at line {}", f.name, prev_kind, prev_line),
                0, "duplicate-declaration",
            ).with_hint(format!("Rename one of the '{}' declarations to avoid the conflict.", f.name)));
        } else { seen.insert(f.name.clone(), ("flow".to_string(), 0)); }
    }

    diags
}

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

fn validate_imports(imports: &[ImportDef]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    for imp in imports {
        for name in &imp.names {
            if seen.contains(name) {
                diags.push(Diagnostic::warning(
                    format!("import '{}' appears more than once", name), 0, "duplicate-import",
                ));
            } else { seen.insert(name.clone()); }
        }
    }
    diags
}

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

fn validate_tools(tools: &[ToolDef]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for tool in tools {
        if tool.docstrings.is_empty() {
            diags.push(Diagnostic::error(
                format!("tool '{}' must include at least one /// docstring line", tool.name), 0, "missing-tool-docstring",
            ).with_hint(r#"Add a docstring using /// before the tool body."#));
        }
        for line in &tool.docstrings {
            if line.trim().is_empty() {
                diags.push(Diagnostic::warning(
                    format!("tool '{}' contains an empty docstring line", tool.name), 0, "empty-tool-docstring-line",
                ).with_hint("Remove empty /// lines or add descriptive text."));
                break;
            }
        }
        diags.extend(validate_annotations(&tool.annotations, &format!("tool '{}'", tool.name), 0));
    }
    diags
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

fn known_tool_references(tools: &[ToolDef], imports: &[ImportDef], rags: &[RagDef]) -> std::collections::HashSet<String> {
    let mut known: std::collections::HashSet<String> = std::collections::HashSet::new();
    for t in tools { known.insert(t.name.clone()); }
    for imp in imports { for name in &imp.names { known.insert(name.clone()); } }
    for rag in rags { for method in &rag.methods { known.insert(format!("{}.{}", rag.name, method.name)); } }
    known
}

fn validate_agents(agents: &[AgentDef], tools: &[ToolDef], imports: &[ImportDef], rags: &[RagDef]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    let known_tools = known_tool_references(tools, imports, rags);

    for agent in agents {
        diags.extend(validate_annotations(&agent.annotations, &format!("agent '{}'", agent.name), 0));

        if agent.model.trim().is_empty() {
            diags.push(Diagnostic::error(
                format!("agent '{}' must declare a model", agent.name), 0, "missing-agent-model",
            ).with_hint("Add a model declaration, e.g., model: @anthropic/claude-4"));
        }

        if agent.methods.is_empty() {
            diags.push(Diagnostic::error(
                format!("agent '{}' must define at least one method", agent.name), 0, "missing-agent-method",
            ).with_hint("Add a method, e.g., fn run(query: Str) -> Str { ... }"));
        }

        let mut seen_tool_refs: std::collections::HashSet<String> = std::collections::HashSet::new();
        for tool_ref in &agent.tools {
            if seen_tool_refs.contains(tool_ref) {
                diags.push(Diagnostic::warning(
                    format!("agent '{}' lists tool '{}' more than once", agent.name, tool_ref), 0, "duplicate-agent-tool",
                ));
            }
            seen_tool_refs.insert(tool_ref.clone());

            if !known_tools.contains(tool_ref) {
                let related = if known_tools.is_empty() { Vec::new() } else {
                    let mut sorted: Vec<String> = known_tools.iter().cloned().collect();
                    sorted.sort();
                    vec![format!("Available tools: {}", sorted.join(", "))]
                };
                diags.push(Diagnostic::error(
                    format!("agent '{}' references unknown tool '{}'", agent.name, tool_ref), 0, "unknown-agent-tool",
                ).with_hint(format!("Define a tool named '{}' or import it from axon:tools/", tool_ref))
                 .with_related(related));
            }
        }

        let mut method_names: std::collections::HashSet<String> = std::collections::HashSet::new();
        for method in &agent.methods {
            if method_names.contains(&method.name) {
                diags.push(Diagnostic::error(
                    format!("agent '{}' has duplicate method '{}' previously declared in the same agent", agent.name, method.name),
                    0, "duplicate-agent-method",
                ));
            }
            method_names.insert(method.name.clone());
            diags.extend(validate_annotations(&method.annotations, &format!("method '{}.{}'", agent.name, method.name), 0));
        }
    }
    diags
}

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

fn validate_prompts(prompts: &[PromptDef]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for prompt in prompts {
        diags.extend(validate_annotations(&prompt.annotations, &format!("prompt '{}'", prompt.name), 0));
        diags.extend(validate_prompt_budget(prompt));
        diags.extend(validate_prompt_interpolations(prompt));
    }
    diags
}

fn validate_prompt_budget(prompt: &PromptDef) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for ann in &prompt.annotations {
        if ann.name != "budget" { continue; }
        match ann.args.get("tokens") {
            None => {
                diags.push(Diagnostic::error(
                    format!("prompt '{}' @budget annotation requires tokens: N", prompt.name), 0, "missing-budget-tokens",
                ));
            }
            Some(tokens) => {
                if !is_positive_integer(tokens.trim()) {
                    diags.push(Diagnostic::error(
                        format!("prompt '{}' @budget tokens must be a positive integer", prompt.name), 0, "invalid-budget-tokens",
                    ));
                }
            }
        }
    }
    diags
}

fn validate_prompt_interpolations(prompt: &PromptDef) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    let param_names: std::collections::HashSet<String> = prompt.params.iter().map(|p| p.name.clone()).collect();
    for expr in template_interpolations(&prompt.template) {
        if let Some(root_name) = parse_template_var(&expr) {
            if !param_names.contains(&root_name) {
                diags.push(Diagnostic::error(
                    format!("prompt '{}' references unknown template variable '{{{}}}'", prompt.name, expr), 0, "unknown-prompt-variable",
                ));
            }
        }
    }
    diags
}

// ---------------------------------------------------------------------------
// RAGs
// ---------------------------------------------------------------------------

fn validate_rags(rags: &[RagDef]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for rag in rags {
        diags.extend(validate_annotations(&rag.annotations, &format!("rag '{}'", rag.name), 0));
        if rag.source.trim().is_empty() {
            diags.push(Diagnostic::error(
                format!("rag '{}' must declare a source", rag.name), 0, "missing-rag-source",
            ).with_hint("Add a source path, e.g., source: ./docs/"));
        }
        let mut method_names: std::collections::HashSet<String> = std::collections::HashSet::new();
        for method in &rag.methods {
            if method_names.contains(&method.name) {
                diags.push(Diagnostic::error(
                    format!("rag '{}' has duplicate method '{}'", rag.name, method.name), 0, "duplicate-rag-method",
                ));
            }
            method_names.insert(method.name.clone());
        }
    }
    diags
}

// ---------------------------------------------------------------------------
// Flows
// ---------------------------------------------------------------------------

fn validate_flows(flows: &[FlowDef]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for flow in flows {
        diags.extend(validate_annotations(&flow.annotations, &format!("flow '{}'", flow.name), 0));

        let mut stage_names: std::collections::HashSet<String> = std::collections::HashSet::new();
        for stage in &flow.stages {
            if stage_names.contains(&stage.name) {
                diags.push(Diagnostic::error(
                    format!("flow '{}' has duplicate stage '{}'", flow.name, stage.name), 0, "duplicate-flow-stage",
                ));
            }
            stage_names.insert(stage.name.clone());
        }

        for edge in &flow.edges {
            if !stage_names.contains(&edge.from_stage) {
                diags.push(Diagnostic::error(
                    format!("flow '{}' edge references unknown from_stage '{}'", flow.name, edge.from_stage), 0, "unknown-flow-edge-from",
                ));
            }
            if !stage_names.contains(&edge.to_stage) {
                diags.push(Diagnostic::error(
                    format!("flow '{}' edge references unknown to_stage '{}'", flow.name, edge.to_stage), 0, "unknown-flow-edge-to",
                ));
            }
        }
    }
    diags
}

// ---------------------------------------------------------------------------
// Annotations
// ---------------------------------------------------------------------------

fn validate_annotations(annotations: &[Annotation], context: &str, line: i32) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for ann in annotations {
        if !KNOWN_ANNOTATIONS.contains(&ann.name.as_str()) {
            diags.push(Diagnostic::warning(
                format!("{} has unknown annotation '@{}'", context, ann.name), line, "unknown-annotation",
            ).with_hint(format!("Known annotations: {}", KNOWN_ANNOTATIONS.join(", "))));
        }
    }
    diags
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn is_positive_integer(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
}

/// Extract `{{...}}` interpolation expressions from a template string.
fn template_interpolations(template: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut chars = template.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '{' && chars.peek() == Some(&'{') {
            chars.next();
            let mut expr = String::new();
            let mut depth = 1;
            while let Some(c2) = chars.next() {
                if c2 == '{' { depth += 1; expr.push(c2); }
                else if c2 == '}' { depth -= 1; if depth == 0 { break; } expr.push(c2); }
                else { expr.push(c2); }
            }
            let trimmed = expr.trim().to_string();
            if !trimmed.is_empty() { result.push(trimmed); }
        }
    }
    result
}

/// Parse a template variable expression and return the root identifier name.
/// E.g., "user.name" -> Some("user"), "item" -> Some("item").
fn parse_template_var(expr: &str) -> Option<String> {
    let trimmed = expr.trim();
    if trimmed.is_empty() { return None; }
    let root: String = trimmed.chars().take_while(|c| c.is_alphanumeric() || *c == '_').collect();
    if root.is_empty() { None } else { Some(root) }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_empty() {
        let ir = crate::parse_source("").unwrap();
        let diags = validate(&ir);
        assert!(diags.is_empty(), "Expected no diagnostics for empty source, got: {:?}", diags);
    }

    #[test]
    fn test_duplicate_tool_names() {
        let src = r#"
tool Foo(a: Int) -> Int {
    /// doc
    a
}
tool Foo(b: Int) -> Int {
    /// doc
    b
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        assert!(diags.iter().any(|d| d.code == "duplicate-declaration"), "Expected duplicate-declaration, got: {:?}", diags);
    }

    #[test]
    fn test_missing_tool_docstring() {
        let src = r#"
tool Foo(a: Int) -> Int {
    a
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        assert!(diags.iter().any(|d| d.code == "missing-tool-docstring"), "Expected missing-tool-docstring, got: {:?}", diags);
    }

    #[test]
    fn test_unknown_agent_tool() {
        let src = r#"
agent Bar {
    model: @openai/gpt-4
    tools: [NonExistent]
    fn run(query: Str) -> Str {
        query
    }
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        assert!(diags.iter().any(|d| d.code == "unknown-agent-tool"), "Expected unknown-agent-tool, got: {:?}", diags);
    }

    #[test]
    fn test_valid_agent_with_tool() {
        let src = r#"
tool Greet(name: Str) -> Str {
    /// Says hello
    name
}
agent Bar {
    model: @openai/gpt-4
    tools: [Greet]
    fn run(query: Str) -> Str {
        query
    }
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        let errors: Vec<_> = diags.iter().filter(|d| d.is_error()).collect();
        assert!(errors.is_empty(), "Expected no errors, got: {:?}", errors);
    }

    #[test]
    fn test_duplicate_flow_stage() {
        let src = r#"
flow MyFlow(query: Str) -> Str {
    stage Parse(input: Str) -> Str
    stage Parse(input: Str) -> Str
    Parse -> Parse
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        assert!(diags.iter().any(|d| d.code == "duplicate-flow-stage"), "Expected duplicate-flow-stage, got: {:?}", diags);
    }

    #[test]
    fn test_unknown_prompt_variable() {
        let src = r#"
prompt Greet(name: Str) -> Str {
"""Hello {{nonexistent}}"""
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        assert!(diags.iter().any(|d| d.code == "unknown-prompt-variable"), "Expected unknown-prompt-variable, got: {:?}", diags);
    }

    #[test]
    fn test_valid_prompt_variable() {
        let src = r#"
prompt Greet(name: Str) -> Str {
"""Hello {{name}}"""
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = validate(&ir);
        let errors: Vec<_> = diags.iter().filter(|d| d.is_error()).collect();
        assert!(errors.is_empty(), "Expected no errors, got: {:?}", errors);
    }

    #[test]
    fn test_validate_source_function() {
        let diags = validate_source("tool Foo(a: Int) -> Int { a }").unwrap();
        assert!(diags.iter().any(|d| d.code == "missing-tool-docstring"));
        assert!(has_errors(&diags));
    }
}
