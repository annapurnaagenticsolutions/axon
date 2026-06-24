"""Tests for AXON OpenAI provider plugin."""

from unittest.mock import MagicMock, patch
from result import Ok, Err

from axon.providers.openai_provider import OpenAIProvider
from axon.provider_plugin import ProviderError, ProviderErrorKind


def test_openai_provider_name():
    p = OpenAIProvider()
    assert p.name() == "openai"


def test_openai_provider_config():
    p = OpenAIProvider()
    config = p.config()
    assert config.name == "openai"
    assert config.api_key_env_var == "OPENAI_API_KEY"
    assert config.timeout_seconds == 120


def test_openai_provider_call_success():
    """Mock a successful OpenAI call."""
    p = OpenAIProvider()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello from AI"

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            res = p.call(prompt="Say hi", model="gpt-4o", max_tokens=10)

    assert isinstance(res, Ok)
    assert res.ok_value == "Hello from AI"
    mock_client.chat.completions.create.assert_called_once()


def test_openai_provider_call_auth_error():
    """Mock an authentication error from OpenAI."""
    import openai

    p = OpenAIProvider()

    # Build a mock response with a request attribute
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

        with patch.dict("os.environ", {"OPENAI_API_KEY": "bad-key"}):
            res = p.call(prompt="Say hi", model="gpt-4o", max_tokens=10)

    assert isinstance(res, Err)
    assert res.err_value.kind == ProviderErrorKind.AUTHENTICATION


def test_openai_provider_config_api_key_missing(monkeypatch):
    """When OPENAI_API_KEY is not set, get_api_key returns error."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAIProvider()
    config = p.config()
    res = config.get_api_key()
    assert isinstance(res, Err)
    assert res.err_value.kind == ProviderErrorKind.AUTHENTICATION
