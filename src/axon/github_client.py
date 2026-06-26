"""GitHub client for AXON tool dispatch.

Provides ``github.list_issues``, ``github.get_issue``, ``github.create_issue``,
``github.add_label``, ``github.assign_issue``, ``github.close_issue``,
``github.list_prs``, ``github.get_pr``, ``github.merge_pr``,
``github.create_comment``, and ``github.create_review`` builtins that AXON
``tool`` bodies can call directly.

Uses Python's standard-library ``urllib`` so that compiler-core tests remain
free of external dependencies.  Real API calls require ``GITHUB_TOKEN`` in the
environment.
"""

from __future__ import annotations

import json as _json
import os
import urllib.error
import urllib.request
from typing import Any


class GitHubError(Exception):
    """Raised when a GitHub API call fails."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"GitHub API error {status}: {message}")


class GitHubClient:
    """GitHub REST API v3 client for AXON tool bodies.

    All methods accept simple AXON-style arguments (strings, ints, dicts) and
    return plain Python values (dicts/lists) so the evaluator can use them
    directly.

    Authentication is via the ``GITHUB_TOKEN`` environment variable.  If not
    set, unauthenticated requests are used (subject to GitHub's rate limits).
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._base_url = base_url or self.BASE_URL

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
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
                if not body:
                    return None
                return _json.loads(body)
        except urllib.error.HTTPError as e:
            charset = e.headers.get_content_charset() or "utf-8" if e.headers else "utf-8"
            try:
                error_body = e.read().decode(charset)
                error_msg = _json.loads(error_body).get("message", error_body)
            except Exception:
                error_msg = str(e)
            raise GitHubError(e.code, error_msg)

    @staticmethod
    def _repo_path(repo: str) -> str:
        """Convert 'owner/repo' to '/repos/owner/repo'."""
        return f"/repos/{repo}"

    # ── Issues ──────────────────────────────────────────────────────────────

    def list_issues(
        self,
        repo: str,
        state: str = "open",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """List issues in a repository.

        Args:
            repo: Repository in 'owner/repo' format.
            state: 'open', 'closed', or 'all'.
            limit: Maximum number of issues to return (1-100).
        """
        path = f"{self._repo_path(repo)}/issues?state={state}&per_page={min(limit, 100)}"
        result = self._request("GET", path)
        # GitHub returns PRs in the issues endpoint too; filter them out
        return [i for i in result if "pull_request" not in i]

    def get_issue(self, repo: str, issue_number: int) -> dict[str, Any]:
        """Get a single issue by number."""
        path = f"{self._repo_path(repo)}/issues/{issue_number}"
        return self._request("GET", path)

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue in a repository."""
        data: dict[str, Any] = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        return self._request("POST", f"{self._repo_path(repo)}/issues", data=data)

    def add_label(self, repo: str, issue_number: int, label: str) -> list[dict[str, Any]]:
        """Add a label to an issue."""
        path = f"{self._repo_path(repo)}/issues/{issue_number}/labels"
        return self._request("POST", path, data={"labels": [label]})

    def assign_issue(self, repo: str, issue_number: int, assignee: str) -> dict[str, Any]:
        """Assign an issue to a user."""
        path = f"{self._repo_path(repo)}/issues/{issue_number}/assignees"
        return self._request("POST", path, data={"assignees": [assignee]})

    def close_issue(self, repo: str, issue_number: int) -> dict[str, Any]:
        """Close an issue."""
        path = f"{self._repo_path(repo)}/issues/{issue_number}"
        return self._request("PATCH", path, data={"state": "closed"})

    def create_comment(self, repo: str, issue_number: int, body: str) -> dict[str, Any]:
        """Create a comment on an issue or PR."""
        path = f"{self._repo_path(repo)}/issues/{issue_number}/comments"
        return self._request("POST", path, data={"body": body})

    # ── Pull Requests ───────────────────────────────────────────────────────

    def list_prs(
        self,
        repo: str,
        state: str = "open",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """List pull requests in a repository.

        Args:
            repo: Repository in 'owner/repo' format.
            state: 'open', 'closed', or 'all'.
            limit: Maximum number of PRs to return (1-100).
        """
        path = f"{self._repo_path(repo)}/pulls?state={state}&per_page={min(limit, 100)}"
        return self._request("GET", path)

    def get_pr(self, repo: str, pr_number: int) -> dict[str, Any]:
        """Get a single pull request by number."""
        path = f"{self._repo_path(repo)}/pulls/{pr_number}"
        return self._request("GET", path)

    def merge_pr(
        self,
        repo: str,
        pr_number: int,
        commit_title: str | None = None,
        merge_method: str = "merge",
    ) -> dict[str, Any]:
        """Merge a pull request.

        Args:
            repo: Repository in 'owner/repo' format.
            pr_number: PR number.
            commit_title: Optional title for the merge commit.
            merge_method: 'merge', 'squash', or 'rebase'.
        """
        path = f"{self._repo_path(repo)}/pulls/{pr_number}/merge"
        data: dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            data["commit_title"] = commit_title
        return self._request("PUT", path, data=data)

    def create_review(
        self,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
    ) -> dict[str, Any]:
        """Create a review on a pull request.

        Args:
            repo: Repository in 'owner/repo' format.
            pr_number: PR number.
            body: Review comment body.
            event: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'.
        """
        path = f"{self._repo_path(repo)}/pulls/{pr_number}/reviews"
        return self._request("POST", path, data={"body": body, "event": event})


def github_builtins(token: str | None = None) -> dict[str, Any]:
    """Return the ``github`` builtin to inject into tool scopes."""
    return {"github": GitHubClient(token=token)}
