//! Static type checker for AXON declarations.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use crate::{
    AgentDef, FlowDef, PromptDef, RagDef, ToolDef, AxonIR,
};
use crate::validator::Diagnostic;
use crate::expression::Expr;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TypeKind {
    Primitive, Generic, Record, Union, Option, Result, Stream, Function, Unknown,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Type {
    pub name: String,
    pub kind: TypeKind,
    #[serde(default)]
    pub args: Vec<Type>,
    #[serde(default)]
    pub fields: HashMap<String, Type>,
}

impl Type {
    pub fn primitive(name: &str) -> Self {
        Type { name: name.into(), kind: TypeKind::Primitive, args: vec![], fields: HashMap::new() }
    }
    pub fn unknown(name: &str) -> Self {
        Type { name: name.into(), kind: TypeKind::Unknown, args: vec![], fields: HashMap::new() }
    }
    pub fn generic(name: &str, args: Vec<Type>) -> Self {
        Type { name: name.into(), kind: TypeKind::Generic, args, fields: HashMap::new() }
    }
    pub fn option(inner: Type) -> Self {
        Type { name: "Option".into(), kind: TypeKind::Option, args: vec![inner], fields: HashMap::new() }
    }
    pub fn result(ok: Type, err: Type) -> Self {
        Type { name: "Result".into(), kind: TypeKind::Result, args: vec![ok, err], fields: HashMap::new() }
    }
    pub fn union(args: Vec<Type>) -> Self {
        Type { name: "Union".into(), kind: TypeKind::Union, args, fields: HashMap::new() }
    }
}

impl std::fmt::Display for Type {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self.kind {
            TypeKind::Primitive => write!(f, "{}", self.name),
            TypeKind::Generic => {
                if self.args.is_empty() { write!(f, "{}", self.name) }
                else { write!(f, "{}<{}>", self.name, self.args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(", ")) }
            }
            TypeKind::Option => {
                if self.args.is_empty() { write!(f, "Option<T>") }
                else { write!(f, "Option<{}>", self.args[0]) }
            }
            TypeKind::Result => {
                if self.args.len() == 2 { write!(f, "Result<{}, {}>", self.args[0], self.args[1]) }
                else { write!(f, "Result<T, E>") }
            }
            TypeKind::Stream => {
                if self.args.is_empty() { write!(f, "Stream<T>") }
                else { write!(f, "Stream<{}>", self.args[0]) }
            }
            TypeKind::Union => write!(f, "{}", self.args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(" | ")),
            _ => write!(f, "{}", self.name),
        }
    }
}

const PRIMITIVE_TYPES: &[&str] = &["Str", "Int", "Float", "Bool", "Any", "Bytes", "Token"];

// ---------------------------------------------------------------------------
// Type parsing
// ---------------------------------------------------------------------------

pub fn parse_type(type_str: &str) -> Type {
    let s = type_str.trim();
    if s == "()" { return Type::primitive("()"); }
    if s.contains('|') { return parse_union_type(s); }
    if s.starts_with("Option<") && s.ends_with('>') {
        let inner = &s[7..s.len()-1];
        return Type::option(parse_type(inner.trim()));
    }
    if s.starts_with("Result<") && s.ends_with('>') {
        let inner = &s[7..s.len()-1];
        let parts = split_type_args(inner);
        let args: Vec<Type> = parts.iter().map(|p| parse_type(p)).collect();
        if args.len() == 2 { return Type::result(args[0].clone(), args[1].clone()); }
        return Type { name: "Result".into(), kind: TypeKind::Result, args, fields: HashMap::new() };
    }
    if s.starts_with("Stream<") && s.ends_with('>') {
        let inner = &s[7..s.len()-1];
        return Type { name: "Stream".into(), kind: TypeKind::Stream, args: vec![parse_type(inner.trim())], fields: HashMap::new() };
    }
    if s.contains('<') && s.ends_with('>') {
        let lt_idx = s.find('<').unwrap();
        let base = s[..lt_idx].trim();
        let inner = &s[lt_idx+1..s.len()-1];
        let parts = split_type_args(inner);
        return Type::generic(base, parts.iter().map(|p| parse_type(p)).collect());
    }
    if PRIMITIVE_TYPES.contains(&s) { return Type::primitive(s); }
    Type::unknown(s)
}

