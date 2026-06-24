use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

fn print_usage() {
    eprintln!("Usage: axon-parser <command> [args]");
    eprintln!("Commands:");
    eprintln!("  parse <source.ax> [--output ir.json]   Parse .ax file to IR JSON");
    eprintln!("  parse-expr <expression> [--output ast.json]  Parse AXON expression to AST JSON");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        print_usage();
        process::exit(1);
    }

    let command = &args[1];

    match command.as_str() {
        "parse" => {
            if args.len() < 3 {
                print_usage();
                process::exit(1);
            }
            let source_path = &args[2];
            let output_path = args
                .windows(2)
                .find(|w| w[0] == "--output")
                .map(|w| PathBuf::from(&w[1]));

            let source = match fs::read_to_string(source_path) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("Error reading '{}': {}", source_path, e);
                    process::exit(1);
                }
            };

            let ir = match axon_parser::parse_source(&source) {
                Ok(ir) => ir,
                Err(e) => {
                    eprintln!("Parse error: {}", e);
                    process::exit(1);
                }
            };

            let json = match serde_json::to_string_pretty(&ir) {
                Ok(j) => j,
                Err(e) => {
                    eprintln!("JSON serialization error: {}", e);
                    process::exit(1);
                }
            };

            write_or_print(json, output_path, "IR");
        }
        "parse-expr" => {
            if args.len() < 3 {
                print_usage();
                process::exit(1);
            }
            let expr_source = &args[2];
            let output_path = args
                .windows(2)
                .find(|w| w[0] == "--output")
                .map(|w| PathBuf::from(&w[1]));

            let ast = match axon_parser::expression::parse_expression(expr_source) {
                Ok(ast) => ast,
                Err(e) => {
                    eprintln!("Expression parse error: {}", e);
                    process::exit(1);
                }
            };

            let json = match serde_json::to_string_pretty(&ast) {
                Ok(j) => j,
                Err(e) => {
                    eprintln!("JSON serialization error: {}", e);
                    process::exit(1);
                }
            };

            write_or_print(json, output_path, "AST");
        }
        _ => {
            eprintln!("Unknown command: {}", command);
            print_usage();
            process::exit(1);
        }
    }
}

fn write_or_print(json: String, output_path: Option<PathBuf>, label: &str) {
    match output_path {
        Some(path) => {
            if let Err(e) = fs::write(&path, json) {
                eprintln!("Error writing '{}': {}", path.display(), e);
                std::process::exit(1);
            }
            println!("{} written to {}", label, path.display());
        }
        None => {
            println!("{}", json);
        }
    }
}
