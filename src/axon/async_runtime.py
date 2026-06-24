"""Async runtime executor for AXON Phase 4.

This module provides an async execution engine for AXON agents,
including async provider calls, streaming, and concurrent tool dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator
from result import Result, Err, Ok

from axon.parser import parse
from axon.provider_registry import resolve_provider_reference, register_provider
from axon.providers import AnthropicProvider, MockProviderPlugin, OpenAIProvider
from axon.runtime import RuntimeConfig
from axon.trace_emitter import TraceEmitter


@dataclass
class AsyncRuntimeConfig:
    """Configuration for async runtime execution."""
    source_path: Path
    provider_name: str = "mock"
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False


class AsyncRuntimeExecutor:
    """Async executor for AXON agents.
    
    Supports async provider calls and streaming for real-time UIs.
    """

    def __init__(self, config: AsyncRuntimeConfig) -> None:
        self.config = config

    async def execute(self) -> Result[str, str]:
        """Execute the AXON source file asynchronously."""
        # Register providers
        try:
            register_provider(OpenAIProvider())
        except Exception:
            pass
        try:
            register_provider(AnthropicProvider())
        except Exception:
            pass
        try:
            register_provider(MockProviderPlugin())
        except Exception:
            pass

        source_text = self.config.source_path.read_text(encoding="utf-8")
        declarations = parse(source_text, parse_expressions=True)

        emitter = TraceEmitter()

        # Find the agent
        from axon.ast_nodes import AgentDecl
        agents = [d for d in declarations if isinstance(d, AgentDecl)]
        if not agents:
            return Err("No agent declaration found in source file")

        agent = agents[0]

        # Resolve provider
        provider_ref = self.config.provider_name
        if hasattr(agent, "model") and agent.model:
            provider_ref = agent.model

        provider_result = resolve_provider_reference(provider_ref)
        if isinstance(provider_result, Err):
            return Err(f"Provider not found: {provider_ref} — {provider_result.err_value}")
        provider = provider_result.ok_value

        model = self.config.model or (provider_ref.split("/")[1] if "/" in provider_ref else "gpt-4")

        # Find the run method
        run_method = None
        if hasattr(agent, "methods"):
            for method in agent.methods:
                if method.name == "run":
                    run_method = method
                    break

        if run_method is None:
            return Err("Agent has no 'run' method")

        # Build prompt from method body
        prompt = self._build_prompt(run_method)

        # Emit trace event
        emitter.model_call(method_name=run_method.name, model_reference=model, prompt_summary=prompt[:100])

        if self.config.stream:
            return Err("Use execute_stream() for streaming")

        # Async provider call
        result = await provider.call_async(
            prompt=prompt,
            model=model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        if isinstance(result, Err):
            return Err(f"Provider error: {result.err_value}")

        return Ok(result.ok_value)

    async def execute_stream(self) -> AsyncIterator[Result[str, str]]:
        """Execute with async streaming.
        
        Yields chunks of the response as they arrive from the provider.
        """
        try:
            register_provider(OpenAIProvider())
        except Exception:
            pass
        try:
            register_provider(AnthropicProvider())
        except Exception:
            pass
        try:
            register_provider(MockProviderPlugin())
        except Exception:
            pass

        source_text = self.config.source_path.read_text(encoding="utf-8")
        declarations = parse(source_text, parse_expressions=True)

        from axon.ast_nodes import AgentDecl
        agents = [d for d in declarations if isinstance(d, AgentDecl)]
        if not agents:
            yield Err("No agent declaration found in source file")
            return

        agent = agents[0]
        provider_ref = self.config.provider_name
        if hasattr(agent, "model") and agent.model:
            provider_ref = agent.model

        provider_result = resolve_provider_reference(provider_ref)
        if isinstance(provider_result, Err):
            yield Err(f"Provider not found: {provider_ref} — {provider_result.err_value}")
            return
        provider = provider_result.ok_value

        model = self.config.model or (provider_ref.split("/")[1] if "/" in provider_ref else "gpt-4")

        run_method = None
        if hasattr(agent, "methods"):
            for method in agent.methods:
                if method.name == "run":
                    run_method = method
                    break

        if run_method is None:
            yield Err("Agent has no 'run' method")
            return

        prompt = self._build_prompt(run_method)

        async for chunk in provider.call_stream_async(
            prompt=prompt,
            model=model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        ):
            if isinstance(chunk, Err):
                yield Err(f"Provider error: {chunk.err_value}")
                return
            yield Ok(chunk.ok_value)

    def _build_prompt(self, method) -> str:
        """Build a prompt from a method declaration."""
        if hasattr(method, "parsed_body") and method.parsed_body:
            from axon.evaluator import evaluate
            from axon.expression_ast import StringInterpolationExpr
            if isinstance(method.parsed_body, StringInterpolationExpr):
                return method.parsed_body.template
            return str(method.parsed_body)
        if hasattr(method, "body") and method.body:
            return method.body
        return ""


async def execute_runtime_async(config: AsyncRuntimeConfig) -> Result[str, str]:
    """Convenience function for async runtime execution."""
    executor = AsyncRuntimeExecutor(config)
    return await executor.execute()
