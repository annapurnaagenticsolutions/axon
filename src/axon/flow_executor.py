"""Flow execution engine for AXON.

Executes AXON `flow` declarations as deterministic DAGs of stage calls.
Stages are resolved to tools or agent methods; outputs flow between
stages according to arrow syntax.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from result import Result, Ok, Err

from axon.ast_nodes import FlowDecl, StageDecl, Param, ToolDecl, AgentDecl
from axon.evaluator import Scope, evaluate
from axon.memory_store import MemoryStore
from axon.tool_registry import MockToolRegistry
from axon.trace_emitter import TraceEmitter


@dataclass
class FlowEdge:
    """A directed edge in the flow DAG."""
    from_stage: str | list[str]  # single stage name or list for parallel branches
    to_stage: str


@dataclass
class FlowNode:
    """A node in the flow DAG representing a stage."""
    stage: StageDecl
    predecessors: list[str] = field(default_factory=list)
    is_parallel_merge: bool = False  # True if this node merges parallel branches
    parallel_sources: list[str] = field(default_factory=list)


def parse_arrows(body: str) -> list[FlowEdge]:
    """Parse arrow syntax from flow body text.

    Supports:
    - A -> B
    - [A, B] -> C
    """
    edges: list[FlowEdge] = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        # Parallel merge: [A, B] -> C
        parallel_match = re.match(r"\[\s*([^\]]+)\s*\]\s*->\s*(\w+)", line)
        if parallel_match:
            sources = [s.strip() for s in parallel_match.group(1).split(",")]
            target = parallel_match.group(2)
            edges.append(FlowEdge(from_stage=sources, to_stage=target))
            continue

        # Linear: A -> B
        linear_match = re.match(r"(\w+)\s*->\s*(\w+)", line)
        if linear_match:
            source = linear_match.group(1)
            target = linear_match.group(2)
            edges.append(FlowEdge(from_stage=source, to_stage=target))

    return edges


def build_dag(flow: FlowDecl) -> dict[str, FlowNode]:
    """Build a DAG from flow stages and arrow edges."""
    edges = parse_arrows(flow.body)

    # Map stage names to StageDecl
    stage_map = {s.name: s for s in flow.stages}

    # Build nodes
    nodes: dict[str, FlowNode] = {}
    for stage in flow.stages:
        nodes[stage.name] = FlowNode(stage=stage)

    # Connect edges
    for edge in edges:
        if isinstance(edge.from_stage, list):
            # Parallel merge: [A, B] -> C
            target = nodes.get(edge.to_stage)
            if target:
                target.is_parallel_merge = True
                target.parallel_sources = edge.from_stage
                for src in edge.from_stage:
                    target.predecessors.append(src)
        else:
            source_name = edge.from_stage
            target = nodes.get(edge.to_stage)
            if target:
                target.predecessors.append(source_name)

    return nodes


def topological_sort(nodes: dict[str, FlowNode]) -> list[str]:
    """Return stage names in topological order."""
    # Kahn's algorithm
    in_degree = {name: 0 for name in nodes}
    for name, node in nodes.items():
        for pred in node.predecessors:
            in_degree[name] += 1

    # Find all nodes with no predecessors
    queue = [name for name, deg in in_degree.items() if deg == 0]
    result: list[str] = []

    while queue:
        # Sort for deterministic order when multiple options
        queue.sort()
        name = queue.pop(0)
        result.append(name)

        # Reduce in-degree for nodes that have this as predecessor
        for other_name, other_node in nodes.items():
            if name in other_node.predecessors:
                in_degree[other_name] -= 1
                if in_degree[other_name] == 0:
                    queue.append(other_name)

    if len(result) != len(nodes):
        raise ValueError("Flow contains a cycle in stage arrows")

    return result


def _type_matches(flow_type: str, stage_type: str) -> bool:
    """Check if two AXON type strings match (simple exact match)."""
    # Normalize Python type names to AXON conventions
    PYTHON_TO_AXON = {
        "str": "Str",
        "int": "Int",
        "float": "Float",
        "bool": "Bool",
        "list": "List",
        "dict": "Map",
    }
    a = flow_type.strip()
    b = stage_type.strip()
    a = PYTHON_TO_AXON.get(a.lower(), a)
    b = PYTHON_TO_AXON.get(b.lower(), b)
    return a == b


def _resolve_param(
    param: Param,
    flow_args: dict[str, Any],
    stage_outputs: dict[str, Any],
) -> Result[Any, str]:
    """Resolve a single stage parameter from flow args or previous stage outputs."""
    # 1. Exact name match with flow args
    if param.name in flow_args:
        return Ok(flow_args[param.name])

    # 2. Match by type from previous stage outputs
    candidates: list[tuple[str, Any]] = []
    for stage_name, output in stage_outputs.items():
        # Simple heuristic: if param type is List<X>, look for list outputs
        # For exact type match
        param_type = param.type_str
        if param_type.startswith("List<"):
            # For List params, we might need to collect from parallel branches
            # handled separately
            pass
        # Try to match output to param by looking at the value type
        candidates.append((stage_name, output))

    # If there's exactly one previous output and the param type seems compatible
    if len(candidates) == 1:
        return Ok(candidates[0][1])

    if param.default is not None:
        return Ok(param.default)

    return Err(f"Cannot resolve parameter '{param.name}: {param.type_str}'")


def _build_stage_args(
    stage: StageDecl,
    flow_args: dict[str, Any],
    stage_outputs: dict[str, Any],
    predecessors: list[str],
    is_merge: bool = False,
    merge_sources: list[str] | None = None,
) -> Result[dict[str, Any], str]:
    """Build keyword arguments for a stage call.

    Only considers stage_outputs from actual DAG predecessors, not sibling
    branches that happen to have executed already.
    """
    kwargs: dict[str, Any] = {}

    # Filter stage_outputs to only include outputs from actual predecessors
    predecessor_outputs = {k: v for k, v in stage_outputs.items() if k in predecessors}

    for param in stage.params:
        # 1. Exact name match with flow args
        if param.name in flow_args:
            kwargs[param.name] = flow_args[param.name]
            continue

        # 2. For merge stages with List<...> param, collect parallel outputs
        if is_merge and merge_sources and param.type_str.startswith("List<"):
            outputs = []
            for src in merge_sources:
                if src in stage_outputs:
                    outputs.append(stage_outputs[src])
            kwargs[param.name] = outputs
            continue

        # 3. Match from predecessor stage outputs
        matched = False
        for src_name, output in predecessor_outputs.items():
            if param.name.lower() in src_name.lower() or src_name.lower() in param.name.lower():
                kwargs[param.name] = output
                matched = True
                break

        if matched:
            continue

        # 4. If only one predecessor output exists
        if len(predecessor_outputs) == 1 and not is_merge:
            output = list(predecessor_outputs.values())[0]
            kwargs[param.name] = output
            continue

        # 5. Type-based match from flow args
        if not predecessor_outputs:
            flow_match = None
            for flow_param_name, flow_value in flow_args.items():
                if _type_matches(param.type_str, type(flow_value).__name__) or param.name.lower() in flow_param_name.lower():
                    flow_match = flow_value
                    break
            if flow_match is not None:
                kwargs[param.name] = flow_match
                continue

        if param.default is not None:
            kwargs[param.name] = param.default
            continue

        return Err(
            f"Cannot resolve parameter '{param.name}: {param.type_str}' "
            f"for stage '{stage.name}'"
        )

    return Ok(kwargs)


def execute_flow(
    flow: FlowDecl,
    flow_args: dict[str, Any],
    tools: MockToolRegistry,
    agents: dict[str, AgentDecl],
    emitter: TraceEmitter,
    memory_store: Optional[MemoryStore] = None,
) -> Result[Any, str]:
    """Execute a flow declaration and return the final result.

    Args:
        flow: The FlowDecl to execute.
        flow_args: Keyword arguments for the flow parameters.
        tools: ToolRegistry for tool dispatch.
        agents: Map of agent name -> AgentDecl for agent dispatch.
        emitter: TraceEmitter for flow/stage trace events.
        memory_store: Optional MemoryStore.

    Returns:
        Ok(final_result) on success, Err(error_message) on failure.
    """
    emitter.flow_start(flow_name=flow.name, args=flow_args)
    start_time = time.time()

    try:
        nodes = build_dag(flow)
        order = topological_sort(nodes)
    except ValueError as e:
        emitter.flow_end(result_type="error", result_summary=str(e))
        return Err(str(e))

    stage_outputs: dict[str, Any] = {}

    for stage_name in order:
        node = nodes[stage_name]
        stage = node.stage

        emitter.stage_start(stage_name=stage.name, input_keys=[p.name for p in stage.params])

        # Build args for this stage
        arg_result = _build_stage_args(
            stage, flow_args, stage_outputs,
            predecessors=node.predecessors,
            is_merge=node.is_parallel_merge,
            merge_sources=node.parallel_sources,
        )
        if isinstance(arg_result, Err):
            emitter.stage_end(
                stage_name=stage.name, result_type="error", result_summary=arg_result.err_value
            )
            emitter.flow_end(
                result_type="error", result_summary=arg_result.err_value
            )
            return Err(arg_result.err_value)

        kwargs = arg_result.ok_value

        # Resolve stage to tool or agent
        result = _execute_stage(stage, kwargs, tools, agents, memory_store)

        if isinstance(result, Err):
            emitter.stage_end(
                stage_name=stage.name, result_type="error", result_summary=str(result.err_value)
            )
            emitter.flow_end(
                result_type="error", result_summary=str(result.err_value)
            )
            return Err(str(result.err_value))

        value = result.ok_value
        stage_outputs[stage.name] = value
        emitter.stage_end(
            stage_name=stage.name,
            result_type="ok",
            result_summary=_value_summary(value),
        )

    duration_ms = int((time.time() - start_time) * 1000)
    final_value = stage_outputs.get(order[-1]) if order else None
    emitter.flow_end(
        result_type="ok",
        result_summary=_value_summary(final_value),
        duration_ms=duration_ms,
    )
    return Ok(final_value)


def _execute_stage(
    stage: StageDecl,
    kwargs: dict[str, Any],
    tools: MockToolRegistry,
    agents: dict[str, AgentDecl],
    memory_store: Optional[MemoryStore],
) -> Result[Any, str]:
    """Execute a single stage by resolving to a tool or agent."""
    # Try tool first
    tool_result = tools.dispatch(stage.name, kwargs)
    if isinstance(tool_result, Ok):
        return tool_result

    # Try agent run method
    agent = agents.get(stage.name)
    if agent is not None:
        run_method = None
        for m in agent.methods:
            if m.name == "run":
                run_method = m
                break
        if run_method is not None:
            scope = Scope()
            for param in run_method.params:
                if param.name in kwargs:
                    scope.set(param.name, kwargs[param.name])

            from axon.tool_registry import _infer_body_expr
            body_text = run_method.body
            if run_method.parsed_body is not None:
                eval_res = evaluate(
                    run_method.parsed_body, scope,
                    kwargs_dispatch_fn=tools.dispatch,
                    memory_store=memory_store,
                )
                if isinstance(eval_res, Ok):
                    return eval_res
                return Err(f"Agent stage '{stage.name}' evaluation error: {eval_res.err_value}")

            inferred = _infer_body_expr(body_text)
            if inferred is not None:
                eval_res = evaluate(
                    inferred, scope,
                    kwargs_dispatch_fn=tools.dispatch,
                    memory_store=memory_store,
                )
                if isinstance(eval_res, Ok):
                    return eval_res
                return Err(f"Agent stage '{stage.name}' evaluation error: {eval_res.err_value}")

            return Ok(None)

    # Neither tool nor agent found
    err_msg = f"Stage '{stage.name}' not found: no matching tool or agent"
    if isinstance(tool_result, Err):
        err_msg = f"Stage '{stage.name}' dispatch failed: {tool_result.err_value}"
    return Err(err_msg)


def _value_summary(value: Any) -> str:
    """Summarize a value for trace events."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return value[:50] + "..." if len(value) > 50 else value
    if isinstance(value, (list, dict)):
        return f"<{type(value).__name__} len={len(value)}>"
    return str(value)[:50]
