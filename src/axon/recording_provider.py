"""Recording/replay provider wrapper for AXON integration tests.

Wraps a real provider plugin and records interactions to a JSON cassette.
During replay mode no network calls are made — the cassette provides
pre-recorded responses.  This keeps CI free of API keys.

Usage::

    # Record (requires API key):
    real = OpenAIProvider()
    rec = RecordingProvider(real, "cassettes/openai_hello.json", mode=RecordMode.RECORD)
    rec.call(prompt="hello", model="gpt-4", max_tokens=10)

    # Replay (no API key):
    rec = RecordingProvider(real, "cassettes/openai_hello.json", mode=RecordMode.REPLAY)
    rec.call(prompt="hello", model="gpt-4", max_tokens=10)  # returns recorded text
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterator

from result import Result, Ok, Err

from axon.provider_plugin import (
    ProviderPlugin,
    ProviderConfig,
    ProviderError,
    ProviderErrorKind,
)


class RecordMode(Enum):
    """Cassette operating mode."""

    RECORD = "record"  # Always call real provider, overwrite cassette
    REPLAY = "replay"  # Only replay from cassette, never call real provider
    AUTO = "auto"  # Replay if match exists, otherwise record


@dataclass
class CassetteRequest:
    """Serializable request key."""

    provider: str
    method: str  # "call" or "call_stream"
    model: str
    prompt: str
    max_tokens: int
    temperature: float


@dataclass
class CassetteResponse:
    """Serializable response entry."""

    ok: bool
    text: str | None = None
    chunks: list[str] | None = None
    error_kind: str | None = None
    error_message: str | None = None


@dataclass
class CassetteEntry:
    """One recorded interaction."""

    request: dict[str, Any]
    response: dict[str, Any]


class CassetteStore:
    """JSON cassette loader / saver."""

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = str(path)
        self._entries: list[CassetteEntry] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._entries = [CassetteEntry(**item) for item in raw]
        else:
            self._entries = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                [asdict(entry) for entry in self._entries],
                f,
                indent=2,
                ensure_ascii=False,
            )

    def find(self, req: CassetteRequest) -> CassetteResponse | None:
        """Return a matching response or None."""
        needle = asdict(req)
        for entry in self._entries:
            if entry.request == needle:
                return CassetteResponse(**entry.response)
        return None

    def append(self, req: CassetteRequest, resp: CassetteResponse) -> None:
        """Append a new entry and persist."""
        self._entries.append(CassetteEntry(request=asdict(req), response=asdict(resp)))
        self._save()

    def clear(self) -> None:
        """Clear all entries and persist empty cassette."""
        self._entries = []
        self._save()


class RecordingProvider(ProviderPlugin):
    """Wraps a real provider to record/replay interactions from a cassette."""

    def __init__(
        self,
        wrapped: ProviderPlugin,
        cassette_path: str | os.PathLike,
        mode: RecordMode = RecordMode.AUTO,
    ) -> None:
        self._wrapped = wrapped
        self._store = CassetteStore(cassette_path)
        self._mode = mode
        self._config = ProviderConfig(
            name=f"recording:{wrapped.name()}",
            api_key_env_var="",
            timeout_seconds=wrapped.config().timeout_seconds,
            max_retries=0,
        )

    def name(self) -> str:
        return self._wrapped.name()

    def config(self) -> ProviderConfig:
        return self._config

    def _make_request(
        self,
        method: str,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> CassetteRequest:
        return CassetteRequest(
            provider=self._wrapped.name(),
            method=method,
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def call(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Result[str, ProviderError]:
        req = self._make_request("call", prompt, model, max_tokens, temperature)
        cached = self._store.find(req)

        if cached is not None:
            if cached.ok:
                return Ok(cached.text or "")
            return Err(
                ProviderError(
                    kind=ProviderErrorKind(cached.error_kind or "unknown"),
                    message=cached.error_message or "unknown",
                    retryable=False,
                )
            )

        if self._mode == RecordMode.REPLAY:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message=f"Cassette miss in REPLAY mode: {req}",
                    retryable=False,
                )
            )

        # Record
        result = self._wrapped.call(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )

        if isinstance(result, Ok):
            resp = CassetteResponse(ok=True, text=result.ok_value)
        else:
            err = result.err_value
            resp = CassetteResponse(
                ok=False,
                error_kind=err.kind.value,
                error_message=err.message,
            )
        self._store.append(req, resp)
        return result

    def call_stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> Iterator[Result[str, ProviderError]]:
        req = self._make_request("call_stream", prompt, model, max_tokens, temperature)
        cached = self._store.find(req)

        if cached is not None:
            if cached.ok:
                for chunk in cached.chunks or []:
                    yield Ok(chunk)
                return
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind(cached.error_kind or "unknown"),
                    message=cached.error_message or "unknown",
                    retryable=False,
                )
            )
            return

        if self._mode == RecordMode.REPLAY:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message=f"Cassette miss in REPLAY mode: {req}",
                    retryable=False,
                )
            )
            return

        # Record
        chunks: list[str] = []
        for chunk in self._wrapped.call_stream(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            if isinstance(chunk, Ok):
                chunks.append(chunk.ok_value)
            yield chunk

        # Persist after stream completes
        resp = CassetteResponse(ok=True, chunks=chunks)
        self._store.append(req, resp)

    def supports_streaming(self) -> bool:
        return self._wrapped.supports_streaming()
