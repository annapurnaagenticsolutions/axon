#!/usr/bin/env python3
"""AXON Demo Runner — showcases real-world agents with live providers.

Usage:
    python examples/run_demos.py                    # mock mode (no API keys needed)
    python examples/run_demos.py --live             # live mode (needs API key)
    python examples/run_demos.py --live --provider groq   # use Groq
    python examples/run_demos.py --live --provider openai # use OpenAI
    python examples/run_demos.py --code-review src/main.py
    python examples/run_demos.py --summarize https://httpbin.org/json
"""

import argparse
import subprocess
import sys
from pathlib import Path


EXAMPLES_DIR = Path(__file__).parent
PROJECT_ROOT = EXAMPLES_DIR.parent


def run_code_review(file_path: str, live: bool, provider: str) -> int:
    """Run the code review agent on a file."""
    cmd = [
        sys.executable, "-m", "axon", "run",
        str(EXAMPLES_DIR / "code_review.ax"),
        "--arg", f"file_path={file_path}",
        "--trace", "trace_code_review.jsonl",
    ]
    if live:
        cmd.extend(["--live", "--provider", provider])
    print(f"\n{'='*60}")
    print(f"  Code Review Agent  →  {file_path}")
    print(f"  Mode: {'LIVE (' + provider + ')' if live else 'MOCK'}")
    print(f"{'='*60}\n")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def run_content_summarizer(url: str, live: bool, provider: str) -> int:
    """Run the content summarizer agent on a URL."""
    cmd = [
        sys.executable, "-m", "axon", "run",
        str(EXAMPLES_DIR / "content_summarizer.ax"),
        "--arg", f"url={url}",
        "--trace", "trace_summary.jsonl",
    ]
    if live:
        cmd.extend(["--live", "--provider", provider])
    print(f"\n{'='*60}")
    print(f"  Content Summarizer Agent  →  {url}")
    print(f"  Mode: {'LIVE (' + provider + ')' if live else 'MOCK'}")
    print(f"{'='*60}\n")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AXON demo agents (code review + content summarizer)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="enable live provider calls (requires API keys)",
    )
    parser.add_argument(
        "--provider",
        default="groq",
        choices=["groq", "openai", "anthropic"],
        help="provider to use with --live (default: groq)",
    )
    parser.add_argument(
        "--code-review",
        metavar="FILE",
        help="run code review agent on the given file",
    )
    parser.add_argument(
        "--summarize",
        metavar="URL",
        help="run content summarizer agent on the given URL",
    )
    args = parser.parse_args()

    exit_code = 0

    if args.code_review:
        exit_code = run_code_review(args.code_review, args.live, args.provider)
        if exit_code != 0:
            return exit_code

    if args.summarize:
        exit_code = run_content_summarizer(args.summarize, args.live, args.provider)
        if exit_code != 0:
            return exit_code

    if not args.code_review and not args.summarize:
        # Run both demos with defaults
        exit_code = run_code_review("examples/hello.ax", args.live, args.provider)
        if exit_code != 0:
            print("\nCode review demo failed. Continuing to summarizer...\n")
        exit_code = run_content_summarizer(
            "https://httpbin.org/json", args.live, args.provider
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
