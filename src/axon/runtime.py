"""Runtime executor for AXON Phase 2.

This module provides the runtime execution engine for AXON agents,
including provider calls, tool dispatch, and trace emission.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from result import Result, Err, Ok

from axon.parser import parse
from axon.ast_nodes import AgentDecl, MethodDecl, RagDecl, ToolDecl
from axon.evaluator import Scope, evaluate
from axon.expression_ast import LiteralExpr, StringInterpolationExpr
from axon.memory_store import MemoryStore
from axon.provider_registry import resolve_provider_reference, register_provider
from axon.providers import AnthropicProvider, MockProviderPlugin, OpenAIProvider
from axon.rag_registry import RagRegistry
from axon.resilience import ResilientProviderWrapper, RetryConfig, CircuitBreakerConfig
from axon.metrics import MetricsCollector, ProviderCallMetrics
from axon.sandbox import SandboxConfig, SandboxedToolRegistry
from axon.tool_registry import MockToolRegistry, _infer_body_expr
from axon.trace_emitter import TraceEmitter
from axon.type_checker import validate_runtime_type


@dataclass
class RuntimeConfig:
    """Configuration for runtime execution."""
    source_path: Path
    args: dict[str, Any] = field(default_factory=dict)
    trace_output: Optional[Path] = None
    memory_path: Optional[Path] = None
    checkpoint: bool = False
    mock: bool = True
    provider_name: Optional[str] = None
    stream: bool = False
    flow_name: Optional[str] = None
    replay_path: Optional[Path] = None
    agent_name: Optional[str] = None
    sandbox_timeout_ms: int | None = 5000
    sandbox_max_depth: int | None = 100
    sandbox_denied_tools: set[str] = field(default_factory=set)
    strict_types: bool = False
    via_ir: bool = False  # compile .ax through IR before execution


class RuntimeExecutor:
    """Runtime executor for AXON agents."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.metrics = MetricsCollector()

    def execute(self) -> Result[str, str]:
        """Execute the AXON source file.

        Returns:
            Ok(output) on success, Err(message) on failure.
        """
        # Register provider plugins (idempotent if already registered)
        try:
            register_provider(OpenAIProvider())
        except Exception:
            pass  # import failed (openai not installed)
        try:
            register_provider(AnthropicProvider())
        except Exception:
            pass  # import failed (anthropic not installed)
        try:
            register_provider(MockProviderPlugin())
        except Exception:
            pass

        # Load declarations: .axonir directly, .ax via parse (or optionally via IR)
        if self.config.source_path.suffix == ".axonir":
            from axon.ir_compiler import load_ir, ir_to_ast
            ir = load_ir(self.config.source_path)
            declarations = ir_to_ast(ir)
        elif self.config.via_ir:
            from axon.ir_compiler import compile_to_ir, ir_to_ast
            ir = compile_to_ir(self.config.source_path)
            declarations = ir_to_ast(ir)
        else:
            source_text = self.config.source_path.read_text(encoding="utf-8")
            declarations = parse(source_text, parse_expressions=True)

        # Build tool return type map for runtime validation
        tool_return_types: dict[str, str] = {}
        if self.config.strict_types:
            for decl in declarations:
                if isinstance(decl, ToolDecl):
                    tool_return_types[decl.name] = decl.return_type

        from axon.http_client import http_builtins
        from axon.fs_client import fs_builtins

        emitter = TraceEmitter()
        builtins = http_builtins()
        builtins.update(fs_builtins(base_dir=self.config.source_path.parent))
        inner_registry = MockToolRegistry(max_depth=self.config.sandbox_max_depth, builtins=builtins)
        inner_registry.register_all(declarations)

        sandbox_config = SandboxConfig(
            timeout_ms=self.config.sandbox_timeout_ms,
            max_eval_depth=self.config.sandbox_max_depth,
            denied_tools=self.config.sandbox_denied_tools,
        )
        registry = SandboxedToolRegistry(inner_registry, sandbox_config, builtins=builtins)

        rag_registry = RagRegistry(source_base=self.config.source_path.parent)
        rag_registry.register_all(declarations)

        # Build agent registry from all declarations
        agent_registry = self._build_agent_registry(declarations)

        # If --flow is specified, execute flow instead of agent
        if self.config.flow_name:
            from axon.ast_nodes import FlowDecl
            from axon.flow_executor import execute_flow

            flows = [d for d in declarations if isinstance(d, FlowDecl)]
            target_flow = None
            for f in flows:
                if f.name == self.config.flow_name:
                    target_flow = f
                    break
            if target_flow is None:
                return Err(f"Flow '{self.config.flow_name}' not found in source file")

            memory_store = MemoryStore()
            if self.config.memory_path is not None and self.config.memory_path.exists():
                try:
                    memory_store.load_from_file(self.config.memory_path)
                except (OSError, ValueError) as e:
                    return Err(f"Failed to load memory from {self.config.memory_path}: {e}")

            result = execute_flow(
                target_flow,
                self.config.args,
                registry,
                agent_registry,
                emitter,
                memory_store=memory_store,
            )
            registry.shutdown()
            self._maybe_write_trace(emitter)
            if isinstance(result, Err):
                return Err(str(result.err_value))
            return Ok(str(result.ok_value))

        # Find agent: by name if --agent specified, otherwise first agent
        if self.config.agent_name:
            agent = agent_registry.get(self.config.agent_name)
            if not agent:
                return Err(f"Agent '{self.config.agent_name}' not found in source file")
        else:
            agent = self._find_agent(declarations)
            if not agent:
                return Err("No agent declaration found in source file")

        run_method = self._find_run_method(agent)
        if not run_method:
            return Err(f"Agent {agent.name} has no run() method")

        emitter.agent_start(agent_name=agent.name, source_file=str(self.config.source_path))

        # Resolve agent model reference to a provider
        if self.config.mock:
            # Mock mode: always use the mock provider regardless of model reference
            provider_result = resolve_provider_reference("@mock/gpt")
            if isinstance(provider_result, Err):
                provider = None
            else:
                provider = provider_result.ok_value
            model_name = agent.model
        else:
            # Real provider mode: resolve from model reference
            effective_ref = agent.model
            if self.config.provider_name:
                # CLI override: swap provider prefix but keep model suffix
                model_suffix = agent.model.split("/", 1)[1] if "/" in agent.model else "gpt-4"
                effective_ref = f"@{self.config.provider_name}/{model_suffix}"
            provider_result = resolve_provider_reference(effective_ref)
            if isinstance(provider_result, Err):
                provider = None
            else:
                provider = provider_result.ok_value
            model_name = effective_ref

        scope = Scope()
        for param in run_method.params:
            if param.name in self.config.args:
                scope.set(param.name, self.config.args[param.name])
            elif param.default is not None:
                scope.set(param.name, self._parse_default(param.default))
            else:
                return Err(f"Missing argument: {param.name}")

        # Initialise memory store, optionally loading from a previous session
        memory_store = MemoryStore()
        if self.config.memory_path is not None and self.config.memory_path.exists():
            try:
                memory_store.load_from_file(self.config.memory_path)
            except (OSError, ValueError) as e:
                return Err(f"Failed to load memory from {self.config.memory_path}: {e}")

        # Load trace replayer if --replay is specified
        replayer = None
        if self.config.replay_path is not None:
            from axon.trace_replayer import TraceReplayer
            replayer = TraceReplayer(self.config.replay_path)
            emitter.replay_start(
                trace_file=str(self.config.replay_path),
                source_file=str(self.config.source_path),
            )

        # Create shared message bus for inter-agent communication
        from axon.message_bus import MessageBus
        message_bus = MessageBus()

        emitter.method_start(method_name=run_method.name, arguments=self.config.args)

        result = self._evaluate_body(run_method, scope, registry, emitter, provider, model_name, agent_registry, rag_registry, memory_store, replayer=replayer, message_bus=message_bus, agent_name=agent.name, metrics_collector=self.metrics, tool_return_types=tool_return_types)
        registry.shutdown()
        if isinstance(result, Err):
            if replayer is not None:
                emitter.replay_end(result_type="error", result_summary=str(result.err_value))
            emitter.agent_end(result_type="error", result_summary=str(result.err_value))
            self._maybe_write_trace(emitter)
            return result

        # Persist memory state if checkpointing is enabled
        if self.config.checkpoint and self.config.memory_path is not None:
            try:
                memory_store.save_to_file(self.config.memory_path)
                snap = memory_store.snapshot()
                total_keys = sum(len(v) for v in snap.values())
                emitter.checkpoint(path=str(self.config.memory_path), sections=len(snap), keys=total_keys)
            except OSError as e:
                emitter.agent_end(result_type="error", result_summary=f"Checkpoint failed: {e}")
                self._maybe_write_trace(emitter)
                return Err(f"Checkpoint failed: {e}")

        value = result.ok_value
        summary = self._value_summary(value)
        emitter.method_return(method_name=run_method.name, result_type="ok", result_summary=summary)
        if replayer is not None:
            emitter.replay_end(result_type="ok", result_summary=summary)
        emitter.agent_end(result_type="ok", result_summary=summary)
        self._maybe_write_trace(emitter)
        return Ok(str(value))

    def _evaluate_body(
        self,
        method: MethodDecl,
        scope: Scope,
        registry: MockToolRegistry,
        emitter: TraceEmitter,
        provider: Any,
        model_name: str,
        agent_registry: dict[str, AgentDecl],
        rag_registry: RagRegistry,
        memory_store: MemoryStore | None = None,
        replayer: Any | None = None,
        message_bus: Any | None = None,
        agent_name: str = "",
        metrics_collector: MetricsCollector | None = None,
        tool_return_types: dict[str, str] | None = None,
    ) -> Result[Any, str]:
        from axon.trace_replayer import TraceReplayer
        body_text = method.body.strip()

        # Build kwargs dispatch wrapper that emits trace events (or replays)
        def _tool_dispatch(name: str, kwargs: dict[str, Any]) -> Result[Any, str]:
            if replayer is not None:
                return replayer.replay_tool_dispatch(name, kwargs)
            emitter.tool_dispatch(method_name=method.name, tool_name=name, arguments=kwargs)
            tool_start = time.time()
            res = registry.dispatch(name, kwargs)
            if isinstance(res, Err) and res.err_value.kind.name == "NOT_FOUND" and "." in name:
                # Try RAG registry fallback for names like "ProductDocs.retrieve"
                res = rag_registry.dispatch(name, kwargs, emitter=emitter)
            tool_latency_ms = (time.time() - tool_start) * 1000
            if isinstance(res, Err):
                emitter.tool_return(method_name=method.name, tool_name=name, result_type="error", result_summary=res.err_value.kind.name)
                if metrics_collector is not None:
                    from axon.metrics import ToolDispatchMetrics
                    metrics_collector.record_tool_dispatch(ToolDispatchMetrics(
                        tool_name=name,
                        latency_ms=tool_latency_ms,
                        success=False,
                    ))
                return Err(f"Tool dispatch failed: {res.err_value}")
            value = res.ok_value
            # Runtime type validation (if strict_types is enabled)
            if tool_return_types and name in tool_return_types:
                type_err = validate_runtime_type(value, tool_return_types[name])
                if type_err:
                    msg = f"Tool '{name}' returned invalid value: {type_err}"
                    emitter.tool_return(method_name=method.name, tool_name=name, result_type="error", result_summary=msg)
                    if metrics_collector is not None:
                        from axon.metrics import ToolDispatchMetrics
                        metrics_collector.record_tool_dispatch(ToolDispatchMetrics(
                            tool_name=name,
                            latency_ms=tool_latency_ms,
                            success=False,
                        ))
                    return Err(msg)
            emitter.tool_return(method_name=method.name, tool_name=name, result_type="ok", result_summary=self._value_summary(value))
            if metrics_collector is not None:
                from axon.metrics import ToolDispatchMetrics
                metrics_collector.record_tool_dispatch(ToolDispatchMetrics(
                    tool_name=name,
                    latency_ms=tool_latency_ms,
                    success=True,
                ))
            return Ok(value)

        from axon.evaluator import KwargsDispatchFn
        kwargs_dispatch: KwargsDispatchFn = _tool_dispatch

        # Build memory store that emits trace events
        if memory_store is None:
            memory_store = MemoryStore()
        original_set = memory_store.set

        def _store_set(section: str, key: str, value: Any) -> None:
            original_set(section, key, value)
            emitter.store(key=f"memory.{section}[{key}]", value=value)

        memory_store.set = _store_set  # type: ignore[method-assign]

        # Inject memory into scope so expressions like memory.working["key"] resolve
        scope.set("memory", memory_store)

        # Inject message bus send/receive into scope for inter-agent communication
        if message_bus is not None:
            from axon.message_bus import MessageBus
            assert isinstance(message_bus, MessageBus)
            message_bus.set_current_agent(agent_name)

            def _send(recipient: str, message: Any) -> None:
                message_bus.set_current_agent(agent_name)
                message_bus.send(recipient, message)
                summary = str(message)[:50]
                emitter.message_sent(from_agent=agent_name, to_agent=recipient, message_summary=summary)

            def _receive(timeout_ms: int = 0) -> Any | None:
                message_bus.set_current_agent(agent_name)
                result = message_bus.receive(timeout_ms=timeout_ms)
                if result is not None:
                    summary = str(result)[:50]
                    emitter.message_received(agent_name=agent_name, message_summary=summary)
                return result

            def _receive_blocking(timeout_ms: int = 5000) -> Any:
                message_bus.set_current_agent(agent_name)
                result = message_bus.receive_blocking(timeout_ms=timeout_ms)
                summary = str(result)[:50]
                emitter.message_received(agent_name=agent_name, message_summary=summary)
                return result

            scope.set("send", _send)
            scope.set("receive", _receive)
            scope.set("receive_blocking", _receive_blocking)

        # Inject semantic memory operations into scope
        if memory_store is not None:
            def _remember(key: str, value: Any) -> None:
                memory_store.remember(key, value)
                emitter.memory_remember(key=key, value_summary=str(value))

            def _recall(query: str, top_k: int = 5) -> list[Any]:
                results = memory_store.recall(query, top_k=top_k)
                emitter.memory_recall(
                    query_summary=query,
                    result_count=len(results),
                    top_keys=[str(r)[:20] for r in results],
                )
                return results

            def _forget(key: str) -> bool:
                existed = memory_store.forget(key)
                emitter.memory_forget(key=key, existed=existed)
                return existed

            scope.set("remember", _remember)
            scope.set("recall", _recall)
            scope.set("forget", _forget)

        # Build model call wrapper that emits trace events (or replays)
        # Wrap with resilience (retry + circuit breaker) and metrics collection
        _resilient = ResilientProviderWrapper(model_name)

        def _model_call(prompt: str) -> Result[Any, str]:
            if replayer is not None:
                return replayer.replay_model_call(prompt)
            prompt_summary = prompt[:50] + "..." if len(prompt) > 50 else prompt
            if provider is None:
                emitter.model_return(method_name=method.name, result_type="error", result_summary="No provider registered")
                return Err(f"No provider registered for model: {model_name}")
            # Extract model identifier from reference (e.g., "@mock/gpt" -> "gpt")
            model_id = model_name.split("/", 1)[1] if "/" in model_name else model_name

            # Streaming path
            if self.config.stream and provider.supports_streaming():
                emitter.model_stream_start(method_name=method.name, model_reference=model_name, prompt_summary=prompt_summary)
                call_start = time.time()
                chunks: list[str] = []
                try:
                    for chunk_result in provider.call_stream(prompt=prompt, model=model_id, max_tokens=1024):
                        if isinstance(chunk_result, Err):
                            emitter.model_stream_end(method_name=method.name, result_type="error", result_summary=chunk_result.err_value.kind.value)
                            if metrics_collector is not None:
                                metrics_collector.record_provider_call(ProviderCallMetrics(
                                    provider_name=type(provider).__name__,
                                    model=model_id,
                                    latency_ms=(time.time() - call_start) * 1000,
                                    success=False,
                                ))
                            return Err(f"Model stream failed: {chunk_result.err_value}")
                        chunk = chunk_result.ok_value
                        chunks.append(chunk)
                        emitter.model_stream_chunk(method_name=method.name, chunk_summary=self._value_summary(chunk))
                except Exception as e:
                    emitter.model_stream_end(method_name=method.name, result_type="error", result_summary=str(e))
                    return Err(f"Model stream exception: {e}")
                value = "".join(chunks)
                latency_ms = (time.time() - call_start) * 1000
                if metrics_collector is not None:
                    metrics_collector.record_provider_call(ProviderCallMetrics(
                        provider_name=type(provider).__name__,
                        model=model_id,
                        latency_ms=latency_ms,
                        success=True,
                    ))
                emitter.model_stream_end(method_name=method.name, result_type="ok", result_summary=self._value_summary(value))
                return Ok(value)

            # Non-streaming path
            emitter.model_call(method_name=method.name, model_reference=model_name, prompt_summary=prompt_summary)
            call_start = time.time()

            def _do_provider_call():
                return provider.call(prompt=prompt, model=model_id, max_tokens=1024)

            res = _resilient.execute_with_retry(_do_provider_call)

            latency_ms = (time.time() - call_start) * 1000
            if metrics_collector is not None:
                metrics_collector.record_provider_call(ProviderCallMetrics(
                    provider_name=type(provider).__name__,
                    model=model_id,
                    latency_ms=latency_ms,
                    success=isinstance(res, Ok),
                ))

            if isinstance(res, Err):
                emitter.model_return(method_name=method.name, result_type="error", result_summary=res.err_value.kind.value)
                return Err(f"Model call failed: {res.err_value}")
            value = res.ok_value
            emitter.model_return(method_name=method.name, result_type="ok", result_summary=self._value_summary(value))
            return Ok(value)

        # Build trace callback for think/observe events
        def _trace_fn(event_type: str, data: dict[str, Any]) -> None:
            if event_type == "think":
                emitter.think(message=data.get("message", ""))
            elif event_type == "observe":
                emitter.observe(name=data.get("name", ""), value_summary=data.get("value_summary", ""))

        from axon.evaluator import ModelCallFn
        model_call: ModelCallFn = _model_call

        # Build delegate wrapper that looks up agents and evaluates their run() method (or replays)
        def _delegate(agent_name: str, kwargs: dict[str, Any]) -> Result[Any, str]:
            if replayer is not None:
                return replayer.replay_delegate(agent_name, kwargs)
            emitter.delegate_call(method_name=method.name, agent_name=agent_name, arguments=kwargs)
            target_agent = agent_registry.get(agent_name)
            if target_agent is None:
                emitter.delegate_return(method_name=method.name, agent_name=agent_name, result_type="error", result_summary=f"Agent not found: {agent_name}")
                return Err(f"Agent not found: {agent_name}")

            target_method = self._find_run_method(target_agent)
            if target_method is None:
                emitter.delegate_return(method_name=method.name, agent_name=agent_name, result_type="error", result_summary=f"Agent {agent_name} has no run() method")
                return Err(f"Agent {agent_name} has no run() method")

            # Resolve target agent's model
            target_provider_result = resolve_provider_reference(target_agent.model)
            if isinstance(target_provider_result, Err):
                target_provider = None
                target_model_name = target_agent.model
            else:
                target_provider = target_provider_result.ok_value
                target_model_name = target_agent.model

            # Build scope for delegated agent
            child_scope = Scope()
            for param in target_method.params:
                if param.name in kwargs:
                    child_scope.set(param.name, kwargs[param.name])
                elif param.default is not None:
                    child_scope.set(param.name, self._parse_default(param.default))
                else:
                    emitter.delegate_return(method_name=method.name, agent_name=agent_name, result_type="error", result_summary=f"Missing argument: {param.name}")
                    return Err(f"Missing argument for {agent_name}.{target_method.name}: {param.name}")

            # Validate argument types at runtime
            for param in target_method.params:
                if param.name in kwargs:
                    err = validate_runtime_type(kwargs[param.name], param.type_str)
                    if err:
                        msg = f"Agent '{agent_name}' argument '{param.name}': {err} (expected {param.type_str})"
                        emitter.delegate_return(method_name=method.name, agent_name=agent_name, result_type="error", result_summary=msg)
                        return Err(msg)

            # Recursively evaluate the target agent's body
            sub_res = self._evaluate_body(target_method, child_scope, registry, emitter, target_provider, target_model_name, agent_registry, rag_registry, memory_store, replayer=replayer, message_bus=message_bus, agent_name=agent_name, metrics_collector=metrics_collector, tool_return_types=tool_return_types)
            if isinstance(sub_res, Err):
                emitter.delegate_return(method_name=method.name, agent_name=agent_name, result_type="error", result_summary=str(sub_res.err_value))
                return sub_res
            value = sub_res.ok_value
            emitter.delegate_return(method_name=method.name, agent_name=agent_name, result_type="ok", result_summary=self._value_summary(value))
            return Ok(value)

        from axon.evaluator import DelegateFn
        delegate: DelegateFn = _delegate

        # If parsed_body is a plain LiteralExpr string that contains interpolation
        # patterns, the expression parser did not split it — fall back to inference.
        if (
            method.parsed_body is not None
            and not isinstance(method.parsed_body, StringInterpolationExpr)
        ):
            if isinstance(method.parsed_body, LiteralExpr) and isinstance(method.parsed_body.value, str):
                if re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", method.parsed_body.value):
                    inferred = _infer_body_expr(body_text)
                    if inferred is not None:
                        eval_res = evaluate(inferred, scope, kwargs_dispatch_fn=kwargs_dispatch, memory_store=memory_store, model_call_fn=model_call, delegate_fn=delegate, trace_fn=_trace_fn)
                        if isinstance(eval_res, Err):
                            return Err(f"Evaluation error: {eval_res.err_value}")
                        return Ok(eval_res.ok_value)

        if method.parsed_body is not None:
            eval_res = evaluate(method.parsed_body, scope, kwargs_dispatch_fn=kwargs_dispatch, memory_store=memory_store, model_call_fn=model_call, delegate_fn=delegate, trace_fn=_trace_fn)
            if isinstance(eval_res, Err):
                return Err(f"Evaluation error: {eval_res.err_value}")
            return Ok(eval_res.ok_value)

        inferred = _infer_body_expr(body_text)
        if inferred is not None:
            eval_res = evaluate(inferred, scope, kwargs_dispatch_fn=kwargs_dispatch, memory_store=memory_store, model_call_fn=model_call, delegate_fn=delegate, trace_fn=_trace_fn)
            if isinstance(eval_res, Err):
                return Err(f"Evaluation error: {eval_res.err_value}")
            return Ok(eval_res.ok_value)
        return Ok(None)

    def _find_run_method(self, agent: AgentDecl) -> Optional[MethodDecl]:
        for method in agent.methods:
            if method.name == "run":
                return method
        return None

    @staticmethod
    def _build_agent_registry(declarations: list) -> dict[str, AgentDecl]:
        """Build a registry mapping agent names to their declarations."""
        registry: dict[str, AgentDecl] = {}
        for decl in declarations:
            if isinstance(decl, AgentDecl):
                registry[decl.name] = decl
        return registry

    def _maybe_write_trace(self, emitter: TraceEmitter) -> None:
        if self.config.trace_output is not None:
            emitter.write(self.config.trace_output)

    def get_metrics(self) -> dict[str, Any]:
        """Return collected runtime metrics as a dictionary."""
        return self.metrics.to_dict()

    @staticmethod
    def _parse_default(value_str: str) -> Any:
        value_str = value_str.strip()
        if value_str == "true":
            return True
        if value_str == "false":
            return False
        if value_str == "None":
            return None
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str

    @staticmethod
    def _value_summary(value: Any) -> str:
        if value is None:
            return "None"
        if isinstance(value, str):
            if len(value) <= 50:
                return value
            return value[:50] + "..."
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(value)
        if isinstance(value, list):
            return f"List[{len(value)}]"
        if isinstance(value, dict):
            return f"Dict[{len(value)}]"
        return str(value)[:50]

    
    def _find_agent(self, declarations: list) -> Optional[AgentDecl]:
        """Find the agent declaration in the parsed declarations."""
        for decl in declarations:
            if isinstance(decl, AgentDecl):
                return decl
        return None


def execute_runtime(config: RuntimeConfig) -> Result[str, str]:
    """Execute AXON runtime with the given configuration.

    Args:
        config: Runtime configuration

    Returns:
        Result with execution output or error message.
    """
    executor = RuntimeExecutor(config)
    return executor.execute()
