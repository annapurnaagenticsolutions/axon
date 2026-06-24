"""Integration tests using recorded provider cassettes (no live API calls)."""

from pathlib import Path

from result import Ok, Err

from axon.recording_provider import RecordingProvider, RecordMode
from axon.providers.openai_provider import OpenAIProvider
from axon.providers.anthropic_provider import AnthropicProvider
from axon.provider_plugin import ProviderErrorKind


def _cassette(name: str) -> str:
    return str(Path(__file__).parent / "cassettes" / name)


def test_openai_replay_call_from_cassette() -> None:
    """Replay a pre-recorded OpenAI call without network."""
    wrapped = OpenAIProvider()
    rec = RecordingProvider(
        wrapped,
        _cassette("openai_hello.json"),
        mode=RecordMode.REPLAY,
    )
    result = rec.call(prompt="Say hello in one word", model="gpt-4", max_tokens=10)
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello!"


def test_openai_replay_stream_from_cassette() -> None:
    """Replay a pre-recorded OpenAI stream without network."""
    wrapped = OpenAIProvider()
    rec = RecordingProvider(
        wrapped,
        _cassette("openai_hello.json"),
        mode=RecordMode.REPLAY,
    )
    chunks = list(rec.call_stream(prompt="Count to three", model="gpt-4", max_tokens=20))
    assert all(isinstance(c, Ok) for c in chunks)
    text = "".join(c.ok_value for c in chunks)
    assert text == "One, two, three"


def test_anthropic_replay_call_from_cassette() -> None:
    """Replay a pre-recorded Anthropic call without network."""
    wrapped = AnthropicProvider()
    rec = RecordingProvider(
        wrapped,
        _cassette("anthropic_hello.json"),
        mode=RecordMode.REPLAY,
    )
    result = rec.call(prompt="Say hello in one word", model="claude-4", max_tokens=10)
    assert isinstance(result, Ok)
    assert result.ok_value == "Hello!"


def test_anthropic_replay_error_from_cassette() -> None:
    """Replay a pre-recorded Anthropic error (rate limit) without network."""
    wrapped = AnthropicProvider()
    rec = RecordingProvider(
        wrapped,
        _cassette("anthropic_hello.json"),
        mode=RecordMode.REPLAY,
    )
    result = rec.call(prompt="Trigger rate limit error", model="claude-4", max_tokens=10)
    assert isinstance(result, Err)
    assert result.err_value.kind == ProviderErrorKind.RATE_LIMIT
    assert "Rate limit exceeded" in result.err_value.message


def test_replay_mode_miss_returns_error() -> None:
    """A cassette miss in REPLAY mode returns an error instead of making a real call."""
    wrapped = OpenAIProvider()
    rec = RecordingProvider(
        wrapped,
        _cassette("openai_hello.json"),
        mode=RecordMode.REPLAY,
    )
    result = rec.call(prompt="Unseen prompt", model="unknown-model", max_tokens=10)
    assert isinstance(result, Err)
    assert "Cassette miss in REPLAY mode" in result.err_value.message
