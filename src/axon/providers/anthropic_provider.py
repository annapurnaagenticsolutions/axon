"""Anthropic provider plugin for AXON Phase 2 runtime.

This module provides a real Anthropic provider implementation. It requires
the ``anthropic`` package to be installed (``pip install anthropic``).
"""

from __future__ import annotations

from typing import AsyncIterator, Iterator, Optional
from result import Result, Ok, Err

from axon.provider_plugin import (
    ProviderPlugin,
    ProviderConfig,
    ProviderError,
    ProviderErrorKind,
)


class AnthropicProvider(ProviderPlugin):
    """Real Anthropic provider for AXON runtime.

    Requires ``anthropic`` package:
        pip install anthropic

    API key is loaded from the ``ANTHROPIC_API_KEY`` environment variable.
    """

    def __init__(self) -> None:
        self._config = ProviderConfig(
            name="anthropic",
            api_key_env_var="ANTHROPIC_API_KEY",
            base_url=None,
            timeout_seconds=120,
            max_retries=3,
        )

    def name(self) -> str:
        """Provider name."""
        return "anthropic"

    def config(self) -> ProviderConfig:
        """Get provider configuration."""
        return self._config

    def call(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
        stream: bool = False,
        response_format: Optional[str] = None,
    ) -> Result[str, ProviderError]:
        """Invoke Anthropic messages API."""
        try:
            import anthropic
        except ImportError:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message="anthropic package not installed. Run: pip install anthropic",
                    retryable=False,
                )
            )

        # Load API key
        config = self.config()
        api_key_res = config.get_api_key()
        if isinstance(api_key_res, Err):
            return api_key_res
        api_key = api_key_res.ok_value

        client = anthropic.Anthropic(api_key=api_key, base_url=config.base_url)

        try:
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format:
                # Anthropic uses tool-use for structured output
                kwargs["tools"] = [{
                    "name": "structured_output",
                    "description": "Return structured output",
                    "input_schema": {"type": "object", "properties": {"result": {"type": "string"}}},
                }]
                kwargs["tool_choice"] = {"type": "tool", "name": "structured_output"}
            response = client.messages.create(**kwargs)
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            return Ok(content)

        except anthropic.AuthenticationError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    message=str(e),
                    status_code=e.status_code if hasattr(e, "status_code") else None,
                    retryable=False,
                )
            )
        except anthropic.RateLimitError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.RATE_LIMIT,
                    message=str(e),
                    status_code=e.status_code if hasattr(e, "status_code") else None,
                    retryable=True,
                )
            )
        except anthropic.APITimeoutError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.TIMEOUT,
                    message=str(e),
                    retryable=True,
                )
            )
        except anthropic.APIError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.SERVER_ERROR,
                    message=str(e),
                    status_code=e.status_code if hasattr(e, "status_code") else None,
                    retryable=True,
                )
            )
        except Exception as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.UNKNOWN,
                    message=str(e),
                    retryable=False,
                )
            )

    def call_stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> Iterator[Result[str, ProviderError]]:
        """Invoke Anthropic with streaming."""
        try:
            import anthropic
        except ImportError:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message="anthropic package not installed. Run: pip install anthropic",
                    retryable=False,
                )
            )
            return

        config = self.config()
        api_key_res = config.get_api_key()
        if isinstance(api_key_res, Err):
            yield api_key_res
            return
        api_key = api_key_res.ok_value

        client = anthropic.Anthropic(api_key=api_key, base_url=config.base_url)

        try:
            with client.messages.stream(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield Ok(text)
        except Exception as e:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.UNKNOWN,
                    message=str(e),
                    retryable=False,
                )
            )

    async def call_stream_async(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> AsyncIterator[Result[str, ProviderError]]:
        """Invoke Anthropic with async streaming."""
        try:
            import anthropic
        except ImportError:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message="anthropic package not installed. Run: pip install anthropic",
                    retryable=False,
                )
            )
            return

        config = self.config()
        api_key_res = config.get_api_key()
        if isinstance(api_key_res, Err):
            yield api_key_res
            return
        api_key = api_key_res.ok_value

        client = anthropic.AsyncAnthropic(api_key=api_key, base_url=config.base_url)

        try:
            async with client.messages.stream(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            ) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield Ok(text)
        except Exception as e:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.UNKNOWN,
                    message=str(e),
                    retryable=False,
                )
            )
