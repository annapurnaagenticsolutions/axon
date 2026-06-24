//! AXON Expression Parser — structured AST for method/tool bodies.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Expr {
    Literal { value: LiteralValue },
    Variable { name: String },
    BinaryOp { op: String, left: Box<Expr>, right: Box<Expr> },
    UnaryOp { op: String, operand: Box<Expr> },
    Call { callee: Box<Expr>, args: Vec<Expr> },
    MemberAccess { object: Box<Expr>, member: String },
    Index { object: Box<Expr>, index: Box<Expr> },
    List { elements: Vec<Expr> },
    Map { pairs: Vec<(Expr, Expr)> },
    If { condition: Box<Expr>, then_branch: Box<Expr>, else_branch: Option<Box<Expr>> },
    While { condition: Box<Expr>, body: Box<Expr> },
    Break,
    Continue,
    For { var_name: String, iterable: Box<Expr>, body: Box<Expr> },
    Let { name: String, value: Box<Expr>, body: Box<Expr> },
    Assign { name: String, value: Box<Expr> },
    Match { value: Box<Expr>, arms: Vec<MatchArm> },
    Block { statements: Vec<Expr> },
    Return { value: Box<Expr> },
    Try { operand: Box<Expr> },
    Ok { value: Box<Expr> },
    Error { value: Box<Expr> },
    Some { value: Box<Expr> },
    None,
    Act { tool_name: String, args: Vec<(String, Expr)> },
    Delegate { agent_name: String, args: Vec<(String, Expr)> },
    Think { message: Box<Expr> },
    Observe { name: String, value: Box<Expr> },
    Store { target: Box<Expr>, value: Box<Expr> },
    ModelCall { prompt: Box<Expr> },
    StringInterpolation { parts: Vec<Expr> },
    Go { call: Box<Expr> },
    Await { future: Box<Expr> },
    Chan { capacity: Option<Box<Expr>> },
    Select { arms: Vec<SelectArm> },
    Pool { size: Box<Expr>, target: Box<Expr> },
    Send { recipient: Box<Expr>, message: Box<Expr> },
    Receive { timeout_ms: Option<Box<Expr>> },
    Broadcast { channel: Box<Expr>, message: Box<Expr> },
    Discover { pattern: Box<Expr> },
    Spawn { source: Box<Expr>, name: Box<Expr>, args: Vec<(String, Expr)> },
    Pause { agent_name: Box<Expr> },
    Resume { agent_name: Box<Expr> },
    Terminate { agent_name: Box<Expr>, reason: Option<Box<Expr>> },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SelectArm {
    pub channel: Expr,
    pub var_name: String,
    pub body: Expr,
    pub is_default: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LiteralValue {
    String(String),
    Int(i64),
    Float(f64),
    Bool(bool),
    Null,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MatchArm {
    pub pattern: String,
    pub expr: Expr,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub guard: Option<Box<Expr>>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ExprParseError {
    pub msg: String,
    pub pos: usize,
    pub line: usize,
    pub column: usize,
}

impl std::fmt::Display for ExprParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "ExprParseError at {}:{}: {}", self.line, self.column, self.msg)
    }
}

impl std::error::Error for ExprParseError {}

fn pos_to_line_col(source: &str, pos: usize) -> (usize, usize) {
    let mut line = 1;
    let mut col = 1;
    for (i, c) in source.char_indices() {
        if i >= pos { break; }
        if c == '\n' { line += 1; col = 1; }
        else { col += 1; }
    }
    (line, col)
}

pub struct ExprParser<'a> {
    source: &'a str,
    pos: usize,
}

impl<'a> ExprParser<'a> {
    pub fn new(source: &'a str) -> Self {
        Self { source, pos: 0 }
    }

    pub fn parse(&mut self) -> Result<Expr, ExprParseError> {
        self.skip_ws();
        if self.pos >= self.source.len() {
            return Ok(Expr::Literal { value: LiteralValue::Null });
        }
        let expr = self.parse_expr()?;
        self.skip_ws();
        if self.pos < self.source.len() {
            return Err(self.err(format!("Unexpected trailing: {}", &self.source[self.pos..self.source.len().min(self.pos + 20)])));
        }
        Ok(expr)
    }

    fn parse_expr(&mut self) -> Result<Expr, ExprParseError> { self.parse_assign() }

    fn parse_assign(&mut self) -> Result<Expr, ExprParseError> {
        let left = self.parse_or()?;
        self.skip_ws();
        if self.peek() == Some('=') && self.peek_at(1) != Some('=') && self.peek_at(1) != Some('>') {
            self.advance();
            let val = self.parse_assign()?;
            if let Expr::Variable { name } = left {
                return Ok(Expr::Assign { name, value: Box::new(val) });
            }
            return Err(self.err("Left side of = must be a variable".into()));
        }
        Ok(left)
    }