fn parse_union_type(type_str: &str) -> Type {
    let parts = split_by_pipe(type_str);
    let args: Vec<Type> = parts.iter().map(|p| parse_type(p)).collect();
    Type::union(args)
}

fn split_type_args(s: &str) -> Vec<String> {
    let mut args = Vec::new();
    let mut current = String::new();
    let mut depth = 0;
    for ch in s.chars() {
        match ch {
            '<' => { depth += 1; current.push(ch); }
            '>' => { depth -= 1; current.push(ch); }
            ',' if depth == 0 => {
                let trimmed = current.trim().to_string();
                if !trimmed.is_empty() { args.push(trimmed); }
                current.clear();
            }
            _ => current.push(ch),
        }
    }
    let trimmed = current.trim().to_string();
    if !trimmed.is_empty() { args.push(trimmed); }
    args
}

fn split_by_pipe(s: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut depth = 0;
    for ch in s.chars() {
        match ch {
            '<' => { depth += 1; current.push(ch); }
            '>' => { depth -= 1; current.push(ch); }
            '|' if depth == 0 => {
                let trimmed = current.trim().to_string();
                if !trimmed.is_empty() { parts.push(trimmed); }
                current.clear();
            }
            _ => current.push(ch),
        }
    }
    let trimmed = current.trim().to_string();
    if !trimmed.is_empty() { parts.push(trimmed); }
    parts
}

// ---------------------------------------------------------------------------
// Type equality and subtyping
// ---------------------------------------------------------------------------

pub fn types_equal(t1: &Type, t2: &Type) -> bool {
    if t1.kind != t2.kind { return false; }
    if t1.name != t2.name { return false; }
    if t1.args.len() != t2.args.len() { return false; }
    t1.args.iter().zip(t2.args.iter()).all(|(a, b)| types_equal(a, b))
}

pub fn is_subtype(sub: &Type, sup: &Type) -> bool {
    // Any is a supertype of everything
    if sup.kind == TypeKind::Primitive && sup.name == "Any" { return true; }
    // Exact match
    if types_equal(sub, sup) { return true; }
    // Union supertype
    if sup.kind == TypeKind::Union {
        return sup.args.iter().any(|m| is_subtype(sub, m));
    }
    // Union subtype
    if sub.kind == TypeKind::Union {
        return sub.args.iter().all(|m| is_subtype(m, sup));
    }
    // Option<T> is a supertype of T
    if sup.kind == TypeKind::Option && sub.kind != TypeKind::Option {
        if !sup.args.is_empty() { return is_subtype(sub, &sup.args[0]); }
    }
    // Result covariance
    if sup.kind == TypeKind::Result && sub.kind == TypeKind::Result {
        if sub.args.len() == 2 && sup.args.len() == 2 {
            return is_subtype(&sub.args[0], &sup.args[0]) && is_subtype(&sub.args[1], &sup.args[1]);
        }
    }
    // Generic covariance
    if sup.kind == TypeKind::Generic && sub.kind == TypeKind::Generic {
        if sub.name == sup.name && sub.args.len() == sup.args.len() {
            return sub.args.iter().zip(sup.args.iter()).all(|(a, b)| is_subtype(a, b));
        }
    }
    // Int <: Float numeric widening
    if sub.kind == TypeKind::Primitive && sup.kind == TypeKind::Primitive {
        if sub.name == "Int" && sup.name == "Float" { return true; }
    }
    false
}

// ---------------------------------------------------------------------------
// TypeChecker
// ---------------------------------------------------------------------------

pub struct TypeChecker {
    type_aliases: HashMap<String, Type>,
    diagnostics: Vec<Diagnostic>,
    variable_types: HashMap<String, Type>,
    tool_signatures: HashMap<String, Type>,
    agent_methods: HashMap<String, Type>,
}

impl TypeChecker {
    pub fn new() -> Self {
        Self {
            type_aliases: HashMap::new(),
            diagnostics: Vec::new(),
            variable_types: HashMap::new(),
            tool_signatures: HashMap::new(),
            agent_methods: HashMap::new(),
        }
    }

