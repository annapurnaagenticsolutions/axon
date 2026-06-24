//! Micro-benchmarks for the AXON parser.
//!
//! Run with `cargo test bench:: -- --nocapture` to see timings.

const STRESS_SMALL: &str = include_str!("../../tests/fixtures/stress_small.ax");
const STRESS_LARGE: &str = include_str!("../../tests/fixtures/stress_large.ax");

#[cfg(test)]
mod tests {
    use std::time::Instant;
    use crate::parse_source;
    use crate::expression::parse_expression;
    use super::*;

    #[test]
    fn bench_parse_stress_small() {
        let iters = 100;
        let start = Instant::now();
        for _ in 0..iters {
            let _ = parse_source(STRESS_SMALL);
        }
        let elapsed = start.elapsed();
        let avg_us = elapsed.as_micros() as f64 / iters as f64;
        println!("stress_small ({} bytes): {} iters in {:?} => {:.1} us/iter",
                 STRESS_SMALL.len(), iters, elapsed, avg_us);
    }

    #[test]
    fn bench_parse_stress_large() {
        let iters = 20;
        let start = Instant::now();
        for _ in 0..iters {
            let _ = parse_source(STRESS_LARGE);
        }
        let elapsed = start.elapsed();
        let avg_ms = elapsed.as_millis() as f64 / iters as f64;
        println!("stress_large ({} bytes): {} iters in {:?} => {:.2} ms/iter",
                 STRESS_LARGE.len(), iters, elapsed, avg_ms);
    }

    #[test]
    fn bench_parse_simple_agent() {
        let src = r#"agent Bot { model: @mock/gpt fn run() -> Str { "hello" } }"#;
        let iters = 10000;
        let start = Instant::now();
        for _ in 0..iters {
            let _ = parse_source(src);
        }
        let elapsed = start.elapsed();
        let avg_ns = elapsed.as_nanos() as f64 / iters as f64;
        println!("simple_agent: {} iters in {:?} => {:.0} ns/iter",
                 iters, elapsed, avg_ns);
    }

    #[test]
    fn bench_expression_parser() {
        let src = r#"if status == "ok" { result.value } else { Err("fail") }"#;
        let iters = 10000;
        let start = Instant::now();
        for _ in 0..iters {
            let _ = parse_expression(src);
        }
        let elapsed = start.elapsed();
        let avg_ns = elapsed.as_nanos() as f64 / iters as f64;
        println!("expression: {} iters in {:?} => {:.0} ns/iter",
                 iters, elapsed, avg_ns);
    }

    #[test]
    fn bench_type_alias_with_fields() {
        let src = "type Issue = { id: Int, title: Str, priority: Int, labels: List<Str> }\n";
        let iters = 10000;
        let start = Instant::now();
        for _ in 0..iters {
            let _ = parse_source(src);
        }
        let elapsed = start.elapsed();
        let avg_ns = elapsed.as_nanos() as f64 / iters as f64;
        println!("type_alias: {} iters in {:?} => {:.0} ns/iter",
                 iters, elapsed, avg_ns);
    }

    #[test]
    fn bench_annotations_top_level() {
        let src = "@trace\n@cache(ttl: 60)\nagent Bot { model: @mock/gpt fn run() -> Str { \"hi\" } }\n";
        let iters = 10000;
        let start = Instant::now();
        for _ in 0..iters {
            let _ = parse_source(src);
        }
        let elapsed = start.elapsed();
        let avg_ns = elapsed.as_nanos() as f64 / iters as f64;
        println!("annotations: {} iters in {:?} => {:.0} ns/iter",
                 iters, elapsed, avg_ns);
    }
}