    fn parse_or(&mut self) -> Result<Expr, ExprParseError> {
        let mut left = self.parse_and()?;
        self.skip_ws();
        while self.starts_with("||") {
            self.advance_by(2);
            let right = self.parse_and()?;
            left = Expr::BinaryOp { op: "||".into(), left: Box::new(left), right: Box::new(right) };
            self.skip_ws();
        }
        Ok(left)
    }

    fn parse_and(&mut self) -> Result<Expr, ExprParseError> {
        let mut left = self.parse_eq()?;
        self.skip_ws();
        while self.starts_with("&&") {
            self.advance_by(2);
            let right = self.parse_eq()?;
            left = Expr::BinaryOp { op: "&&".into(), left: Box::new(left), right: Box::new(right) };
            self.skip_ws();
        }
        Ok(left)
    }

    fn parse_eq(&mut self) -> Result<Expr, ExprParseError> {
        let mut left = self.parse_cmp()?;
        self.skip_ws();
        loop {
            if self.starts_with("==") { self.advance_by(2); let r = self.parse_cmp()?; left = Expr::BinaryOp { op: "==".into(), left: Box::new(left), right: Box::new(r) }; }
            else if self.starts_with("!=") { self.advance_by(2); let r = self.parse_cmp()?; left = Expr::BinaryOp { op: "!=".into(), left: Box::new(left), right: Box::new(r) }; }
            else { break; }
            self.skip_ws();
        }
        Ok(left)
    }

    fn parse_cmp(&mut self) -> Result<Expr, ExprParseError> {
        let mut left = self.parse_add()?;
        self.skip_ws();
        loop {
            if self.starts_with("<=") { self.advance_by(2); let r = self.parse_add()?; left = Expr::BinaryOp { op: "<=".into(), left: Box::new(left), right: Box::new(r) }; }
            else if self.starts_with(">=") { self.advance_by(2); let r = self.parse_add()?; left = Expr::BinaryOp { op: ">=".into(), left: Box::new(left), right: Box::new(r) }; }
            else if self.peek() == Some('<') { self.advance(); let r = self.parse_add()?; left = Expr::BinaryOp { op: "<".into(), left: Box::new(left), right: Box::new(r) }; }
            else if self.peek() == Some('>') { self.advance(); let r = self.parse_add()?; left = Expr::BinaryOp { op: ">".into(), left: Box::new(left), right: Box::new(r) }; }
            else { break; }
            self.skip_ws();
        }
        Ok(left)
    }

    fn parse_add(&mut self) -> Result<Expr, ExprParseError> {
        let mut left = self.parse_mul()?;
        self.skip_ws();
        loop {
            if self.peek() == Some('+') { self.advance(); let r = self.parse_mul()?; left = Expr::BinaryOp { op: "+".into(), left: Box::new(left), right: Box::new(r) }; }
            else if self.peek() == Some('-') { self.advance(); let r = self.parse_mul()?; left = Expr::BinaryOp { op: "-".into(), left: Box::new(left), right: Box::new(r) }; }
            else { break; }
            self.skip_ws();
        }
        Ok(left)
    }

    fn parse_mul(&mut self) -> Result<Expr, ExprParseError> {
        let mut left = self.parse_unary()?;
        self.skip_ws();
        loop {
            if self.peek() == Some('*') { self.advance(); let r = self.parse_unary()?; left = Expr::BinaryOp { op: "*".into(), left: Box::new(left), right: Box::new(r) }; }
            else if self.peek() == Some('/') { self.advance(); let r = self.parse_unary()?; left = Expr::BinaryOp { op: "/".into(), left: Box::new(left), right: Box::new(r) }; }
            else { break; }
            self.skip_ws();
        }
        Ok(left)
    }

    fn parse_unary(&mut self) -> Result<Expr, ExprParseError> {
        self.skip_ws();
        if self.peek() == Some('!') { self.advance(); let op = self.parse_unary()?; return Ok(Expr::UnaryOp { op: "!".into(), operand: Box::new(op) }); }
        if self.peek() == Some('-') { self.advance(); let op = self.parse_unary()?; return Ok(Expr::UnaryOp { op: "-".into(), operand: Box::new(op) }); }
        self.parse_postfix()
    }

    fn parse_postfix(&mut self) -> Result<Expr, ExprParseError> {
        let mut expr = self.parse_primary()?;
        self.skip_ws();
        loop {
            if self.peek() == Some('(') {
                self.advance();
                let mut args = Vec::new();
                self.skip_ws();
                if self.peek() == Some(')') { self.advance(); }
                else { loop { args.push(self.parse_expr()?); self.skip_ws(); if self.peek() == Some(',') { self.advance(); self.skip_ws(); continue; } if self.peek() == Some(')') { self.advance(); break; } return Err(self.err("Expected , or )".into())); } }
                expr = Expr::Call { callee: Box::new(expr), args };
            } else if self.peek() == Some('.') && self.peek_at(1).is_some_and(|c| c.is_alphabetic() || c == '_') {
                self.advance();
                let member = self.parse_ident()?;
                expr = Expr::MemberAccess { object: Box::new(expr), member };
            } else if self.peek() == Some('[') {
                self.advance();
                let idx = self.parse_expr()?;
                self.skip_ws();
                self.expect(']')?;
                expr = Expr::Index { object: Box::new(expr), index: Box::new(idx) };
            } else if self.peek() == Some('?') {
                self.advance();
                expr = Expr::Try { operand: Box::new(expr) };
            } else { break; }
            self.skip_ws();
        }
        Ok(expr)
    }

