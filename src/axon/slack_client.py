"""Slack client for AXON tool dispatch.

Provides ``slack.send_message``, ``slack.list_channels``, ``slack.get_channel_history``,
``slack.create_channel``, ``slack.archive_channel``, ``slack.set_topic``,
``slack.invite_user``, and ``slack.search_messages`` builtins that AXON
``tool`` bodies can call directly.

Uses Python's standard-library ``urllib`` so that compiler-core tests remain
free of external dependencies.  Real API calls require ``SLACK_BOT_TOKEN`` in
the environment (a ``xoxb-`` prefixed token from Slack's API management).
"""

from __future__ import annotations

import json as _json
import os
import urllib.error
import urllib.request
from typing import Any


class SlackError(Exception):
    """Raised when a Slack API call fails."""

    def __init__(self, error: str, status: int = 0) -> None:
        self.error = error
        self.status = status
        super().__init__(f"Slack API error: {error}")


class SlackClient:
    """Slack Web API client for AXON tool bodies.

    All methods accept simple AXON-style arguments (strings, ints, dicts) and
    return plain Python values (dicts/lists) so the evaluator can use them
    directly.

    Authentication is via the ``SLACK_BOT_TOKEN`` environment variable.
    """

    BASE_URL = "https://slack.com/api"

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self._token = token or os.environ.get("SLACK_BOT_TOKEN")
        self._base_url = base_url or self.BASE_URL

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json; charset=utf-8",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}/{endpoint}"
        payload: bytes | None = None
        if data is not None:
            payload = _json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers=self._headers(),
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset)
                result = _json.loads(body)
                if not result.get("ok", False):
                    raise SlackError(result.get("error", "unknown_error"))
                return result
        except urllib.error.HTTPError as e:
            charset = e.headers.get_content_charset() or "utf-8" if e.headers else "utf-8"
            try:
                error_body = e.read().decode(charset)
                error_msg = _json.loads(error_body).get("error", error_body)
            except Exception:
                error_msg = str(e)
            raise SlackError(error_msg, status=e.code)

    # ── Messaging ───────────────────────────────────────────────────────────

    def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a channel.

        Args:
            channel: Channel ID or name (e.g., 'C123456' or '#general').
            thread_ts: Optional timestamp of the parent message to reply in a thread.
            blocks: Optional Slack Block Kit blocks for rich formatting.
        """
        data: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            data["thread_ts"] = thread_ts
        if blocks:
            data["blocks"] = blocks
        return self._request("POST", "chat.postMessage", data=data)

    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
    ) -> dict[str, Any]:
        """Update an existing message."""
        return self._request("POST", "chat.update", data={
            "channel": channel,
            "ts": ts,
            "text": text,
        })

    def delete_message(self, channel: str, ts: str) -> dict[str, Any]:
        """Delete a message."""
        return self._request("POST", "chat.delete", data={
            "channel": channel,
            "ts": ts,
        })

    # ── Channels ────────────────────────────────────────────────────────────

    def list_channels(
        self,
        types: str = "public_channel,private_channel",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List channels in the workspace.

        Args:
            types: Comma-separated channel types to include.
            limit: Maximum number of channels to return (1-999).
        """
        data = {"types": types, "limit": min(limit, 999)}
        result = self._request("POST", "conversations.list", data=data)
        return result.get("channels", [])

    def get_channel_history(
        self,
        channel: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent messages from a channel.

        Args:
            channel: Channel ID.
            limit: Number of messages to fetch (1-1000).
        """
        data = {"channel": channel, "limit": min(limit, 1000)}
        result = self._request("POST", "conversations.history", data=data)
        return result.get("messages", [])

    def create_channel(
        self,
        name: str,
        is_private: bool = False,
    ) -> dict[str, Any]:
        """Create a new channel.

        Args:
            name: Channel name (lowercase, no spaces).
            is_private: Whether the channel is private.
        """
        return self._request("POST", "conversations.create", data={
            "name": name,
            "is_private": is_private,
        })

    def archive_channel(self, channel: str) -> dict[str, Any]:
        """Archive a channel."""
        return self._request("POST", "conversations.archive", data={
            "channel": channel,
        })

    def set_topic(self, channel: str, topic: str) -> dict[str, Any]:
        """Set the topic of a channel."""
        return self._request("POST", "conversations.setTopic", data={
            "channel": channel,
            "topic": topic,
        })

    def invite_user(self, channel: str, users: str) -> dict[str, Any]:
        """Invite one or more users to a channel.

        Args:
            channel: Channel ID.
            users: Comma-separated user IDs.
        """
        return self._request("POST", "conversations.invite", data={
            "channel": channel,
            "users": users,
        })

    # ── Search ──────────────────────────────────────────────────────────────

    def search_messages(
        self,
        query: str,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for messages matching a query.

        Args:
            query: Search query (supports Slack search operators).
            count: Number of results (1-100).
        """
        data = {"query": query, "count": min(count, 100)}
        result = self._request("POST", "search.messages", data=data)
        return result.get("messages", {}).get("matches", [])


def slack_builtins(token: str | None = None) -> dict[str, Any]:
    """Return the ``slack`` builtin to inject into tool scopes."""
    return {"slack": SlackClient(token=token)}
