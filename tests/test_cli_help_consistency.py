from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from axon.cli import _make_arg_parser


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_COMMANDS = [
    "version",
    "info",
    "project-info",
    "foundation-audit",
    "handoff",
    "release-notes",
    "changelog",
    "release-bundle-manifest",
    "release-artifacts",
    "release-artifacts-check",
    "release-artifact-consistency",
    "task-template",
    "runtime-rfc-template",
    "runtime-plan",
    "runtime-plan-corpus",
    "runtime-plan-review",
    "runtime-plan-review-check",
    "runtime-governance",
    "runtime-governance-evidence",
    "runtime-governance-gate",
    "new",
    "init",
    "deps",
    "dependency-audit",
    "hygiene",
    "repo-hygiene",
    "precommit",
    "config",
    "syntax",
    "validate",
    "type-check",
    "token-budget",
    "lsp",
    "docs",
    "ast",
    "format",
    "check-project",
    "doctor",
    "build",
    "compile",
    "health",
    "serve",
    "serve-api",
    "smoke",
    "trace-preview",
    "trace-read",
    "trace-log",
    "run",
    "repl",
    "agent",
    "supervisor",
    "watch",
    "metrics",
    "secret",
    "eval",
    "govern",
    "ci-template",
    "explain",
    "add",
    "remove",
    "deploy",
    "debug",
    "profile",
    "replay",
    "dashboard",
    "playground",
    "quickstart",
    "test",
    "cheatsheet",
]

EXPECTED_OPTIONS = {
    "version": ["--json"],
    "info": ["--json", "--path", "--config"],
    "project-info": ["--json"],
    "foundation-audit": ["--json"],
    "handoff": ["--full", "--output", "--json"],
    "release-notes": ["--version", "--date", "--path", "--change", "--tests", "--output", "--json"],
    "changelog": ["--version", "--date", "--path", "--change", "--tests", "--output", "--json"],
    "release-bundle-manifest": ["--output", "--format", "--json"],
    "release-artifacts": ["--output-dir", "--version", "--date", "--change", "--tests", "--skip-corpus", "--json"],
    "release-artifacts-check": ["--json"],
    "release-artifact-consistency": ["--json"],
    "task-template": ["--number", "--title", "--module", "--output", "--json"],
    "runtime-rfc-template": ["--number", "--title", "--owner", "--status", "--output", "--json"],
    "runtime-plan": ["--json", "--write", "--check", "--root"],
    "runtime-plan-corpus": ["--examples-dir", "--snapshot-dir", "--allow-missing-snapshots", "--json"],
    "runtime-plan-review": ["--change", "--output", "--json"],
    "runtime-plan-review-check": ["--examples-dir", "--snapshot-dir", "--skip-corpus", "--json"],
    "runtime-governance": ["--examples-dir", "--snapshot-dir", "--skip-corpus", "--json"],
    "runtime-governance-evidence": ["--examples-dir", "--snapshot-dir", "--skip-corpus", "--output", "--format", "--json"],
    "runtime-governance-gate": ["--examples-dir", "--snapshot-dir", "--skip-corpus", "--json"],
    "new": ["--force", "--template"],
    "init": ["--force"],
    "deps": ["--json"],
    "dependency-audit": ["--json"],
    "hygiene": ["--json", "--write-gitignore", "--force"],
    "repo-hygiene": ["--json", "--write-gitignore", "--force"],
    "precommit": ["--path", "--hook-path", "--force", "--full", "--json"],
    "config": ["--config", "--json", "--resolve-env"],
    "syntax": ["--json"],
    "validate": ["--json", "--warnings-as-errors"],
    "ast": ["--no-lines", "--write", "--check"],
    "format": ["--check", "--write"],
    "check-project": ["--json", "--no-smoke", "--warnings-as-errors", "--snapshot-dir", "--require-snapshots"],
    "doctor": ["--json", "--no-smoke", "--warnings-as-errors", "--snapshot-dir", "--require-snapshots"],
    "build": ["--output", "--name", "--stdout", "--config"],
    "health": ["--json"],
    "serve": ["--output", "--name", "--config", "--dry-run", "--python"],
    "serve-api": ["--host", "--port", "--api-key"],
    "smoke": ["--name", "--json"],
    "trace-preview": ["--json", "--jsonl"],
    "trace-read": ["--type", "--agent", "--events", "--json", "--jsonl"],
    "trace-log": ["--type", "--agent", "--events", "--json", "--jsonl"],
    "run": ["--arg", "--trace", "--memory", "--checkpoint", "--mock", "--no-mock", "--flow", "--agent", "--replay", "--stream", "--sandbox-timeout", "--sandbox-max-depth", "--sandbox-denied", "--metrics", "--json"],
    "repl": ["--live", "--provider"],
    "agent": [],
    "supervisor": [],
    "watch": [],
    "metrics": [],
    "govern": ["--mesh-url", "--output", "--business-owner", "--technical-owner", "--target-environment"],
    "ci-template": ["--platform", "--output", "--mesh-url"],
    "explain": [],
    "eval": ["--iterations", "--baseline", "--json"],
    "add": ["--branch"],
    "remove": [],
    "deploy": ["--target", "--image-tag", "--file"],
    "debug": ["--non-interactive"],
    "profile": ["--json", "--csv", "--tool-csv", "--hotspot-threshold", "--max-hotspots"],
    "replay": ["--compare", "--threshold", "--json"],
    "dashboard": ["--trace", "--metrics", "--json", "--serve"],
    "playground": ["--host", "--port"],
    "quickstart": ["--name", "--use-case", "--model", "--non-interactive"],
    "test": ["--json", "--verbose"],
    "cheatsheet": [],
}


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError("CLI parser does not define subcommands")


