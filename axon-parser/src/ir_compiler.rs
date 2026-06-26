//! IR compiler — compiles AXON source to IR JSON and provides IR-to-AST conversion.
//!
//! In the Rust crate, `parse_source` already produces `AxonIR` directly,
//! so the "compile" step is simply parse + validate. This module provides
//! the `compile_source` function and IR-to-AST-JSON conversion for
//! Python interop via PyO3.

use crate::validator::{self, Diagnostic};
use crate::AxonIR;
use serde_json::{json, Value};

/// Compile AXON source text into IR, running validation.
/// Returns the IR on success, or diagnostics on validation failure.
pub fn compile_source(source: &str) -> Result<AxonIR, Vec<Diagnostic>> {
    let ir = match crate::parse_source(source) {
        Ok(ir) => ir,
        Err(e) => {
            return Err(vec![Diagnostic::error(
                format!("Parse error: {}", e), 0, "parse-error",
            )]);
        }
    };
    let diagnostics = validator::validate(&ir);
    if validator::has_errors(&diagnostics) {
        return Err(diagnostics);
    }
    Ok(ir)
}

/// Compile AXON source and return IR as JSON string.
pub fn compile_to_json(source: &str) -> Result<String, String> {
    match compile_source(source) {
        Ok(ir) => serde_json::to_string_pretty(&ir).map_err(|e| format!("Serialization error: {}", e)),
        Err(diags) => {
            let msgs: Vec<String> = diags.iter().map(|d| d.format()).collect();
            Err(msgs.join("\n"))
        }
    }
}

/// Convert IR JSON back into a JSON representation of AST declarations.
/// This mirrors the Python `ir_to_ast` function for round-trip compatibility.
pub fn ir_to_ast_json(ir_json: &str) -> Result<String, String> {
    let ir: AxonIR = serde_json::from_str(ir_json).map_err(|e| format!("IR parse error: {}", e))?;
    let declarations = ir_to_declarations_json(&ir);
    serde_json::to_string_pretty(&declarations).map_err(|e| format!("Serialization error: {}", e))
}

/// Convert IR to a JSON array of declaration dicts matching Python AST structure.
fn ir_to_declarations_json(ir: &AxonIR) -> Value {
    let mut decls: Vec<Value> = Vec::new();

    for imp in &ir.imports {
        decls.push(json!({
            "kind": "import",
            "names": imp.names,
            "source": imp.source,
        }));
    }

    for ta in &ir.type_aliases {
        decls.push(json!({
            "kind": "type_alias",
            "name": ta.name,
            "type_params": ta.type_params,
            "value": ta.value,
            "fields": ta.fields.iter().map(|p| json!({
                "name": p.name,
                "type_str": p.type_str,
                "default": p.default,
            })).collect::<Vec<_>>(),
            "line": 0,
        }));
    }

    for rag in &ir.rags {
        decls.push(json!({
            "kind": "rag",
            "name": rag.name,
            "source": rag.source,
            "chunker": rag.chunker,
            "embedder": rag.embedder,
            "store": rag.store,
            "annotations": annotations_to_json(&rag.annotations),
            "methods": methods_to_json(&rag.methods),
            "line": 0,
        }));
    }

    for prompt in &ir.prompts {
        decls.push(json!({
            "kind": "prompt",
            "name": prompt.name,
            "params": params_to_json(&prompt.params),
            "return_type": prompt.return_type,
            "template": prompt.template,
            "annotations": annotations_to_json(&prompt.annotations),
            "line": 0,
        }));
    }

    for tool in &ir.tools {
        decls.push(json!({
            "kind": "tool",
            "name": tool.name,
            "params": params_to_json(&tool.params),
            "return_type": tool.return_type,
            "docstrings": tool.docstrings,
            "body": tool.body,
            "annotations": annotations_to_json(&tool.annotations),
            "line": 0,
            "parsed_body": null,
        }));
    }

    for agent in &ir.agents {
        let memory = if let Some(mem) = &agent.memory {
            json!({"kind": mem.kind, "options": mem.options})
        } else {
            Value::Null
        };
        decls.push(json!({
            "kind": "agent",
            "name": agent.name,
            "model": agent.model,
            "tools": agent.tools,
            "memory": memory,
            "annotations": annotations_to_json(&agent.annotations),
            "methods": methods_to_json(&agent.methods),
            "workers": agent.workers,
            "version": agent.version,
            "line": 0,
        }));
    }

    for flow in &ir.flows {
        let arrow_lines: Vec<String> = flow.edges.iter()
            .map(|e| format!("{} -> {}", e.from_stage, e.to_stage))
            .collect();
        let body = arrow_lines.join("\n");
        decls.push(json!({
            "kind": "flow",
            "name": flow.name,
            "params": params_to_json(&flow.params),
            "return_type": flow.return_type,
            "annotations": annotations_to_json(&flow.annotations),
            "stages": flow.stages.iter().map(|s| json!({
                "name": s.name,
                "params": params_to_json(&s.params),
                "return_type": s.return_type,
                "line": 0,
            })).collect::<Vec<_>>(),
            "body": body,
            "parsed_body": null,
            "line": 0,
        }));
    }

    Value::Array(decls)
}