    pub fn check(&mut self, ir: &AxonIR) -> Vec<Diagnostic> {
        self.diagnostics.clear();
        self.type_aliases.clear();
        self.tool_signatures.clear();
        self.agent_methods.clear();

        // First pass: collect type aliases and signatures
        for ta in &ir.type_aliases {
            self.collect_type_alias(ta);
        }
        for tool in &ir.tools {
            self.tool_signatures.insert(tool.name.clone(), parse_type(&tool.return_type));
        }
        for agent in &ir.agents {
            for method in &agent.methods {
                let key = format!("{}.{}", agent.name, method.name);
                self.agent_methods.insert(key, parse_type(&method.return_type));
            }
        }

        // Second pass: check each declaration
        for tool in &ir.tools { self.check_tool(tool); }
        for agent in &ir.agents { self.check_agent(agent); }
        for prompt in &ir.prompts { self.check_prompt(prompt); }
        for rag in &ir.rags { self.check_rag(rag); }
        for flow in &ir.flows { self.check_flow(flow); }

        self.diagnostics.clone()
    }

    fn collect_type_alias(&mut self, decl: &crate::TypeAliasDef) {
        let parsed = parse_type(&decl.value);
        if !decl.fields.is_empty() {
            let mut field_types = HashMap::new();
            for p in &decl.fields {
                field_types.insert(p.name.clone(), parse_type(&p.type_str));
            }
            self.type_aliases.insert(decl.name.clone(), Type {
                name: decl.name.clone(),
                kind: TypeKind::Record,
                args: vec![],
                fields: field_types,
            });
        } else {
            self.type_aliases.insert(decl.name.clone(), parsed);
        }
    }

    fn check_tool(&mut self, tool: &ToolDef) {
        for param in &tool.params {
            let pt = parse_type(&param.type_str);
            self.validate_type(&pt, &format!("tool '{}' parameter '{}'", tool.name, param.name), 0);
        }
        let rt = parse_type(&tool.return_type);
        self.validate_type(&rt, &format!("tool '{}' return type", tool.name), 0);
    }

    fn check_agent(&mut self, agent: &AgentDef) {
        for method in &agent.methods {
            self.check_method(method, &format!("agent '{}'", agent.name), 0);
        }
    }

    fn check_method(&mut self, method: &crate::MethodDef, context: &str, line: i32) {
        let method_ctx = format!("{} method '{}'", context, method.name);
        for param in &method.params {
            let pt = parse_type(&param.type_str);
            self.validate_type(&pt, &format!("{} parameter '{}'", method_ctx, param.name), line);
        }
        let rt = parse_type(&method.return_type);
        self.validate_type(&rt, &format!("{} return type", method_ctx), line);

        if let Some(body_ast) = &method.body_ast {
            self.variable_types.clear();
            for param in &method.params {
                self.variable_types.insert(param.name.clone(), parse_type(&param.type_str));
            }
            if let Some(inferred) = self.infer_expr_type(body_ast, &method_ctx) {
                if !is_subtype(&inferred, &rt) {
                    self.diagnostics.push(Diagnostic::error(
                        format!("{}: inferred return type '{}' does not match declared return type '{}'", method_ctx, inferred, rt),
                        line, "return-type-mismatch",
                    ).with_hint(format!("Expected '{}' but inferred '{}'", rt, inferred)));
                }
            }
        }
    }

    fn check_prompt(&mut self, prompt: &PromptDef) {
        for param in &prompt.params {
            let pt = parse_type(&param.type_str);
            self.validate_type(&pt, &format!("prompt '{}' parameter '{}'", prompt.name, param.name), 0);
        }
        let rt = parse_type(&prompt.return_type);
        self.validate_type(&rt, &format!("prompt '{}' return type", prompt.name), 0);
    }

    fn check_rag(&mut self, rag: &RagDef) {
        for method in &rag.methods {
            self.check_method(method, &format!("rag '{}'", rag.name), 0);
        }
    }

