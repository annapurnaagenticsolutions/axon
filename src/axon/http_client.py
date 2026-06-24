"""HTTP client for AXON tool dispatch.

Provides ``http.get``, ``http.post``, ``http.put``, and ``http.delete``
builtins that AXON ``tool`` bodies can call directly.  Uses only the
Python standard library so that compiler-core tests remain free of
external network dependencies; real HTTP calls are only made when the
runtime is executing via ``axon run``.
"""

from __future__ import annotations

import json as _json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class EnvProxy:
    """Read-only proxy to ``os.environ`` accessible as ``env.VAR_NAME``."""

    def __getattr__(self, name: str) -> str | None:
        return os.environ.get(name)

    def __getitem__(self, name: str) -> str | None:
        return os.environ.get(name)

    def get(self, name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, default)


@dataclass(frozen=True)
class HttpResponse:
    """Lightweight HTTP response wrapper."""

    status: int
    body: str
    headers: dict[str, str]

    def json(self) -> Any:
        """Parse body as JSON."""
        return _json.loads(self.body)


class HttpClient:
    """Standard-library HTTP client for AXON tool bodies.

    Methods accept AXON-style arguments (strings, dicts) and return
    plain Python values so the evaluator can use them directly.
    """

    def _request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        req_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        payload: bytes | None = None
        if data is not None:
            payload = _json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers=req_headers,
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            try:
                charset = resp.headers.get_content_charset() or "utf-8"
            except AttributeError:
                charset = "utf-8"
            raw_body = resp.read().decode(charset)
            response_headers = {}
            try:
                response_headers = dict(resp.headers.items())
            except Exception:
                pass
            return HttpResponse(status=getattr(resp, "status", 200), body=raw_body, headers=response_headers)

    def get(self, url: str, headers: dict[str, str] | None = None) -> Any:
        """Perform an HTTP GET and return the response body (parsed JSON if possible)."""
        resp = self._request("GET", url, headers=headers)
        return _try_parse_json(resp.body)

    def post(self, url: str, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        """Perform an HTTP POST and return the response body."""
        resp = self._request("POST", url, data=data, headers=headers)
        return _try_parse_json(resp.body)

    def put(self, url: str, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        """Perform an HTTP PUT and return the response body."""
        resp = self._request("PUT", url, data=data, headers=headers)
        return _try_parse_json(resp.body)

    def delete(self, url: str, headers: dict[str, str] | None = None) -> Any:
        """Perform an HTTP DELETE and return the response body."""
        resp = self._request("DELETE", url, headers=headers)
        return _try_parse_json(resp.body)


def _try_parse_json(text: str) -> Any:
    """Return parsed JSON if valid, otherwise the raw string."""
    try:
        return _json.loads(text)
    except Exception:
        return text


def http_builtins() -> dict[str, Any]:
    """Return the ``http`` and ``env`` builtins to inject into tool scopes."""
    return {"http": HttpClient(), "env": EnvProxy()}
