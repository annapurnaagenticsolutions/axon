"""Tests for the ``axon run`` CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from axon.cli import run_file


def test_cli_run_simple_return(tmp_path: Path):
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")
    code, output = run_file(p, args={"q": "World"})
    assert code == 0
    assert output == "World"


def test_cli_run_act_dispatch(tmp_path: Path):
    source = '''tool Greet(name: Str) -> Str {
        "Hello, {name}!"
    }

    agent Bot {
        model: @mock/model
        tools: [Greet]
        fn run(q: Str) -> Str {
            act Greet(name: q)
        }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")
    code, output = run_file(p, args={"q": "CLI"})
    assert code == 0
    assert output == "Hello, CLI!"


def test_cli_run_trace_output(tmp_path: Path):
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"
    code, output = run_file(p, args={"q": "hi"}, trace_output=trace_path)
    assert code == 0
    assert trace_path.exists()
    lines = trace_path.read_text().strip().split("\n")
    assert len(lines) == 4  # agent_start, method_start, method_return, agent_end


def test_cli_run_json_output(tmp_path: Path):
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")
    code, output = run_file(p, args={"q": "test"}, json_output=True)
    assert code == 0
    assert '"output": "test"' in output


def test_cli_run_missing_agent(tmp_path: Path):
    source = '''tool Greet(name: Str) -> Str { "hi" }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")
    code, output = run_file(p)
    assert code == 1
    assert "No agent declaration" in output


def test_cli_run_missing_argument(tmp_path: Path):
    source = '''agent Bot {
        model: @mock/model
        tools: []
        fn run(q: Str) -> Str { q }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")
    code, output = run_file(p, args={})
    assert code == 1
    assert "Missing argument" in output


def test_cli_run_real_provider_mocked(tmp_path: Path, monkeypatch):
    """End-to-end test for --no-mock path with a mocked OpenAI client."""
    source = '''agent Bot {
        model: @openai/gpt-4
        tools: []
        fn run(q: Str) -> Str {
            model.complete("Say hello to " + q)
        }
    }'''
    p = tmp_path / "test.ax"
    p.write_text(source, encoding="utf-8")

    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello, AI!"

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            code, output = run_file(p, args={"q": "AI"}, mock=False)

    assert code == 0
    assert "Hello, AI!" in output
    mock_client.chat.completions.create.assert_called_once()
