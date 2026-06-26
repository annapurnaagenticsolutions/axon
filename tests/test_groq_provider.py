"""Tests for AXON Groq provider plugin."""

from unittest.mock import MagicMock, patch
from result import Ok, Err

from axon.providers.groq_provider import GroqProvider
from axon.provider_plugin import ProviderError, ProviderErrorKind


def test_groq_provider_name():
    p = GroqProvider()
    assert p.name() == "groq"


def test_groq_provider_config():
    p = GroqProvider()
    config = p.config()
    assert config.name == "groq"
    assert config.api_key_env_var == "GROQ_API_KEY"
    assert config.base_url == "https://api.groq.com/openai/v1"
    assert config.timeout_seconds == 120


def test_groq_provider_call_success():
    """Mock a successful Groq call."""
    p = GroqProvider()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello from Groq"

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            res = p.call(prompt="Say hi", model="llama-3.3-70b-versatile", max_tokens=10)

    assert isinstance(res, Ok)
    assert res.ok_value == "Hello from Groq"
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "llama-3.3-70b-versatile"


def test_groq_provider_call_auth_error():
    """Mock an authentication error from Groq."""
    import openai

    p = GroqProvider()

    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.request = mock_request
    mock_response.status_code = 401

    auth_error = openai.AuthenticationError(
        message="Invalid key",
        response=mock_response,
        body=None,
    )

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = auth_error
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GROQ_API_KEY": "bad-key"}):
            res = p.call(prompt="Say hi", model="llama-3.3-70b-versatile", max_tokens=10)

    assert isinstance(res, Err)
    assert res.err_value.kind == ProviderErrorKind.AUTHENTICATION


def test_groq_provider_config_api_key_missing(monkeypatch):
    """When GROQ_API_KEY is not set, get_api_key returns error."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    p = GroqProvider()
    config = p.config()
    res = config.get_api_key()
    assert isinstance(res, Err)
    assert res.err_value.kind == ProviderErrorKind.AUTHENTICATION


def test_groq_provider_call_stream_success():
    """Mock a successful streaming Groq call."""
    p = GroqProvider()

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta.content = "Hello "

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta.content = "world!"

    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk1, mock_chunk2]))

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            chunks = list(p.call_stream(prompt="Say hi", model="llama-3.3-70b-versatile", max_tokens=10))

    assert len(chunks) == 2
    assert all(isinstance(c, Ok) for c in chunks)
    assert chunks[0].ok_value == "Hello "
    assert chunks[1].ok_value == "world!"


def test_groq_provider_uses_groq_base_url():
    """Verify the provider creates OpenAI client with Groq base URL."""
    p = GroqProvider()

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            p.call(prompt="test", model="llama-3.3-70b-versatile", max_tokens=10)

    call_args = mock_client_class.call_args
    assert call_args.kwargs["base_url"] == "https://api.groq.com/openai/v1"
