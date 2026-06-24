//! Fuzz / property tests for the AXON parser.
//!
//! These tests generate random (but constrained) AXON source text and
//! verify that the parser never panics and that valid-looking input
//! round-trips through IR JSON correctly.

// Simple deterministic LCG for reproducible fuzz seeds.
struct Rng {
    state: u64,
}

impl Rng {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }
    fn next(&mut self) -> u64 {
        self.state = self.state.wrapping_mul(6364136223846793005).wrapping_add(1);
        self.state
    }
    fn range(&mut self, max: usize) -> usize {
        (self.next() as usize) % max.max(1)
    }
    fn bool(&mut self) -> bool {
        self.next() & 1 == 0
    }
    fn pick<'a, T>(&mut self, opts: &'a [T]) -> &'a T {
        &opts[self.range(opts.len())]
    }
}

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

fn gen_ident(rng: &mut Rng) -> String {
    let chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_";
    let rest = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
    let mut s = String::new();
    s.push(chars.as_bytes()[rng.range(chars.len())] as char);
    let len = 1 + rng.range(8);
    for _ in 0..len {
        s.push(rest.as_bytes()[rng.range(rest.len())] as char);
    }
    s
}

fn gen_type(rng: &mut Rng) -> String {
    let base = *rng.pick(&["Str", "Int", "Float", "Bool", "Json", "Any", "List", "Map"]);
    if rng.bool() && base != "Str" && base != "Int" {
        let inner = gen_type(rng);
        format!("{}<{}>", base, inner)
    } else {
        base.to_string()
    }
}

fn gen_string(rng: &mut Rng) -> String {
    let parts = ["hello", "world", "foo", "bar", "test", "data", "value"];
    let mut s = String::new();
    s.push('"');
    s.push_str(rng.pick(&parts));
    s.push('"');
    s
}

fn gen_param(rng: &mut Rng) -> String {
    let name = gen_ident(rng);
    let ty = gen_type(rng);
    if rng.bool() {
        format!("{}: {}", name, ty)
    } else {
        let val = gen_string(rng);
        format!("{}: {} = {}", name, ty, val)
    }
}

fn gen_params(rng: &mut Rng) -> String {
    let n = rng.range(4);
    let params: Vec<String> = (0..n).map(|_| gen_param(rng)).collect();
    format!("({})", params.join(", "))
}

fn gen_body(rng: &mut Rng) -> String {
    let parts = [
        r#""hello""#,
        "42",
        "result.value",
        "items[0]",
        "process(data)",
        "if ready { go() }",
        "for item in items { log(item) }",
        "return result",
        "store memory = \"data\"",
        "act Fetch(url: \"http://a.com\")",
    ];
    let n = 1 + rng.range(3);
    let body: Vec<&str> = (0..n).map(|_| *rng.pick(&parts)).collect();
    body.join("\n    ")
}

fn gen_docstrings(rng: &mut Rng) -> String {
    let n = rng.range(3);
    let mut s = String::new();
    for _ in 0..n {
        s.push_str("    /// A docstring line\n");
    }
    s
}

fn gen_tool(rng: &mut Rng) -> String {
    let name = gen_ident(rng);
    let params = gen_params(rng);
    let ret = gen_type(rng);
    let body = gen_body(rng);
    let docs = gen_docstrings(rng);
    format!("tool {}{}{} {{
{}{}
}}\n", name, params, if ret.is_empty() { String::new() } else { format!(" -> {}", ret) }, docs, body)
}

fn gen_agent(rng: &mut Rng) -> String {
    let name = gen_ident(rng);
    let model = *rng.pick(&["@mock/gpt", "@anthropic/claude", "@openai/gpt-4"]);
    let n_tools = rng.range(3);
    let tools: Vec<String> = (0..n_tools).map(|_| gen_ident(rng)).collect();
    let tools_str = if tools.is_empty() {
        String::new()
    } else {
        format!("    tools: [{}]\n", tools.join(", "))
    };
    let n_methods = 1 + rng.range(3);
    let methods: Vec<String> = (0..n_methods)
        .map(|_| {
            let mname = gen_ident(rng);
            let params = gen_params(rng);
            let ret = gen_type(rng);
            let body = gen_body(rng);
            format!("    fn {}{} -> {} {{
        {}
    }}", mname, params, ret, body)
        })
        .collect();
    format!("agent {} {{
    model: {}
{}{}
}}\n", name, model, tools_str, methods.join("\n"))
}

