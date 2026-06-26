/* tslint:disable */
/* eslint-disable */

/**
 * Compile AXON source (parse + validate) and return IR JSON.
 * Returns error string if validation fails.
 */
export function compile_axon(source: string): string;

/**
 * Evaluate an AXON expression (given as AST JSON) with a scope (JSON object).
 * Returns the result as JSON, or an error JSON string.
 */
export function evaluate_expr(expr_json: string, scope_json: string, max_depth: number): string;

/**
 * Parse AXON source text and return IR JSON.
 */
export function parse_axon(source: string): string;

/**
 * Parse a single AXON expression and return AST JSON.
 */
export function parse_expr(source: string): string;

/**
 * Validate AXON source and return diagnostics JSON.
 */
export function validate_axon(source: string): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly compile_axon: (a: number, b: number) => [number, number, number, number];
    readonly evaluate_expr: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly parse_axon: (a: number, b: number) => [number, number, number, number];
    readonly parse_expr: (a: number, b: number) => [number, number, number, number];
    readonly validate_axon: (a: number, b: number) => [number, number, number, number];
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