    fn check_flow(&mut self, flow: &FlowDef) {
        for param in &flow.params {
            let pt = parse_type(&param.type_str);
            self.validate_type(&pt, &format!("flow '{}' parameter '{}'", flow.name, param.name), 0);
        }
        let rt = parse_type(&flow.return_type);
        self.validate_type(&rt, &format!("flow '{}' return type", flow.name), 0);
        for stage in &flow.stages {
            let stage_ctx = format!("flow '{}' stage '{}'", flow.name, stage.name);
            for param in &stage.params {
                let pt = parse_type(&param.type_str);
                self.validate_type(&pt, &format!("{} parameter '{}'", stage_ctx, param.name), 0);
            }
            let srt = parse_type(&stage.return_type);
            self.validate_type(&srt, &format!("{} return type", stage_ctx), 0);
        }
    }

    fn validate_type(&mut self, t: &Type, context: &str, line: i32) {
        if t.kind == TypeKind::Unknown && !self.type_aliases.contains_key(&t.name) {
            self.diagnostics.push(Diagnostic::warning(
                format!("{} uses unknown type '{}'", context, t.name), line, "unknown-type",
            ));
        }
        for arg in &t.args {
            self.validate_type(arg, context, line);
        }
        for (_, ft) in &t.fields {
            self.validate_type(ft, context, line);
        }
    }

    // -----------------------------------------------------------------------
    // Expression type inference
    // -----------------------------------------------------------------------