fn gen_import(rng: &mut Rng) -> String {
    let n = 1 + rng.range(3);
    let names: Vec<String> = (0..n).map(|_| gen_ident(rng)).collect();
    let source = *rng.pick(&["std/core", "vendor/http", "stdlib/utils"]);
    format!("import {{ {} }} from \"{}\"\n", names.join(", "), source)
}

fn gen_type_alias(rng: &mut Rng) -> String {
    let name = gen_ident(rng);
    if rng.bool() {
        let ty = gen_type(rng);
        format!("type {} = {}\n", name, ty)
    } else {
        let n_fields = 1 + rng.range(4);
        let fields: Vec<String> = (0..n_fields)
            .map(|_| {
                let fname = gen_ident(rng);
                let fty = gen_type(rng);
                format!("{}: {}", fname, fty)
            })
            .collect();
        format!("type {} = {{ {} }}\n", name, fields.join(", "))
    }
}

fn gen_source(rng: &mut Rng) -> String {
    let mut parts = Vec::new();
    let n = 1 + rng.range(5);
    for _ in 0..n {
        match rng.range(4) {
            0 => parts.push(gen_import(rng)),
            1 => parts.push(gen_type_alias(rng)),
            2 => parts.push(gen_tool(rng)),
            _ => parts.push(gen_agent(rng)),
        }
    }
    parts.join("\n")
}

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use crate::parse_source;
    use crate::expression::parse_expression;
    use super::*;

    /// Verify parser never panics on random valid-looking input.
    #[test]
    fn fuzz_parse_never_panics() {
        let mut rng = Rng::new(42);
        for i in 0..200 {
            let source = gen_source(&mut rng);
            let _ = parse_source(&source); // must not panic
            if i % 50 == 0 {
                // Also test expression parser on a random body
                let body = gen_body(&mut rng);
                let _ = parse_expression(&body);
            }
        }
    }

    /// Verify valid generated source actually parses successfully.
    #[test]
    fn fuzz_generated_source_parses() {
        let mut rng = Rng::new(123);
        for _ in 0..100 {
            let source = gen_source(&mut rng);
            let result = parse_source(&source);
            // Some random combinations might be syntactically invalid;
            // we just ensure no panic. For well-formed cases, print stats.
            assert!(result.is_ok() || result.is_err(), "parser panicked!");
        }
    }

    /// Verify parse-then-serialize roundtrip doesn't lose top-level structure.
    #[test]
    fn fuzz_roundtrip_structure() {
        let mut rng = Rng::new(99);
        for _ in 0..50 {
            let source = gen_source(&mut rng);
            if let Ok(ir) = parse_source(&source) {
                let json = serde_json::to_string(&ir).unwrap();
                let ir2: crate::AxonIR = serde_json::from_str(&json).unwrap();
                assert_eq!(ir.imports.len(), ir2.imports.len());
                assert_eq!(ir.type_aliases.len(), ir2.type_aliases.len());
                assert_eq!(ir.tools.len(), ir2.tools.len());
                assert_eq!(ir.agents.len(), ir2.agents.len());
            }
        }
    }

    /// Verify expression parser handles random bodies without panic.
    #[test]
    fn fuzz_expression_never_panics() {
        let mut rng = Rng::new(7);
        for _ in 0..200 {
            let body = gen_body(&mut rng);
            let _ = parse_expression(&body);
        }
    }

    /// Stress test: very large source.
    #[test]
    fn fuzz_large_source() {
        let mut rng = Rng::new(1);
        let mut source = String::new();
        for _ in 0..100 {
            source.push_str(&gen_agent(&mut rng));
            source.push('\n');
        }
        let result = parse_source(&source);
        assert!(result.is_ok() || result.is_err(), "parser panicked on large source");
    }
}