    fn parse_primary(&mut self) -> Result<Expr, ExprParseError> {
        self.skip_ws();
        match self.peek() {
            Some('{') => return self.parse_block(),
            Some('"') | Some('\'') => return self.parse_str_lit(),
            Some('[') => return self.parse_list_lit(),
            _ => {}
        }
        if self.peek().is_some_and(|c| c.is_ascii_digit()) { return self.parse_num_lit(); }

        // Keywords
        if self.starts_with_kw("return") { self.advance_by(6); self.skip_ws(); let v = if self.is_expr_start() { self.parse_expr()? } else { Expr::Literal { value: LiteralValue::Null } }; return Ok(Expr::Return { value: Box::new(v) }); }
        if self.starts_with_kw("let") { self.advance_by(3); self.skip_ws(); let name = self.parse_ident()?; self.skip_ws(); self.expect('=')?; self.skip_ws(); let val = self.parse_expr()?; self.skip_ws(); self.expect_kw("in")?; self.skip_ws(); let body = self.parse_expr()?; return Ok(Expr::Let { name, value: Box::new(val), body: Box::new(body) }); }
        if self.starts_with_kw("if") { self.advance_by(2); self.skip_ws(); let cond = self.parse_expr()?; self.skip_ws(); let then_ = Box::new(self.parse_block()?); self.skip_ws(); let else_ = if self.starts_with_kw("else") { self.advance_by(4); self.skip_ws(); Some(Box::new(self.parse_block()?)) } else { None }; return Ok(Expr::If { condition: Box::new(cond), then_branch: then_, else_branch: else_ }); }
        if self.starts_with_kw("while") { self.advance_by(5); self.skip_ws(); let cond = Box::new(self.parse_expr()?); self.skip_ws(); let body = Box::new(self.parse_block()?); return Ok(Expr::While { condition: cond, body }); }
        if self.starts_with_kw("break") { self.advance_by(5); return Ok(Expr::Break); }
        if self.starts_with_kw("continue") { self.advance_by(8); return Ok(Expr::Continue); }
        if self.starts_with_kw("for") { self.advance_by(3); self.skip_ws(); let var = self.parse_ident()?; self.skip_ws(); self.expect_kw("in")?; self.skip_ws(); let iter = Box::new(self.parse_expr()?); self.skip_ws(); let body = Box::new(self.parse_block()?); return Ok(Expr::For { var_name: var, iterable: iter, body }); }
        if self.starts_with_kw("match") { self.advance_by(5); self.skip_ws(); let val = Box::new(self.parse_expr()?); self.skip_ws(); let arms = self.parse_match_arms()?; return Ok(Expr::Match { value: val, arms }); }
        if self.starts_with_kw("act") { self.advance_by(3); self.skip_ws(); let tool = self.parse_ident()?; self.skip_ws(); let args = self.parse_named_args('(', ')')?; return Ok(Expr::Act { tool_name: tool, args }); }
        if self.starts_with_kw("delegate") { self.advance_by(8); self.skip_ws(); let agent = self.parse_ident()?; self.skip_ws(); let args = self.parse_named_args('(', ')')?; return Ok(Expr::Delegate { agent_name: agent, args }); }
        if self.starts_with_kw("think") { self.advance_by(5); self.skip_ws(); let msg = Box::new(self.parse_expr()?); return Ok(Expr::Think { message: msg }); }
        if self.starts_with_kw("observe") { self.advance_by(7); self.skip_ws(); let name = self.parse_ident()?; self.skip_ws(); self.expect(':')?; self.skip_ws(); let val = Box::new(self.parse_expr()?); return Ok(Expr::Observe { name, value: val }); }
        if self.starts_with_kw("store") { self.advance_by(5); self.skip_ws(); let target_name = self.parse_ident()?; self.skip_ws(); self.expect('=')?; self.skip_ws(); let val = Box::new(self.parse_expr()?); return Ok(Expr::Store { target: Box::new(Expr::Variable { name: target_name }), value: val }); }
        if self.starts_with_kw("model") { self.advance_by(5); self.skip_ws(); self.expect('.')?; let _method = self.parse_ident()?; self.skip_ws(); self.expect('(')?; self.skip_ws(); let prompt = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(')')?; return Ok(Expr::ModelCall { prompt }); }
        if self.starts_with_kw("Ok") { self.advance_by(2); self.skip_ws(); self.expect('(')?; let v = self.parse_expr()?; self.skip_ws(); self.expect(')')?; return Ok(Expr::Ok { value: Box::new(v) }); }
        if self.starts_with_kw("Err") { self.advance_by(3); self.skip_ws(); self.expect('(')?; let v = self.parse_expr()?; self.skip_ws(); self.expect(')')?; return Ok(Expr::Error { value: Box::new(v) }); }
        if self.starts_with_kw("Some") { self.advance_by(4); self.skip_ws(); self.expect('(')?; let v = self.parse_expr()?; self.skip_ws(); self.expect(')')?; return Ok(Expr::Some { value: Box::new(v) }); }
        if self.starts_with_kw("None") { self.advance_by(4); return Ok(Expr::None); }
        if self.starts_with_kw("go") { self.advance_by(2); self.skip_ws(); let call = Box::new(self.parse_expr()?); return Ok(Expr::Go { call }); }
        if self.starts_with_kw("await") { self.advance_by(5); self.skip_ws(); let future = Box::new(self.parse_expr()?); return Ok(Expr::Await { future }); }
        if self.starts_with_kw("chan") { self.advance_by(4); self.skip_ws(); self.expect('(')?; self.skip_ws(); let capacity = if self.peek() == Some(')') { None } else { let cap = self.parse_expr()?; self.skip_ws(); Some(Box::new(cap)) }; self.expect(')')?; return Ok(Expr::Chan { capacity }); }
        if self.starts_with_kw("select") { self.advance_by(6); self.skip_ws(); let arms = self.parse_select_arms()?; return Ok(Expr::Select { arms }); }
        if self.starts_with_kw("pool") { self.advance_by(4); self.skip_ws(); self.expect('(')?; self.skip_ws(); let size = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(',')?; self.skip_ws(); let target = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(')')?; return Ok(Expr::Pool { size, target }); }
        if self.starts_with_kw("send") { self.advance_by(4); self.skip_ws(); let recipient = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(',')?; self.skip_ws(); let message = Box::new(self.parse_expr()?); return Ok(Expr::Send { recipient, message }); }
        if self.starts_with_kw("receive") { self.advance_by(7); self.skip_ws(); let timeout_ms = if self.peek() == Some('(') { self.advance(); self.skip_ws(); let t = if self.peek() == Some(')') { None } else { let t = self.parse_expr()?; self.skip_ws(); Some(Box::new(t)) }; self.expect(')')?; t } else { None }; return Ok(Expr::Receive { timeout_ms }); }
        if self.starts_with_kw("broadcast") { self.advance_by(9); self.skip_ws(); let channel = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(',')?; self.skip_ws(); let message = Box::new(self.parse_expr()?); return Ok(Expr::Broadcast { channel, message }); }
        if self.starts_with_kw("discover") { self.advance_by(8); self.skip_ws(); self.expect('(')?; self.skip_ws(); let pattern = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(')')?; return Ok(Expr::Discover { pattern }); }
        if self.starts_with_kw("spawn") { self.advance_by(5); self.skip_ws(); let source = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(',')?; self.skip_ws(); let name = Box::new(self.parse_expr()?); self.skip_ws(); let args = if self.peek() == Some('(') { self.parse_named_args('(', ')')? } else { Vec::new() }; return Ok(Expr::Spawn { source, name, args }); }
        if self.starts_with_kw("pause") { self.advance_by(5); self.skip_ws(); self.expect('(')?; self.skip_ws(); let agent_name = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(')')?; return Ok(Expr::Pause { agent_name }); }
        if self.starts_with_kw("resume") { self.advance_by(6); self.skip_ws(); self.expect('(')?; self.skip_ws(); let agent_name = Box::new(self.parse_expr()?); self.skip_ws(); self.expect(')')?; return Ok(Expr::Resume { agent_name }); }
        if self.starts_with_kw("terminate") { self.advance_by(9); self.skip_ws(); self.expect('(')?; self.skip_ws(); let agent_name = Box::new(self.parse_expr()?); self.skip_ws(); let reason = if self.peek() == Some(',') { self.advance(); self.skip_ws(); let r = self.parse_expr()?; self.skip_ws(); Some(Box::new(r)) } else { None }; self.expect(')')?; return Ok(Expr::Terminate { agent_name, reason }); }

        let name = self.parse_ident()?;
        Ok(Expr::Variable { name })
    }

