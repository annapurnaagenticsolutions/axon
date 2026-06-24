"""OpenAI provider plugin for AXON Phase 2 runtime.

This module provides a real OpenAI provider implementation. It requires
the ``openai`` package to be installed (``pip install openai``).
"""

from __future__ import annotations

from typing import AsyncIterator, Iterator
from result import Result, Ok, Err

from axon.provider_plugin import (
    ProviderPlugin,
    ProviderConfig,
    ProviderError,
    ProviderErrorKind,
)


class OpenAIProvider(ProviderPlugin):
    """Real OpenAI provider for AXON runtime.

    Requires ``openai`` package:
        pip install openai

    API key is loaded from the ``OPENAI_API_KEY`` environment variable.
    """

    def __init__(self) -> None:
        self._config = ProviderConfig(
            name="openai",
            api_key_env_var="OPENAI_API_KEY",
            base_url=None,
            timeout_seconds=120,
            max_retries=3,
        )

    def name(self) -> str:
        """Provider name."""
        return "openai"

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
    ) -> Result[str, ProviderError]:
        """Invoke OpenAI chat completions API."""
        try:
            import openai
        except ImportError:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message="openai package not installed. Run: pip install openai",
                    retryable=False,
                )
            )

        # Load API key
        config = self.config()
        api_key_res = config.get_api_key()
        if isinstance(api_key_res, Err):
            return api_key_res
        api_key = api_key_res.ok_value

        client = openai.OpenAI(api_key=api_key, base_url=config.base_url)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""
            return Ok(content)

        except openai.AuthenticationError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    message=str(e),
                    status_code=e.status_code if hasattr(e, "status_code") else None,
                    retryable=False,
                )
            )
        except openai.RateLimitError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.RATE_LIMIT,
                    message=str(e),
                    status_code=e.status_code if hasattr(e, "status_code") else None,
                    retryable=True,
                )
            )
        except openai.APITimeoutError as e:
            return Err(
                ProviderError(
                    kind=ProviderErrorKind.TIMEOUT,
                    message=str(e),
                    retryable=True,
                )
            )
        except openai.APIError as e:
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
        """Invoke OpenAI with streaming."""
        try:
            import openai
        except ImportError:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message="openai package not installed. Run: pip install openai",
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

        client = openai.OpenAI(api_key=api_key, base_url=config.base_url)

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield Ok(content)
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
        """Invoke OpenAI with async streaming."""
        try:
            import openai
        except ImportError:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    message="openai package not installed. Run: pip install openai",
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

        client = openai.AsyncOpenAI(api_key=api_key, base_url=config.base_url)

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield Ok(content)
        except Exception as e:
            yield Err(
                ProviderError(
                    kind=ProviderErrorKind.UNKNOWN,
                    message=str(e),
                    retryable=False,
                )
            )
