"""Fake OpenAI-compatible HTTP server for provider integration testing.

Spins up on a random local port and returns realistic chat completion
responses.  Used by ``test_provider_integration.py`` so the real
``OpenAIProvider`` can be exercised without an actual API key.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class _Handler(BaseHTTPRequestHandler):
    """Minimal OpenAI chat completions endpoint."""

    # Injected by the test harness before server starts
    fail_next: int = 0  # Number of requests to fail with 500
    rate_limit: bool = False

    def log_message(self, format: str, *args: Any) -> None:
        # Silence logs during tests
        pass

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Simulate rate limit
        if _Handler.rate_limit:
            self._send_json(429, {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}})
            return

        # Simulate server failure (for retry testing)
        if _Handler.fail_next > 0:
            _Handler.fail_next -= 1
            self._send_json(500, {"error": {"message": "Internal server error", "type": "internal_error"}})
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": {"message": "Invalid JSON"}})
            return

        model = data.get("model", "gpt-4")
        stream = data.get("stream", False)
        messages = data.get("messages", [])
        prompt = ""
        if messages:
            prompt = messages[-1].get("content", "")

        if stream:
            self._stream_response(prompt, model)
        else:
            self._completion_response(prompt, model)

    def _completion_response(self, prompt: str, model: str) -> None:
        response = {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "created": 1700000000,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"Fake response to: {prompt}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": 5, "total_tokens": 10},
        }
        self._send_json(200, response)

    def _stream_response(self, prompt: str, model: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        chunks = ["Hello, ", "this ", "is ", "a ", "fake ", "stream."]
        for chunk in chunks:
            data = {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "created": 1700000000,
                "model": model,
                "choices": [
                    {"index": 0, "delta": {"content": chunk}, "finish_reason": None}
                ],
            }
            self.wfile.write(f"data: {json.dumps(data)}\n\n".encode("utf-8"))
        # Final chunk
        final = {
            "id": "chatcmpl-fake",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        self.wfile.write(f"data: {json.dumps(final)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


class FakeOpenAIServer:
    """Context-manager friendly fake OpenAI server."""

    def __init__(self) -> None:
        self.server: HTTPServer | None = None
        self.port: int = 0
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"

    def start(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def __enter__(self) -> "FakeOpenAIServer":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
