"""Tests for axon ci-template and axon explain CLI commands."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from axon.cli import main, _generate_ci_template, _explain_diagnostics, _diagnostic_fix_suggestion


class TestCITemplate:
    """Test the axon ci-template command."""

    def test_github_actions_template(self):
        template = _generate_ci_template("github-actions")
        assert "name: AXON CI" in template
        assert "ubuntu-latest" in template
        assert "axon validate" in template
        assert "axon type-check" in template
        assert "axon hygiene" in template
        assert "pytest" in template

    def test_github_actions_with_mesh_url(self):
        template = _generate_ci_template("github-actions", mesh_url="http://localhost:8000")
        assert "governance" in template.lower()
        assert "axon govern" in template
        assert "http://localhost:8000" in template
        assert "continue-on-error" in template

    def test_gitlab_ci_template(self):
        template = _generate_ci_template("gitlab-ci")
        assert "stages:" in template
        assert "lint" in template
        assert "test" in template
        assert "axon validate" in template
        assert "pytest" in template

    def test_gitlab_ci_with_mesh_url(self):
        template = _generate_ci_template("gitlab-ci", mesh_url="http://mesh:8000")
        assert "governance" in template.lower()
        assert "axon govern" in template
        assert "http://mesh:8000" in template
        assert "allow_failure" in template

    def test_unsupported_platform(self):
        template = _generate_ci_template("unsupported")
        assert "Unsupported" in template

    def test_cli_ci_template_stdout(self, capsys):
        ret = main(["ci-template", "--platform", "github-actions"])
        captured = capsys.readouterr()
        assert ret == 0
        assert "AXON CI" in captured.out

    def test_cli_ci_template_to_file(self, tmp_path, capsys):
        out_file = tmp_path / "ci.yml"
        ret = main(["ci-template", "--platform", "github-actions", "-o", str(out_file)])
        captured = capsys.readouterr()
        assert ret == 0
        assert "CI template written" in captured.out
        content = out_file.read_text(encoding="utf-8")
        assert "AXON CI" in content

    def test_cli_ci_template_with_mesh_url(self, capsys):
        ret = main(["ci-template", "--platform", "github-actions", "--mesh-url", "http://localhost:8000"])
        captured = capsys.readouterr()
        assert ret == 0
        assert "axon govern" in captured.out


class TestExplain:
    """Test the axon explain command."""

    def test_explain_valid_file(self, capsys):
        # Use hello.ax which should be valid
        hello_path = Path(__file__).resolve().parent.parent / "examples" / "hello.ax"
        if not hello_path.exists():
            pytest.skip("hello.ax not found")
        ret = main(["explain", str(hello_path)])
        captured = capsys.readouterr()
        # Should either pass (0) or have warnings (0)
        assert ret == 0
        assert "Everything looks good" in captured.out or "AXON Explanation" in captured.out

    def test_explain_nonexistent_file(self, capsys):
        ret = main(["explain", "nonexistent.ax"])
        captured = capsys.readouterr()
        assert ret != 0
        assert "not found" in captured.err or "not found" in captured.out

    def test_explain_diagnostics_with_errors(self):
        class MockDiag:
            def __init__(self, message, code="", line=10, hint=""):
                self.message = message
                self.code = code
                self.line = line
                self.hint = hint
                self.severity = "error"

        errors = [MockDiag("tool 'Foo' must include at least one /// docstring line", code="tool-docstring", line=5)]
        warnings = []
        result = _explain_diagnostics(errors, warnings, "test.ax")
        assert "1 error" in result
        assert "tool 'Foo'" in result
        assert "docstring" in result
        assert "line 5" in result

    def test_explain_diagnostics_with_warnings(self):
        class MockDiag:
            def __init__(self, message, code="", line=0, hint=""):
                self.message = message
                self.code = code
                self.line = line
                self.hint = hint
                self.severity = "warning"

        errors = []
        warnings = [MockDiag("Unused type alias 'Foo'", code="unused-type", line=20)]
        result = _explain_diagnostics(errors, warnings, "test.ax")
        assert "1 warning" in result
        assert "Unused type alias" in result
        assert "No blocking errors" in result

    def test_explain_diagnostics_no_issues(self):
        result = _explain_diagnostics([], [], "clean.ax")
        # Empty errors and warnings — should have no error/warning sections
        assert "AXON Explanation" in result

    def test_diagnostic_fix_suggestion_known_codes(self):
        class MockDiag:
            def __init__(self, code, message=""):
                self.code = code
                self.message = message
                self.line = 1
                self.hint = ""

        assert "docstring" in _diagnostic_fix_suggestion(MockDiag("tool-docstring"))
        assert "run()" in _diagnostic_fix_suggestion(MockDiag("agent-missing-run"))
        assert "unique name" in _diagnostic_fix_suggestion(MockDiag("duplicate-declaration"))
        assert "type" in _diagnostic_fix_suggestion(MockDiag("unknown-type")).lower()

    def test_diagnostic_fix_suggestion_fallback(self):
        class MockDiag:
            def __init__(self, code, message):
                self.code = code
                self.message = message
                self.line = 1
                self.hint = ""

        result = _diagnostic_fix_suggestion(MockDiag("unknown-code", "parse error at line 5"))
        assert "syntax" in result.lower()

    def test_diagnostic_fix_suggestion_empty(self):
        class MockDiag:
            def __init__(self):
                self.code = ""
                self.message = ""
                self.line = 0
                self.hint = ""

        result = _diagnostic_fix_suggestion(MockDiag())
        assert "axon syntax" in result.lower()
