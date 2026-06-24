/**
 * Parse AXON source text and return IR JSON string.
 * @param source — AXON source code (.ax)
 * @returns Pretty-printed IR JSON (AxonIR v0.2 schema)
 * @throws Error on parse failure
 */
export function parse_axon(source: string): string;

// Re-export init for browser/web entry point
export function init(module_or_path?: WebAssembly.Module | BufferSource | string | URL | Request | Promise<InitInput>): Promise<InitOutput>;
export function initSync(module: WebAssembly.Module | BufferSource): InitOutput;

export interface InitOutput {
  readonly memory: WebAssembly.Memory;
  readonly parse_axon: (a: number, b: number) => [number, number, number, number];
}

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;
