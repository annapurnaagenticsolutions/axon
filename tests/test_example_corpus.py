from __future__ import annotations

import py_compile
from pathlib import Path

from axon.ast_snapshot import check_snapshot_file, source_file_to_snapshot_json
from axon.cli import build_to_stdout, syntax_check_file, validate_file
from axon.parser import parse
from axon.smoke import smoke_test_source_file
from axon.validator import has_errors, validate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
EXAMPLE_SNAPSHOTS_DIR = ROOT / "tests" / "snapshots" / "examples"

CORE_EXAMPLE_NAMES = {
    "hello.ax",
    "hello_run.ax",
    "types.ax",
    "prompts.ax",
    "rag.ax",
    "flow.ax",
    "trace_preview.ax",
    "github_triage.ax",
    "customer_support.ax",
    "invoice_extraction.ax",
    "monitoring_alerts.ax",
    "meeting_notes.ax",
    "data_analysis.ax",
    "debate.ax",
}


def _example_paths() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.ax"))


def test_example_corpus_contains_expected_reference_files():
    names = {path.name for path in _example_paths()}
    assert CORE_EXAMPLE_NAMES.issubset(names)


def test_every_example_parses_and_has_at_least_one_declaration():
    for path in _example_paths():
        declarations = parse(path.read_text(encoding="utf-8"))
        assert declarations, f"{path.name} did not parse into declarations"


def test_every_example_passes_syntax_command():
    for path in _example_paths():
        exit_code, output = syntax_check_file(path)
        assert exit_code == 0, f"{path.name} syntax failed:\n{output}"
        assert "OK:" in output


def test_every_example_has_no_validation_errors():
    for path in _example_paths():
        declarations = parse(path.read_text(encoding="utf-8"))
        diagnostics = validate(declarations)
        assert not has_errors(diagnostics), (
            f"{path.name} validation errors:\n"
            + "\n".join(diagnostic.format() for diagnostic in diagnostics)
        )


def test_every_example_passes_validate_command_without_warnings_as_errors():
    for path in _example_paths():
        exit_code, output = validate_file(path)
        assert exit_code == 0, f"{path.name} validate command failed:\n{output}"


def test_every_example_generates_compilable_server_code(tmp_path: Path):
    for path in _example_paths():
        code = build_to_stdout(path)
        generated = tmp_path / f"{path.stem}_server.py"
        generated.write_text(code, encoding="utf-8")
        py_compile.compile(str(generated), doraise=True)


def test_every_example_passes_generated_server_smoke_test():
    for path in _example_paths():
        report = smoke_test_source_file(path)
        assert report.passed, (
            f"{path.name} smoke failed:\n"
            + "\n".join(diagnostic.format() for diagnostic in report.diagnostics)
        )


def test_every_example_can_render_stable_ast_json():
    for path in _example_paths():
        rendered = source_file_to_snapshot_json(path, include_lines=False)
        assert '"node"' in rendered
        assert '"line"' not in rendered




def test_every_example_has_checked_in_ast_snapshot():
    for path in _example_paths():
        snapshot = EXAMPLE_SNAPSHOTS_DIR / f"{path.stem}.ast.json"
        assert snapshot.exists(), f"missing AST snapshot for {path.name}: {snapshot}"
        result = check_snapshot_file(path, snapshot)
        assert result.matched, result.message


def test_example_snapshot_directory_has_no_orphan_snapshots():
    example_stems = {path.stem for path in _example_paths()}
    snapshot_stems = {path.stem.replace(".ast", "") for path in EXAMPLE_SNAPSHOTS_DIR.glob("*.ast.json")}
    assert snapshot_stems == example_stems

def test_realistic_examples_cover_major_domain_patterns():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in _example_paths())
    expected_terms = [
        "GitHubTriageAgent",
        "CustomerSupportAgent",
        "InvoiceExtractionAgent",
        "MonitoringAgent",
        "MeetingNotesAgent",
        "DataAnalysisAgent",
        "DebatePipeline",
        "ProductDocs.retrieve",
        "@schedule(every: 5.minutes)",
        "think \"Fetch untriaged issues and classify them\"",
    ]
    for term in expected_terms:
        assert term in combined


def test_examples_readme_mentions_all_corpus_files():
    readme = (EXAMPLES_DIR / "README.md").read_text(encoding="utf-8")
    for name in sorted(CORE_EXAMPLE_NAMES):
        assert f"`{name}`" in readme