    fn parse_block(&mut self) -> Result<Expr, ExprParseError> {
        self.expect('{')?;
        let mut stmts = Vec::new();
        let mut depth = 0;
        loop {
            self.skip_ws();
            if self.pos >= self.source.len() { return Err(self.err("Unclosed block".into())); }
            if self.peek() == Some('{') { depth += 1; self.advance(); continue; }
            if self.peek() == Some('}') { if depth == 0 { self.advance(); break; } depth -= 1; self.advance(); continue; }
            stmts.push(self.parse_expr()?);
            self.skip_ws();
            if self.peek() == Some(';') { self.advance(); self.skip_ws(); }
        }
        Ok(Expr::Block { statements: stmts })
    }

    fn parse_str_lit(&mut self) -> Result<Expr, ExprParseError> {
        let q = self.peek().unwrap();
        self.advance();
        let mut val = String::new();
        let mut parts: Vec<Expr> = Vec::new();
        let mut interp = false;
        while let Some(c) = self.peek() {
            if c == q { self.advance(); break; }
            if c == '\\' { self.advance(); if let Some(e) = self.peek() { match e { 'n' => val.push('\n'), 't' => val.push('\t'), 'r' => val.push('\r'), '\\' => val.push('\\'), '"' => val.push('"'), _ => val.push(e) } self.advance(); } continue; }
            if c == '{' && q == '"' {
                if !val.is_empty() { parts.push(Expr::Literal { value: LiteralValue::String(val.clone()) }); val.clear(); }
                self.advance(); interp = true; let e = self.parse_expr()?; self.skip_ws(); self.expect('}')?; parts.push(e); continue;
            }
            val.push(c); self.advance();
        }
        if !val.is_empty() { parts.push(Expr::Literal { value: LiteralValue::String(val) }); }
        if interp && parts.len() > 1 { Ok(Expr::StringInterpolation { parts }) }
        else if parts.len() == 1 { Ok(parts.into_iter().next().unwrap()) }
        else { Ok(Expr::Literal { value: LiteralValue::String(String::new()) }) }
    }