fn annotations_to_json(anns: &[crate::Annotation]) -> Vec<serde_json::Value> {
    anns.iter().map(|a| json!({
        "name": a.name,
        "args": a.args,
    })).collect()
}

fn params_to_json(params: &[crate::Param]) -> Vec<serde_json::Value> {
    params.iter().map(|p| json!({
        "name": p.name,
        "type_str": p.type_str,
        "default": p.default,
    })).collect()
}

fn methods_to_json(methods: &[crate::MethodDef]) -> Vec<serde_json::Value> {
    methods.iter().map(|m| json!({
        "name": m.name,
        "params": params_to_json(&m.params),
        "return_type": m.return_type,
        "body": m.body,
        "annotations": annotations_to_json(&m.annotations),
    })).collect()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compile_valid_source() {
        let src = r#"
tool Add(a: Int, b: Int) -> Int {
    /// Adds two numbers
    a + b
}
"#;
        let result = compile_source(src);
        assert!(result.is_ok(), "Expected Ok, got: {:?}", result.err());
        let ir = result.unwrap();
        assert_eq!(ir.tools.len(), 1);
        assert_eq!(ir.tools[0].name, "Add");
    }

    #[test]
    fn test_compile_invalid_source() {
        let src = r#"
tool Foo(a: Int) -> Int {
    a
}
"#;
        let result = compile_source(src);
        assert!(result.is_err(), "Expected validation error");
        let diags = result.unwrap_err();
        assert!(diags.iter().any(|d| d.code == "missing-tool-docstring"));
    }

    #[test]
    fn test_compile_to_json() {
        let src = r#"
tool Add(a: Int, b: Int) -> Int {
    /// Adds two numbers
    a + b
}
"#;
        let json = compile_to_json(src).unwrap();
        assert!(json.contains("\"name\": \"Add\""));
        assert!(json.contains("\"version\""));
    }

    #[test]
    fn test_ir_to_ast_json() {
        let src = r#"
tool Add(a: Int, b: Int) -> Int {
    /// Adds two numbers
    a + b
}
"#;
        let ir_json = compile_to_json(src).unwrap();
        let ast_json = ir_to_ast_json(&ir_json).unwrap();
        assert!(ast_json.contains("\"kind\": \"tool\""));
        assert!(ast_json.contains("\"name\": \"Add\""));
    }

    #[test]
    fn test_ir_to_ast_with_agent() {
        let src = r#"
tool Greet(name: Str) -> Str {
    /// Says hello
    name
}
agent Bot {
    model: openai/gpt-4
    tools: [Greet]
    fn run(query: Str) -> Str {
        query
    }
}
"#;
        let ir_json = compile_to_json(src).unwrap();
        let ast_json = ir_to_ast_json(&ir_json).unwrap();
        assert!(ast_json.contains("\"kind\": \"agent\""));
        assert!(ast_json.contains("\"kind\": \"tool\""));
    }
}
