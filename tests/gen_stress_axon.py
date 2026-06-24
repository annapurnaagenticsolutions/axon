#!/usr/bin/env python3
"""Generate synthetic large AXON files for parser stress testing."""

import argparse
from pathlib import Path


def gen_agents(n_agents: int, n_tools: int, n_methods: int, body_lines: int) -> str:
    lines = []

    # Generate tools
    for t in range(n_tools):
        lines.append(f'tool Tool{t}(x: Str, y: Int = 0) -> Str {{')
        for _ in range(body_lines):
            lines.append(f'    "line of body text for tool {t}"')
        lines.append('}')
        lines.append('')

    # Generate agents
    for a in range(n_agents):
        tool_refs = ', '.join(f'Tool{t}' for t in range(min(3, n_tools)))
        lines.append(f'agent Agent{a} {{')
        lines.append(f'    model: @mock/gpt-{a % 5}')
        if n_tools > 0:
            lines.append(f'    tools: [{tool_refs}]')
        lines.append(f'    memory: Memory<Semantic>')
        lines.append('')

        for m in range(n_methods):
            lines.append(f'    fn method{m}(q: Str) -> Str {{')
            for _ in range(body_lines):
                lines.append(f'        "line of body text for method {m}"')
            lines.append('    }')

        lines.append('}')
        lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", type=int, default=10)
    parser.add_argument("--tools", type=int, default=5)
    parser.add_argument("--methods", type=int, default=3)
    parser.add_argument("--body-lines", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    src = gen_agents(args.agents, args.tools, args.methods, args.body_lines)
    args.output.write_text(src)
    size = args.output.stat().st_size
    print(f"Wrote {args.output} ({size:,} bytes, {len(src.splitlines()):,} lines)")


if __name__ == "__main__":
    main()
