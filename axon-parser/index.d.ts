/**
 * Parse AXON source text and return IR JSON string.
 * @param source — AXON source code (.ax)
 * @returns Pretty-printed IR JSON (AxonIR v0.2 schema)
 * @throws Error on parse failure
 */
export function parse_axon(source: string): string;

/**
 * Evaluate an AXON expression (given as AST JSON) with a scope (JSON object).
 * @param exprJson — AST JSON string (from parse_expr)
 * @param scopeJson — Scope as JSON object string, e.g. '{"x": 1}'
 * @param maxDepth — Maximum evaluation depth (e.g. 100)
 * @returns Result JSON string, or error JSON string
 * @throws Error on invalid input
 */
export function evaluate_expr(exprJson: string, scopeJson: string, maxDepth: number): string;

// Re-export init for browser/web entry point
export function init(module_or_path?: WebAssembly.Module | BufferSource | string | URL | Request | Promise<InitInput>): Promise<InitOutput>;
export function initSync(module: WebAssembly.Module | BufferSource): InitOutput;

export interface InitOutput {
  readonly memory: WebAssembly.Memory;
  readonly parse_axon: (a: number, b: number) => [number, number, number, number];
}

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;
