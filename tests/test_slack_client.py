"""Tests for the Slack tool module — no real API calls.

Uses ``unittest.mock`` to patch ``urllib.request.urlopen`` so the full
``SlackClient`` code paths are exercised without network access.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from axon.slack_client import SlackClient, SlackError, slack_builtins


# ── Helpers ─────────────────────────────────────────────────────────────────


def _mock_response(data, status: int = 200) -> MagicMock:
    """Create a mock HTTP response that supports context manager."""
    body = json.dumps(data).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.headers.get_content_charset.return_value = "utf-8"
    resp.status = status
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_error(status: int, error: str = "invalid_auth") -> urllib.error.HTTPError:
    """Create a mock HTTPError."""
    body = json.dumps({"ok": False, "error": error}).encode("utf-8")
    return urllib.error.HTTPError(
        url="https://slack.com/api/test",
        code=status,
        msg=error,
        hdrs=MagicMock(),
        fp=io.BytesIO(body),
    )


# ── Messaging ───────────────────────────────────────────────────────────────


class TestSendMessage:
    def test_send_message_returns_response(self):
        resp_data = {"ok": True, "channel": "C123", "ts": "1234567890.123456", "message": {"text": "Hello"}}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            result = client.send_message("C123", "Hello!")
            req = mock_urlopen.call_args[0][0]
            assert req.method == "POST"
            payload = json.loads(req.data.decode())
            assert payload["channel"] == "C123"
            assert payload["text"] == "Hello!"
        assert result["ok"] is True
        assert result["ts"] == "1234567890.123456"

    def test_send_message_with_thread(self):
        resp_data = {"ok": True, "channel": "C123", "ts": "123.456", "message": {"text": "Reply"}}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.send_message("C123", "Reply!", thread_ts="123.000")
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["thread_ts"] == "123.000"

    def test_send_message_with_blocks(self):
        resp_data = {"ok": True, "channel": "C123", "ts": "123.456", "message": {}}
        client = SlackClient(token="xoxb-fake")
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "*Bold*"}}]
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.send_message("C123", "text", blocks=blocks)
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["blocks"] == blocks


class TestUpdateMessage:
    def test_update_message_sends_correct_payload(self):
        resp_data = {"ok": True, "channel": "C123", "ts": "123.456", "text": "Updated"}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.update_message("C123", "123.456", "Updated text")
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["channel"] == "C123"
            assert payload["ts"] == "123.456"
            assert payload["text"] == "Updated text"


class TestDeleteMessage:
    def test_delete_message_sends_correct_payload(self):
        resp_data = {"ok": True, "channel": "C123", "ts": "123.456"}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.delete_message("C123", "123.456")
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["channel"] == "C123"
            assert payload["ts"] == "123.456"


# ── Channels ────────────────────────────────────────────────────────────────


class TestListChannels:
    def test_list_channels_returns_list(self):
        channels = [{"id": "C1", "name": "general"}, {"id": "C2", "name": "random"}]
        resp_data = {"ok": True, "channels": channels}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)):
            result = client.list_channels()
        assert len(result) == 2
        assert result[0]["name"] == "general"

    def test_list_channels_limit_capped(self):
        resp_data = {"ok": True, "channels": []}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.list_channels(limit=5000)
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["limit"] == 999


class TestGetChannelHistory:
    def test_get_history_returns_messages(self):
        messages = [{"text": "Hello", "ts": "123.456"}, {"text": "World", "ts": "124.567"}]
        resp_data = {"ok": True, "messages": messages}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)):
            result = client.get_channel_history("C123", limit=50)
        assert len(result) == 2
        assert result[0]["text"] == "Hello"


class TestCreateChannel:
    def test_create_channel_sends_name_and_private(self):
        resp_data = {"ok": True, "channel": {"id": "C999", "name": "new-channel"}}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.create_channel("new-channel", is_private=True)
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["name"] == "new-channel"
            assert payload["is_private"] is True


class TestArchiveChannel:
    def test_archive_channel_sends_channel(self):
        resp_data = {"ok": True}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.archive_channel("C123")
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload == {"channel": "C123"}


class TestSetTopic:
    def test_set_topic_sends_topic(self):
        resp_data = {"ok": True}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.set_topic("C123", "New topic")
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["channel"] == "C123"
            assert payload["topic"] == "New topic"


class TestInviteUser:
    def test_invite_user_sends_users(self):
        resp_data = {"ok": True}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)) as mock_urlopen:
            client.invite_user("C123", "U1,U2")
            payload = json.loads(mock_urlopen.call_args[0][0].data.decode())
            assert payload["channel"] == "C123"
            assert payload["users"] == "U1,U2"


# ── Search ──────────────────────────────────────────────────────────────────


class TestSearchMessages:
    def test_search_returns_matches(self):
        matches = [{"text": "found it", "channel": {"name": "general"}}]
        resp_data = {"ok": True, "messages": {"matches": matches, "total": 1}}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)):
            result = client.search_messages("test query")
        assert len(result) == 1
        assert result[0]["text"] == "found it"


# ── Auth & Error Handling ───────────────────────────────────────────────────


class TestAuth:
    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-env-token")
        client = SlackClient()
        assert client._token == "xoxb-env-token"

    def test_token_override(self):
        client = SlackClient(token="xoxb-explicit")
        assert client._token == "xoxb-explicit"

    def test_no_token_no_auth_header(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        client = SlackClient()
        headers = client._headers()
        assert "Authorization" not in headers

    def test_token_in_headers(self):
        client = SlackClient(token="xoxb-my-token")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer xoxb-my-token"


class TestErrorHandling:
    def test_slack_api_error_raises(self):
        """When Slack returns ok=false, raise SlackError."""
        resp_data = {"ok": False, "error": "channel_not_found"}
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_data)):
            with pytest.raises(SlackError) as exc_info:
                client.send_message("C999", "test")
            assert exc_info.value.error == "channel_not_found"

    def test_http_error_raises_slack_error(self):
        client = SlackClient(token="xoxb-fake")
        with patch("urllib.request.urlopen", side_effect=_mock_error(401, "invalid_auth")):
            with pytest.raises(SlackError) as exc_info:
                client.list_channels()
            assert "invalid_auth" in str(exc_info.value)


# ── Builtins ────────────────────────────────────────────────────────────────


class TestBuiltins:
    def test_slack_builtins_returns_client(self):
        builtins = slack_builtins(token="xoxb-test")
        assert "slack" in builtins
        assert isinstance(builtins["slack"], SlackClient)
        assert builtins["slack"]._token == "xoxb-test"

    def test_slack_builtins_no_token(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        builtins = slack_builtins()
        assert "slack" in builtins
        assert builtins["slack"]._token is None
