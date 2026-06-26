"""Tests for the GitHub tool module — no real API calls.

Uses ``unittest.mock`` to patch ``urllib.request.urlopen`` so the full
``GitHubClient`` code paths are exercised without network access.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from axon.github_client import GitHubClient, GitHubError, github_builtins


# ── Helpers ─────────────────────────────────────────────────────────────────


def _mock_response(data, status: int = 200) -> MagicMock:
    """Create a mock HTTP response object that supports context manager."""
    body = json.dumps(data).encode("utf-8") if data is not None else b""
    resp = MagicMock()
    resp.read.return_value = body
    resp.headers.get_content_charset.return_value = "utf-8"
    resp.status = status
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_error(status: int, message: str = "Not Found") -> urllib.error.HTTPError:
    """Create a mock HTTPError."""
    body = json.dumps({"message": message}).encode("utf-8")
    return urllib.error.HTTPError(
        url="https://api.github.com/test",
        code=status,
        msg=message,
        hdrs=MagicMock(),
        fp=io.BytesIO(body),
    )


# ── Issues ──────────────────────────────────────────────────────────────────


class TestListIssues:
    def test_list_issues_returns_list(self):
        issues = [
            {"number": 1, "title": "Bug", "pull_request": {}},
            {"number": 2, "title": "Real issue"},
        ]
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response(issues)):
            result = client.list_issues("owner/repo", state="open", limit=30)
        assert len(result) == 1
        assert result[0]["number"] == 2

    def test_list_issues_state_param(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response([])) as mock_urlopen:
            client.list_issues("owner/repo", state="closed", limit=10)
            req = mock_urlopen.call_args[0][0]
            assert "state=closed" in req.full_url
            assert "per_page=10" in req.full_url

    def test_list_issues_limit_capped_at_100(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response([])) as mock_urlopen:
            client.list_issues("owner/repo", limit=500)
            req = mock_urlopen.call_args[0][0]
            assert "per_page=100" in req.full_url


class TestGetIssue:
    def test_get_issue_returns_dict(self):
        issue = {"number": 42, "title": "Test issue", "state": "open"}
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response(issue)):
            result = client.get_issue("owner/repo", 42)
        assert result["number"] == 42
        assert result["title"] == "Test issue"


class TestCreateIssue:
    def test_create_issue_sends_post(self):
        created = {"number": 10, "title": "New bug"}
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response(created)) as mock_urlopen:
            result = client.create_issue("owner/repo", title="New bug", body="Description", labels=["bug"])
            req = mock_urlopen.call_args[0][0]
            assert req.method == "POST"
            payload = json.loads(req.data.decode())
            assert payload["title"] == "New bug"
            assert payload["labels"] == ["bug"]
        assert result["number"] == 10


class TestAddLabel:
    def test_add_label_sends_labels(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response([{"name": "bug"}])) as mock_urlopen:
            client.add_label("owner/repo", 5, "bug")
            req = mock_urlopen.call_args[0][0]
            assert req.method == "POST"
            payload = json.loads(req.data.decode())
            assert payload == {"labels": ["bug"]}


class TestAssignIssue:
    def test_assign_issue_sends_assignees(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response({"assignees": [{"login": "alice"}]})) as mock_urlopen:
            client.assign_issue("owner/repo", 5, "alice")
            req = mock_urlopen.call_args[0][0]
            payload = json.loads(req.data.decode())
            assert payload == {"assignees": ["alice"]}


class TestCloseIssue:
    def test_close_issue_sends_patch(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response({"state": "closed"})) as mock_urlopen:
            client.close_issue("owner/repo", 5)
            req = mock_urlopen.call_args[0][0]
            assert req.method == "PATCH"
            payload = json.loads(req.data.decode())
            assert payload == {"state": "closed"}


class TestCreateComment:
    def test_create_comment_sends_body(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response({"id": 1, "body": "Nice"})) as mock_urlopen:
            client.create_comment("owner/repo", 5, "Nice work!")
            req = mock_urlopen.call_args[0][0]
            payload = json.loads(req.data.decode())
            assert payload == {"body": "Nice work!"}


# ── Pull Requests ───────────────────────────────────────────────────────────


class TestListPRs:
    def test_list_prs_returns_list(self):
        prs = [{"number": 1, "title": "Fix bug"}, {"number": 2, "title": "Add feature"}]
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response(prs)):
            result = client.list_prs("owner/repo", state="open", limit=30)
        assert len(result) == 2
        assert result[0]["number"] == 1


class TestGetPR:
    def test_get_pr_returns_dict(self):
        pr = {"number": 7, "title": "Improve docs", "state": "open"}
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response(pr)):
            result = client.get_pr("owner/repo", 7)
        assert result["number"] == 7


class TestMergePR:
    def test_merge_pr_sends_put(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response({"sha": "abc", "merged": True})) as mock_urlopen:
            client.merge_pr("owner/repo", 7, commit_title="Merge #7", merge_method="squash")
            req = mock_urlopen.call_args[0][0]
            assert req.method == "PUT"
            payload = json.loads(req.data.decode())
            assert payload["merge_method"] == "squash"
            assert payload["commit_title"] == "Merge #7"


class TestCreateReview:
    def test_create_review_sends_event(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", return_value=_mock_response({"id": 1})) as mock_urlopen:
            client.create_review("owner/repo", 7, "Looks good!", event="APPROVE")
            req = mock_urlopen.call_args[0][0]
            payload = json.loads(req.data.decode())
            assert payload["event"] == "APPROVE"
            assert payload["body"] == "Looks good!"


# ── Auth & Error Handling ───────────────────────────────────────────────────


class TestAuth:
    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        client = GitHubClient()
        assert client._token == "env-token"

    def test_token_override(self):
        client = GitHubClient(token="explicit")
        assert client._token == "explicit"

    def test_no_token_unauthenticated(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        client = GitHubClient()
        assert client._token is None
        headers = client._headers()
        assert "Authorization" not in headers

    def test_token_in_headers(self):
        client = GitHubClient(token="my-token")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer my-token"


class TestErrorHandling:
    def test_http_error_raises_github_error(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", side_effect=_mock_error(404, "Not Found")):
            with pytest.raises(GitHubError) as exc_info:
                client.get_issue("owner/repo", 999)
            assert exc_info.value.status == 404
            assert "Not Found" in exc_info.value.message

    def test_http_error_403_raises_github_error(self):
        client = GitHubClient(token="fake-token")
        with patch("urllib.request.urlopen", side_effect=_mock_error(403, "Rate limit exceeded")):
            with pytest.raises(GitHubError) as exc_info:
                client.list_issues("owner/repo")
            assert exc_info.value.status == 403


# ── Builtins ────────────────────────────────────────────────────────────────


class TestBuiltins:
    def test_github_builtins_returns_client(self):
        builtins = github_builtins(token="test-token")
        assert "github" in builtins
        assert isinstance(builtins["github"], GitHubClient)
        assert builtins["github"]._token == "test-token"

    def test_github_builtins_no_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        builtins = github_builtins()
        assert "github" in builtins
        assert builtins["github"]._token is None