    fn infer_expr_type(&mut self, expr: &Expr, context: &str) -> Option<Type> {
        match expr {
            Expr::Literal { value } => Some(self.infer_literal(value)),
            Expr::Variable { name } => {
                if let Some(t) = self.variable_types.get(name) { Some(t.clone()) }
                else { Some(Type::unknown(name)) }
            }
            Expr::BinaryOp { op, left, right } => {
                let lt = self.infer_expr_type(left, context)?;
                let rt = self.infer_expr_type(right, context)?;
                if ["+", "-", "*", "/"].contains(&op.as_str()) {
                    if lt.kind == TypeKind::Primitive && lt.name == "Int" && rt.kind == TypeKind::Primitive && rt.name == "Int" {
                        return Some(Type::primitive("Int"));
                    }
                    if lt.kind == TypeKind::Primitive && lt.name == "Float" && rt.kind == TypeKind::Primitive && rt.name == "Float" {
                        return Some(Type::primitive("Float"));
                    }
                    if lt.kind == TypeKind::Primitive && lt.name == "Str" && rt.kind == TypeKind::Primitive && rt.name == "Str" {
                        return Some(Type::primitive("Str"));
                    }
                    return Some(Type::primitive("Any"));
                }
                if ["==", "!=", "<", ">", "<=", ">=", "&&", "||"].contains(&op.as_str()) {
                    return Some(Type::primitive("Bool"));
                }
                Some(Type::primitive("Any"))
            }
            Expr::UnaryOp { op, operand } => {
                let ot = self.infer_expr_type(operand, context)?;
                if op == "-" {
                    if ot.kind == TypeKind::Primitive && (ot.name == "Int" || ot.name == "Float") {
                        return Some(ot);
                    }
                }
                if op == "!" || op == "not" { return Some(Type::primitive("Bool")); }
                Some(ot)
            }
            Expr::Call { callee, .. } => {
                if let Expr::Variable { name } = callee.as_ref() {
                    if let Some(t) = self.tool_signatures.get(name) { return Some(t.clone()); }
                    if let Some(t) = self.agent_methods.get(name) { return Some(t.clone()); }
                }
                Some(Type::unknown("CallResult"))
            }
            Expr::MemberAccess { object, member } => {
                let ot = self.infer_expr_type(object, context)?;
                if ot.kind == TypeKind::Record {
                    if let Some(ft) = ot.fields.get(member) { return Some(ft.clone()); }
                }
                if ot.kind == TypeKind::Unknown {
                    if let Some(alias) = self.type_aliases.get(&ot.name) {
                        if alias.kind == TypeKind::Record {
                            if let Some(ft) = alias.fields.get(member) { return Some(ft.clone()); }
                        }
                    }
                }
                Some(Type::unknown(member))
            }
            Expr::Index { object, .. } => {
                let ot = self.infer_expr_type(object, context)?;
                if ot.kind == TypeKind::Generic && ot.name == "List" && !ot.args.is_empty() {
                    return Some(ot.args[0].clone());
                }
                if ot.kind == TypeKind::Generic && ot.name == "Map" && ot.args.len() >= 2 {
                    return Some(ot.args[1].clone());
                }
                Some(Type::unknown("IndexResult"))
            }
            Expr::List { elements } => {
                if elements.is_empty() { return Some(Type::generic("List", vec![Type::primitive("Any")])); }
                let ft = self.infer_expr_type(&elements[0], context)?;
                Some(Type::generic("List", vec![ft]))
            }
            Expr::Map { pairs } => {
                if pairs.is_empty() {
                    return Some(Type::generic("Map", vec![Type::primitive("Str"), Type::primitive("Any")]));
                }
                let kt = self.infer_expr_type(&pairs[0].0, context)?;
                let vt = self.infer_expr_type(&pairs[0].1, context)?;
                Some(Type::generic("Map", vec![kt, vt]))
            }
            Expr::Ok { value } => {
                let vt = self.infer_expr_type(value, context)?;
                Some(Type::result(vt, Type::primitive("Any")))
            }
            Expr::Error { value } => {
                let vt = self.infer_expr_type(value, context)?;
                Some(Type::result(Type::primitive("Any"), vt))
            }
            Expr::Some { value } => {
                let vt = self.infer_expr_type(value, context)?;
                Some(Type::option(vt))
            }
            Expr::None => Some(Type::option(Type::primitive("Any"))),
            Expr::If { then_branch, else_branch, .. } => {
                let tt = self.infer_expr_type(then_branch, context)?;
                if let Some(eb) = else_branch {
                    let et = self.infer_expr_type(eb, context)?;
                    if types_equal(&tt, &et) { return Some(tt); }
                    return Some(Type::primitive("Any"));
                }
                Some(tt)
            }
            Expr::Let { name, value, body } => {
                let vt = self.infer_expr_type(value, context)?;
                self.variable_types.insert(name.clone(), vt);
                self.infer_expr_type(body, context)
            }
            Expr::Block { statements } => {
                if statements.is_empty() { return Some(Type::primitive("()")); }
                self.infer_expr_type(&statements[statements.len()-1], context)
            }
            Expr::Return { value } => self.infer_expr_type(value, context),
            Expr::StringInterpolation { .. } => Some(Type::primitive("Str")),
            Expr::Act { tool_name, .. } => {
                if let Some(t) = self.tool_signatures.get(tool_name) { Some(t.clone()) }
                else { Some(Type::unknown("CallResult")) }
            }
            Expr::Delegate { agent_name, .. } => {
                for (key, rt) in &self.agent_methods {
                    if key.ends_with(&format!(".{}", agent_name)) || key == agent_name {
                        return Some(rt.clone());
                    }
                }
                Some(Type::unknown("DelegateResult"))
            }
            Expr::ModelCall { .. } => Some(Type::primitive("Str")),
            Expr::Try { operand } => {
                let ot = self.infer_expr_type(operand, context)?;
                if ot.kind == TypeKind::Result && !ot.args.is_empty() { return Some(ot.args[0].clone()); }
                if ot.kind == TypeKind::Option && !ot.args.is_empty() { return Some(ot.args[0].clone()); }
                Some(ot)
            }
            Expr::For { var_name, iterable, body } => {
                let it = self.infer_expr_type(iterable, context)?;
                let mut elem = Type::primitive("Any");
                if it.kind == TypeKind::Generic && it.name == "List" && !it.args.is_empty() {
                    elem = it.args[0].clone();
                } else if it.kind == TypeKind::Generic && it.name == "Map" && it.args.len() >= 2 {
                    elem = it.args[0].clone();
                }
                self.variable_types.insert(var_name.clone(), elem);
                self.infer_expr_type(body, context)
            }
            Expr::Assign { name, value } => {
                let vt = self.infer_expr_type(value, context)?;
                self.variable_types.insert(name.clone(), vt.clone());
                Some(vt)
            }
            Expr::Match { arms, .. } => {
                let mut arm_types = Vec::new();
                for arm in arms {
                    if let Some(t) = self.infer_expr_type(&arm.expr, context) {
                        arm_types.push(t);
                    }
                }
                if arm_types.is_empty() { return Some(Type::primitive("Any")); }
                if arm_types.len() == 1 { return Some(arm_types[0].clone()); }
                let first = &arm_types[0];
                if arm_types[1..].iter().all(|t| types_equal(first, t)) { return Some(first.clone()); }
                Some(Type::union(arm_types))
            }
            Expr::Store { .. } | Expr::Think { .. } | Expr::Observe { .. } => Some(Type::primitive("()")),
            _ => Some(Type::unknown("Unknown")),
        }
    }