def _command_help(command: str) -> str:
    parser = _make_arg_parser()
    subparsers = _subparser_action(parser)
    return subparsers.choices[command].format_help()


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_argparse_command_surface_matches_documented_contract():
    parser = _make_arg_parser()
    subparsers = _subparser_action(parser)
    assert set(subparsers.choices.keys()) == set(EXPECTED_COMMANDS)


def test_top_level_help_mentions_every_command():
    help_text = _make_arg_parser().format_help()
    for command in EXPECTED_COMMANDS:
        assert command in help_text


def test_every_command_help_is_available_and_mentions_expected_options():
    for command, options in EXPECTED_OPTIONS.items():
        help_text = _command_help(command)
        assert "usage:" in help_text
        for option in options:
            assert option in help_text


def test_readme_and_cli_reference_document_every_argparse_command():
    readme = _read("README.md")
    cli_reference = _read("docs/CLI_REFERENCE.md")

    for command in EXPECTED_COMMANDS:
        rendered = f"axon {command}"
        assert rendered in readme
        assert rendered in cli_reference


def test_cli_reference_mentions_each_expected_command_option():
    cli_reference = _read("docs/CLI_REFERENCE.md")
    for command, options in EXPECTED_OPTIONS.items():
        command_index = cli_reference.find(f"axon {command}")
        assert command_index != -1, f"missing CLI reference entry for axon {command}"
        for option in options:
            assert option in cli_reference[command_index:], f"{option} not documented for axon {command}"


def test_argparse_help_entrypoints_do_not_crash(capsys):
    # Keep this check in-process so the CLI contract remains fast and does not
    # depend on subprocess-heavy environments. `python -m axon` is covered by
    # command-specific tests elsewhere.
    for args in (["--help"], ["version", "--help"], ["info", "--help"], ["project-info", "--help"], ["foundation-audit", "--help"], ["handoff", "--help"], ["release-bundle-manifest", "--help"], ["release-artifacts", "--help"], ["release-artifacts-check", "--help"], ["task-template", "--help"], ["runtime-rfc-template", "--help"], ["runtime-plan", "--help"], ["runtime-plan-corpus", "--help"], ["runtime-plan-review", "--help"], ["runtime-plan-review-check", "--help"], ["runtime-governance", "--help"], ["runtime-governance-evidence", "--help"], ["runtime-governance-gate", "--help"], ["deps", "--help"], ["hygiene", "--help"], ["precommit", "--help"], ["release-notes", "--help"], ["build", "--help"], ["trace-read", "--help"]):
        try:
            _make_arg_parser().parse_args(list(args))
        except SystemExit as exc:
            assert exc.code == 0
        output = capsys.readouterr().out
        assert "usage:" in output