    fn parse_num_lit(&mut self) -> Result<Expr, ExprParseError> {
        let start = self.pos;
        while self.peek().is_some_and(|c| c.is_ascii_digit()) { self.advance(); }
        if self.peek() == Some('.') && self.peek_at(1).is_some_and(|c| c.is_ascii_digit()) {
            self.advance();
            while self.peek().is_some_and(|c| c.is_ascii_digit()) { self.advance(); }
            let s = &self.source[start..self.pos];
            let v: f64 = s.parse().map_err(|_| self.err(format!("bad float: {}", s)))?;
            return Ok(Expr::Literal { value: LiteralValue::Float(v) });
        }
        let s = &self.source[start..self.pos];
        let v: i64 = s.parse().map_err(|_| self.err(format!("bad int: {}", s)))?;
        Ok(Expr::Literal { value: LiteralValue::Int(v) })
    }

    fn parse_list_lit(&mut self) -> Result<Expr, ExprParseError> {
        self.advance(); // [
        let mut els = Vec::new();
        self.skip_ws();
        if self.peek() == Some(']') { self.advance(); return Ok(Expr::List { elements: els }); }
        loop {
            els.push(self.parse_expr()?); self.skip_ws();
            if self.peek() == Some(',') { self.advance(); self.skip_ws(); continue; }
            if self.peek() == Some(']') { self.advance(); break; }
            return Err(self.err("Expected , or ]".into()));
        }
        Ok(Expr::List { elements: els })
    }

    fn parse_named_args(&mut self, open: char, close: char) -> Result<Vec<(String, Expr)>, ExprParseError> {
        self.expect(open)?;
        let mut args = Vec::new();
        self.skip_ws();
        if self.peek() == Some(close) { self.advance(); return Ok(args); }
        loop {
            let name = self.parse_ident()?; self.skip_ws(); self.expect(':')?; self.skip_ws();
            let val = self.parse_expr()?;
            args.push((name, val)); self.skip_ws();
            if self.peek() == Some(',') { self.advance(); self.skip_ws(); continue; }
            if self.peek() == Some(close) { self.advance(); break; }
            return Err(self.err(format!("Expected , or {}", close)));
        }
        Ok(args)
    }

    fn parse_match_arms(&mut self) -> Result<Vec<MatchArm>, ExprParseError> {
        self.expect('{')?;
        let mut arms = Vec::new(); self.skip_ws();
        while self.peek() != Some('}') && self.pos < self.source.len() {
            let pattern = self.parse_ident()?; self.skip_ws();
            let guard = if self.starts_with_kw("if") {
                self.advance_by(2); self.skip_ws();
                Some(Box::new(self.parse_expr()?))
            } else { None };
            self.skip_ws();
            if !self.starts_with("=>") { return Err(self.err("Expected =>".into())); }
            self.advance_by(2); self.skip_ws();
            let expr = self.parse_expr()?;
            arms.push(MatchArm { pattern, expr, guard }); self.skip_ws();
            if self.peek() == Some(',') { self.advance(); self.skip_ws(); }
        }
        self.expect('}')?;
        Ok(arms)
    }