    fn infer_literal(&self, value: &crate::expression::LiteralValue) -> Type {
        match value {
            crate::expression::LiteralValue::Null => Type::option(Type::primitive("Any")),
            crate::expression::LiteralValue::Bool(_) => Type::primitive("Bool"),
            crate::expression::LiteralValue::Int(_) => Type::primitive("Int"),
            crate::expression::LiteralValue::Float(_) => Type::primitive("Float"),
            crate::expression::LiteralValue::String(_) => Type::primitive("Str"),
        }
    }
}

pub fn check_types(ir: &AxonIR) -> Vec<Diagnostic> {
    let mut checker = TypeChecker::new();
    checker.check(ir)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_primitive() {
        assert_eq!(parse_type("Str"), Type::primitive("Str"));
        assert_eq!(parse_type("Int"), Type::primitive("Int"));
    }

    #[test]
    fn test_parse_generic() {
        let t = parse_type("List<Int>");
        assert_eq!(t.kind, TypeKind::Generic);
        assert_eq!(t.name, "List");
        assert_eq!(t.args.len(), 1);
        assert_eq!(t.args[0], Type::primitive("Int"));
    }

    #[test]
    fn test_parse_option() {
        let t = parse_type("Option<Str>");
        assert_eq!(t.kind, TypeKind::Option);
        assert_eq!(t.args[0], Type::primitive("Str"));
    }

    #[test]
    fn test_parse_result() {
        let t = parse_type("Result<Int, Str>");
        assert_eq!(t.kind, TypeKind::Result);
        assert_eq!(t.args.len(), 2);
    }

    #[test]
    fn test_parse_union() {
        let t = parse_type("\"low\" | \"medium\" | \"high\"");
        assert_eq!(t.kind, TypeKind::Union);
        assert_eq!(t.args.len(), 3);
    }

    #[test]
    fn test_types_equal() {
        assert!(types_equal(&parse_type("Int"), &parse_type("Int")));
        assert!(!types_equal(&parse_type("Int"), &parse_type("Str")));
    }

    #[test]
    fn test_is_subtype_any() {
        assert!(is_subtype(&parse_type("Int"), &parse_type("Any")));
    }

    #[test]
    fn test_is_subtype_int_float() {
        assert!(is_subtype(&parse_type("Int"), &parse_type("Float")));
        assert!(!is_subtype(&parse_type("Float"), &parse_type("Int")));
    }

    #[test]
    fn test_is_subtype_option() {
        assert!(is_subtype(&parse_type("Int"), &parse_type("Option<Int>")));
    }

    #[test]
    fn test_check_valid_program() {
        let src = r#"
tool Add(a: Int, b: Int) -> Int {
    /// Adds two numbers
    a + b
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = check_types(&ir);
        let errors: Vec<_> = diags.iter().filter(|d| d.is_error()).collect();
        assert!(errors.is_empty(), "Expected no errors, got: {:?}", errors);
    }

    #[test]
    fn test_check_unknown_type() {
        let src = r#"
tool Foo(a: Int) -> BogusType {
    /// doc
    a
}
"#;
        let ir = crate::parse_source(src).unwrap();
        let diags = check_types(&ir);
        assert!(diags.iter().any(|d| d.code == "unknown-type"), "Expected unknown-type warning, got: {:?}", diags);
    }
}
