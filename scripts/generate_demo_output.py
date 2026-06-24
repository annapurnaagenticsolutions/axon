#!/usr/bin/env python3
"""Generate a pretty demo output for README / screenshots.

Usage:
    python scripts/generate_demo_output.py

This creates a simulated terminal session showing AXON commands
and their output, suitable for pasting into README or docs.
"""

from __future__ import annotations

import textwrap


def _box(title: str, lines: list[str]) -> str:
    width = max(len(title), max(len(l) for l in lines)) + 4
    out = []
    out.append("┌" + "─" * (width - 2) + "┐")
    out.append(f"│ {title.ljust(width - 4)} │")
    out.append("├" + "─" * (width - 2) + "┤")
    for line in lines:
        out.append(f"│ {line.ljust(width - 4)} │")
    out.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(out)


def main() -> None:
    print("=" * 72)
    print("AXON Demo Session — Multi-Agent Research Pipeline")
    print("=" * 72)
    print()

    # Step 1: Validate
    print("$ axon validate examples/research_pipeline.ax")
    print("  ✓ Validated successfully")
    print("  Agents: 5, Tools: 2, RAGs: 1, Flows: 1")
    print()

    # Step 2: Run
    print("$ axon run examples/research_pipeline.ax --query 'What is AXON?'")
    print("  [RUN] ResearchCoordinator started")
    print("  [THINK] Starting research on: What is AXON? (depth: quick)")
    print("  [ACT] WebSearch(query='What is AXON?', max_results=5)")
    print("  [ACT] ResearchDocs.retrieve(query='What is AXON?', top_k=3)")
    print("  [OBSERVE] fact_check {claim: 'AXON is a programming language', ...}")
    print("  [STORE] last_report = {topic: 'What is AXON?', confidence: 0.92}")
    print("  [THINK] Research complete. Confidence: 0.92")
    print("  ✓ Execution finished in 4205ms")
    print("  Trace written to: trace.axontrace")
    print()

    # Step 3: Debug
    print("$ axon debug trace.axontrace --non-interactive")
    print("  AXON Debugger — 47 events loaded")
    print()
    events = [
        ("[1/47]", "THINK", "agent: ResearchCoordinator", "Starting research on: What is AXON?"),
        ("[2/47]", "ACT", "agent: ResearchCoordinator", "tool: WebSearch, args: {q: 'What is AXON?'}"),
        ("[3/47]", "ACT", "agent: ResearchCoordinator", "tool: ResearchDocs.retrieve, args: {query: 'What is AXON?', top_k: 3}"),
        ("[4/47]", "THINK", "agent: QueryPlanner", "Decomposed into 3 sub-queries"),
        ("[5/47]", "ACT", "agent: FactCheckerAgent", "tool: WebSearch, args: {q: 'AXON programming language'}"),
        ("[47/47]", "STORE", "agent: ResearchCoordinator", "key: last_report, value: {confidence: 0.92}"),
    ]
    for idx, etype, meta, detail in events:
        print(f"  {idx} {etype:6} {meta}")
        print(f"       {detail}")
    print()

    # Step 4: Profile
    print("$ axon profile trace.axontrace")
    print("  AXON Profile: 4205.3ms overall, 47 events")
    print("    ResearchCoordinator: 1802.1ms, 12 events, 3 acts (avg 120.0ms)")
    print("    QueryPlanner:        245.3ms,  4 events, 1 act (avg 80.0ms)")
    print("    ResearchAgent:       1450.2ms, 18 events, 9 acts (avg 110.0ms)")
    print("    SummarizerAgent:     380.5ms,  5 events, 0 acts")
    print("    FactCheckerAgent:     327.2ms,  8 events, 2 acts (avg 90.0ms)")
    print()

    # Step 5: Compile
    print("$ axon compile examples/research_pipeline.ax --target ts -o research.ts")
    print("  TypeScript written to research.ts")
    print("  Generated: 5 interfaces, 5 classes, 8 helper functions")
    print()

    # Step 6: Deploy
    print("$ axon deploy --target fly")
    print("  Building Docker image: axon-app:research-pipeline...")
    print("  ✓ Built image: axon-app:research-pipeline")
    print("  Deploying to Fly.io...")
    print("  ✓ Deployed to https://research-pipeline.fly.dev")
    print()

    print("=" * 72)
    print("End of demo")
    print("=" * 72)


if __name__ == "__main__":
    main()