    fn parse_select_arms(&mut self) -> Result<Vec<SelectArm>, ExprParseError> {
        self.expect('{')?;
        let mut arms = Vec::new(); self.skip_ws();
        while self.peek() != Some('}') && self.pos < self.source.len() {
            if self.starts_with_kw("default") {
                self.advance_by(7); self.skip_ws();
                if !self.starts_with("=>") { return Err(self.err("Expected =>".into())); }
                self.advance_by(2); self.skip_ws();
                let body = self.parse_expr()?;
                arms.push(SelectArm { channel: Expr::Literal { value: LiteralValue::Null }, var_name: "".into(), body, is_default: true }); self.skip_ws();
                if self.peek() == Some(',') { self.advance(); self.skip_ws(); }
                continue;
            }
            let channel = self.parse_expr()?; self.skip_ws();
            if !self.starts_with_kw("as") { return Err(self.err("Expected 'as' in select arm".into())); }
            self.advance_by(2); self.skip_ws();
            let var_name = self.parse_ident()?; self.skip_ws();
            if !self.starts_with("=>") { return Err(self.err("Expected =>".into())); }
            self.advance_by(2); self.skip_ws();
            let body = self.parse_expr()?;
            arms.push(SelectArm { channel, var_name, body, is_default: false }); self.skip_ws();
            if self.peek() == Some(',') { self.advance(); self.skip_ws(); }
        }
        self.expect('}')?;
        Ok(arms)
    }

    fn parse_ident(&mut self) -> Result<String, ExprParseError> {
        let start = self.pos;
        let c = self.peek().ok_or_else(|| self.err("Expected identifier".into()))?;
        if !c.is_alphabetic() && c != '_' { return Err(self.err("Expected identifier".into())); }
        self.advance();
        while let Some(c) = self.peek() { if c.is_alphanumeric() || c == '_' || c == '-' { self.advance(); } else { break; } }
        Ok(self.source[start..self.pos].to_string())
    }

    fn starts_with_kw(&self, kw: &str) -> bool {
        if !self.source[self.pos..].starts_with(kw) { return false; }
        let end = self.pos + kw.len();
        end >= self.source.len() || !self.source[end..].chars().next().unwrap().is_alphanumeric()
    }

    fn is_expr_start(&self) -> bool {
        if self.pos >= self.source.len() { return false; }
        let c = self.source[self.pos..].chars().next().unwrap();
        c.is_alphanumeric() || c == '_' || c == '-' || c == '"' || c == '\'' || c == '[' || c == '{' || c == '(' || c == '!'
    }

    fn skip_ws(&mut self) {
        while self.pos < self.source.len() {
            let c = self.source[self.pos..].chars().next().unwrap();
            if c.is_whitespace() { self.advance(); } else { break; }
        }
    }

    fn peek(&self) -> Option<char> { self.source[self.pos..].chars().next() }
    fn peek_at(&self, offset: usize) -> Option<char> { let mut cs = self.source[self.pos..].chars(); for _ in 0..offset { cs.next()?; } cs.next() }
    fn advance(&mut self) { if let Some(c) = self.source[self.pos..].chars().next() { self.pos += c.len_utf8(); } }
    fn advance_by(&mut self, n: usize) { for _ in 0..n { self.advance(); } }
    fn starts_with(&self, s: &str) -> bool { self.source[self.pos..].starts_with(s) }

    fn expect(&mut self, ch: char) -> Result<(), ExprParseError> {
        if self.peek() != Some(ch) { return Err(self.err(format!("Expected {}", ch))); }
        self.advance(); Ok(())
    }

    fn expect_kw(&mut self, kw: &str) -> Result<(), ExprParseError> {
        if !self.starts_with_kw(kw) { return Err(self.err(format!("Expected {}", kw))); }
        self.advance_by(kw.len()); Ok(())
    }

    fn err(&self, msg: String) -> ExprParseError {
        let (line, column) = pos_to_line_col(self.source, self.pos);
        ExprParseError { msg, pos: self.pos, line, column }
    }
}

