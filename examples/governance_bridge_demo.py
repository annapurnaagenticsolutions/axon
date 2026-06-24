#!/usr/bin/env python3
"""AXON → AgentOps Mesh Governance Bridge Demo

Demonstrates the end-to-end pipeline:
    .ax file → parse → validate → compile to governance JSON
    → (optionally) submit to AgentOps Mesh API → 9-gate governance workflow

Usage:
    python examples/governance_bridge_demo.py
    python examples/governance_bridge_demo.py --submit http://localhost:8000
"""
import json
import sys
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from axon.parser import parse
from axon.validator import validate
from axon.codegen.governance import generate_governance_submission


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AXON → AgentOps Mesh governance bridge demo")
    parser.add_argument("--source", default="examples/research_pipeline.ax",
                        help="path to .ax source file")
    parser.add_argument("--submit", default=None,
                        help="AgentOps Mesh API URL to submit to (e.g. http://localhost:8000)")
    parser.add_argument("--output", "-o", default=None,
                        help="write governance JSON to file")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: source file not found: {args.source}", file=sys.stderr)
        return 1

    # Step 1: Parse
    print(f"[1/4] Parsing {source_path.name}...")
    declarations = parse(source_path.read_text(encoding="utf-8"))
    agents = [d for d in declarations if d.__class__.__name__ == "AgentDecl"]
    tools = [d for d in declarations if d.__class__.__name__ == "ToolDecl"]
    print(f"      Found {len(agents)} agent(s), {len(tools)} tool(s)")

    # Step 2: Validate
    print("[2/4] Validating...")
    diagnostics = validate(declarations)
    errors = [d for d in diagnostics if d.severity == "error"]
    if errors:
        for e in errors:
            print(f"  error: {e}", file=sys.stderr)
        return 1
    print(f"      Validation passed ({len(diagnostics)} diagnostics)")

    # Step 3: Generate governance submission
    print("[3/4] Generating AgentOps Mesh governance submission...")
    submission = generate_governance_submission(
        declarations,
        source_filename=source_path.name,
    )
    print(f"      use_case_id: {submission['use_case_id']}")
    print(f"      domain: {submission['domain']}")
    print(f"      autonomy_level: {submission['autonomy_level']}")
    print(f"      risk_factors: {json.dumps(submission['risk_factors'])}")

    gov_json = json.dumps(submission, indent=2)

    if args.output:
        Path(args.output).write_text(gov_json, encoding="utf-8")
        print(f"      Written to {args.output}")

    # Step 4: Submit to AgentOps Mesh (optional)
    if args.submit:
        print(f"[4/4] Submitting to AgentOps Mesh at {args.submit}...")
        try:
            import urllib.request
            url = f"{args.submit}/governance/run"
            req = urllib.request.Request(
                url,
                data=gov_json.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                print(f"      Overall decision: {result.get('overall_decision', 'N/A')}")
                print(f"      Gates passed: {sum(1 for g in result.get('gates', []) if g.get('status') == 'pass')}")
                print(f"      Gates with caution: {sum(1 for g in result.get('gates', []) if g.get('status') == 'caution')}")
                print(f"      Gates failed: {sum(1 for g in result.get('gates', []) if g.get('status') == 'fail')}")
                if args.output:
                    base = Path(args.output).stem
                    Path(f"{base}_result.json").write_text(
                        json.dumps(result, indent=2), encoding="utf-8"
                    )
                    print(f"      Result written to {base}_result.json")
        except Exception as e:
            print(f"      Submit failed: {e}", file=sys.stderr)
            print(f"      (Is AgentOps Mesh running at {args.submit}?)")
            return 1
    else:
        print("[4/4] Skipping submission (use --submit URL to submit to AgentOps Mesh)")
        print()
        print("--- Governance Submission JSON ---")
        print(gov_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