pub fn parse_expression(source: &str) -> Result<Expr, ExprParseError> {
    ExprParser::new(source).parse()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_string_literal() {
        let e = parse_expression("\"hello\"").unwrap();
        assert!(matches!(e, Expr::Literal { value: LiteralValue::String(ref s) } if s == "hello"));
    }

    #[test]
    fn test_int_literal() {
        let e = parse_expression("42").unwrap();
        assert!(matches!(e, Expr::Literal { value: LiteralValue::Int(42) }));
    }

    #[test]
    fn test_float_literal() {
        let e = parse_expression("2.5").unwrap();
        assert!(matches!(e, Expr::Literal { value: LiteralValue::Float(v) } if (v - 2.5_f64).abs() < 0.001));
    }

    #[test]
    fn test_bool_literal() {
        let e = parse_expression("True").unwrap();
        assert!(matches!(e, Expr::Variable { name } if name == "True"));
    }

    #[test]
    fn test_none() {
        let e = parse_expression("None").unwrap();
        assert!(matches!(e, Expr::None));
    }

    #[test]
    fn test_variable() {
        let e = parse_expression("my_var").unwrap();
        assert!(matches!(e, Expr::Variable { name } if name == "my_var"));
    }

    #[test]
    fn test_binary_op() {
        let e = parse_expression("1 + 2 * 3").unwrap();
        assert!(matches!(e, Expr::BinaryOp { op, .. } if op == "+"));
    }

    #[test]
    fn test_comparison() {
        let e = parse_expression("a <= b").unwrap();
        assert!(matches!(e, Expr::BinaryOp { op, .. } if op == "<="));
    }

    #[test]
    fn test_equality() {
        let e = parse_expression("x == y").unwrap();
        assert!(matches!(e, Expr::BinaryOp { op, .. } if op == "=="));
    }

    #[test]
    fn test_logical_and() {
        let e = parse_expression("a && b").unwrap();
        assert!(matches!(e, Expr::BinaryOp { op, .. } if op == "&&"));
    }

    #[test]
    fn test_unary_not() {
        let e = parse_expression("!active").unwrap();
        assert!(matches!(e, Expr::UnaryOp { op, .. } if op == "!"));
    }

    #[test]
    fn test_call() {
        let e = parse_expression("greet(\"world\")").unwrap();
        assert!(matches!(e, Expr::Call { .. }));
    }

    #[test]
    fn test_member_access() {
        let e = parse_expression("user.name").unwrap();
        assert!(matches!(e, Expr::MemberAccess { member, .. } if member == "name"));
    }

    #[test]
    fn test_index() {
        let e = parse_expression("items[0]").unwrap();
        assert!(matches!(e, Expr::Index { .. }));
    }

    #[test]
    fn test_list_literal() {
        let e = parse_expression("[1, 2, 3]").unwrap();
        assert!(matches!(e, Expr::List { elements } if elements.len() == 3));
    }

    #[test]
    fn test_empty_list() {
        let e = parse_expression("[]").unwrap();
        assert!(matches!(e, Expr::List { elements } if elements.is_empty()));
    }

    #[test]
    fn test_assignment() {
        let e = parse_expression("x = 5").unwrap();
        assert!(matches!(e, Expr::Assign { name, .. } if name == "x"));
    }

    #[test]
    fn test_if() {
        let e = parse_expression("if ready { run() }").unwrap();
        assert!(matches!(e, Expr::If { else_branch: None, .. }));
    }

    #[test]
    fn test_if_else() {
        let e = parse_expression("if ready { run() } else { wait() }").unwrap();
        assert!(matches!(e, Expr::If { else_branch: Some(_), .. }));
    }

    #[test]
    fn test_for_loop() {
        let e = parse_expression("for item in items { process(item) }").unwrap();
        assert!(matches!(e, Expr::For { var_name, .. } if var_name == "item"));
    }

    #[test]
    fn test_let_in() {
        let e = parse_expression("let x = 10 in x + 1").unwrap();
        assert!(matches!(e, Expr::Let { name, .. } if name == "x"));
    }

    #[test]
    fn test_block() {
        let e = parse_expression("{ a = 1; b = 2 }").unwrap();
        assert!(matches!(e, Expr::Block { statements } if statements.len() == 2));
    }

    #[test]
    fn test_return() {
        let e = parse_expression("return result").unwrap();
        assert!(matches!(e, Expr::Return { .. }));
    }

    #[test]
    fn test_try() {
        let e = parse_expression("fetch()?").unwrap();
        assert!(matches!(e, Expr::Try { .. }));
    }

    #[test]
    fn test_ok_some_err() {
        assert!(matches!(parse_expression("Ok(42)").unwrap(), Expr::Ok { .. }));
        assert!(matches!(parse_expression("Some(x)").unwrap(), Expr::Some { .. }));
        assert!(matches!(parse_expression("Err(\"fail\")").unwrap(), Expr::Error { .. }));
    }

    #[test]
    fn test_act() {
        let e = parse_expression("act Fetch(url: \"http://a.com\")").unwrap();
        assert!(matches!(e, Expr::Act { tool_name, .. } if tool_name == "Fetch"));
    }

    #[test]
    fn test_delegate() {
        let e = parse_expression("delegate Agent(query: \"hello\")").unwrap();
        assert!(matches!(e, Expr::Delegate { agent_name, .. } if agent_name == "Agent"));
    }

    #[test]
    fn test_think() {
        let e = parse_expression("think \"planning...\"").unwrap();
        assert!(matches!(e, Expr::Think { .. }));
    }

    #[test]
    fn test_observe() {
        let e = parse_expression("observe metric: 42").unwrap();
        assert!(matches!(e, Expr::Observe { name, .. } if name == "metric"));
    }

    #[test]
    fn test_model_call() {
        let e = parse_expression("model.complete(\"Hello\")").unwrap();
        assert!(matches!(e, Expr::ModelCall { .. }));
    }

    #[test]
    fn test_string_interpolation() {
        let e = parse_expression("\"Hello {name}!\"").unwrap();
        assert!(matches!(e, Expr::StringInterpolation { parts } if parts.len() == 3));
    }

    #[test]
    fn test_match() {
        let e = parse_expression("match val { A => 1, B => 2 }").unwrap();
        assert!(matches!(e, Expr::Match { arms, .. } if arms.len() == 2));
    }

    #[test]
    fn test_store() {
        let e = parse_expression("store memory = \"data\"").unwrap();
        assert!(matches!(e, Expr::Store { .. }));
    }

    #[test]
    fn test_complex_nested() {
        let src = r#"if status == "ok" { result.value } else { Err("fail") }"#;
        let e = parse_expression(src).unwrap();
        assert!(matches!(e, Expr::If { .. }));
    }

    #[test]
    fn test_empty_source() {
        let e = parse_expression("").unwrap();
        assert!(matches!(e, Expr::Literal { value: LiteralValue::Null }));
    }

    #[test]
    fn test_error_line_column() {
        let src = "\n\n1 + + 2";
        let err = parse_expression(src).unwrap_err();
        assert_eq!(err.line, 3, "expected line 3, got {}", err.line);
        assert_eq!(err.column, 5, "expected col 5, got {}", err.column);
        assert!(err.to_string().contains("3:5"), "error message should contain line:col");
    }

    #[test]
    fn test_while() {
        let e = parse_expression("while active { process() }").unwrap();
        assert!(matches!(e, Expr::While { .. }));
    }

    #[test]
    fn test_break() {
        let e = parse_expression("break").unwrap();
        assert!(matches!(e, Expr::Break));
    }

    #[test]
    fn test_continue() {
        let e = parse_expression("continue").unwrap();
        assert!(matches!(e, Expr::Continue));
    }

    #[test]
    fn test_go() {
        let e = parse_expression("go fetch(1)").unwrap();
        assert!(matches!(e, Expr::Go { .. }));
    }

    #[test]
    fn test_await() {
        let e = parse_expression("await f").unwrap();
        assert!(matches!(e, Expr::Await { .. }));
    }

    #[test]
    fn test_chan_unbounded() {
        let e = parse_expression("chan()").unwrap();
        assert!(matches!(e, Expr::Chan { capacity: None }));
    }

    #[test]
    fn test_chan_bounded() {
        let e = parse_expression("chan(10)").unwrap();
        assert!(matches!(e, Expr::Chan { capacity: Some(_) }));
    }

    #[test]
    fn test_select() {
        let e = parse_expression("select { c1 as msg => msg, c2 as alert => alert, default => \"none\" }").unwrap();
        if let Expr::Select { arms } = e {
            assert_eq!(arms.len(), 3);
            assert!(arms[0].is_default == false);
            assert_eq!(arms[0].var_name, "msg");
            assert!(arms[1].is_default == false);
            assert_eq!(arms[1].var_name, "alert");
            assert!(arms[2].is_default == true);
        } else {
            panic!("Expected Select expression");
        }
    }

    #[test]
    fn test_pool() {
        let e = parse_expression("pool(4, Agent)").unwrap();
        assert!(matches!(e, Expr::Pool { .. }));
    }

    #[test]
    fn test_match_guard() {
        let e = parse_expression("match x { A if x > 0 => \"pos\", B => \"other\" }").unwrap();
        if let Expr::Match { ref arms, .. } = e {
            assert_eq!(arms.len(), 2);
            assert!(arms[0].guard.is_some());
            assert!(arms[1].guard.is_none());
        } else {
            panic!("Expected Match expression");
        }
    }

    #[test]
    fn test_send() {
        let e = parse_expression("send \"agent1\", \"hello\"").unwrap();
        assert!(matches!(e, Expr::Send { .. }));
    }

    #[test]
    fn test_receive() {
        let e = parse_expression("receive(1000)").unwrap();
        assert!(matches!(e, Expr::Receive { .. }));
    }

    #[test]
    fn test_broadcast() {
        let e = parse_expression("broadcast \"alerts\", \"fire\"").unwrap();
        assert!(matches!(e, Expr::Broadcast { .. }));
    }

    #[test]
    fn test_discover() {
        let e = parse_expression("discover(\"*Worker\")").unwrap();
        assert!(matches!(e, Expr::Discover { .. }));
    }

    #[test]
    fn test_spawn() {
        let e = parse_expression("spawn \"agent.ax\", \"my_agent\"").unwrap();
        assert!(matches!(e, Expr::Spawn { .. }));
    }

    #[test]
    fn test_pause() {
        let e = parse_expression("pause(\"my_agent\")").unwrap();
        assert!(matches!(e, Expr::Pause { .. }));
    }

    #[test]
    fn test_resume() {
        let e = parse_expression("resume(\"my_agent\")").unwrap();
        assert!(matches!(e, Expr::Resume { .. }));
    }

    #[test]
    fn test_terminate() {
        let e = parse_expression("terminate(\"my_agent\")").unwrap();
        assert!(matches!(e, Expr::Terminate { .. }));
    }
}
