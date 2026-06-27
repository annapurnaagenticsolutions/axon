"""FastAPI server for AXON runtime.

Exposes agent lifecycle, supervision, metrics, checkpointing,
and real-time streaming via REST and WebSocket endpoints.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from result import Err, Ok

from axon.agent_lifecycle import AgentLifecycleManager, AgentStatus
from axon.agent_supervisor import AgentSupervisor, RestartStrategy
from axon.checkpoint_manager import CheckpointManager
from axon.metrics import MetricsCollector
from axon.metrics_exporter import MetricsExporter
from axon.streaming_collector import StreamingCollector
from axon.trace_emitter import TraceEmitter


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SpawnRequest(BaseModel):
    name: str = Field(..., description="Unique name for the agent instance")
    source: str = Field(..., description="Path to the .ax source file")
    args: dict[str, Any] = Field(default_factory=dict)
    mock: bool = True
    provider_name: str | None = None
    trace_output: str | None = None
    memory_path: str | None = None
    checkpoint: bool = False
    stream: bool = False


class SupervisorStartRequest(BaseModel):
    name: str
    strategy: str = "one_for_one"
    max_restarts: int = 5
    max_seconds: int = 60
    mock: bool = True
    provider_name: str | None = None
    children: list[str] = Field(default_factory=list)  # source_path::child_name


class CheckpointRequest(BaseModel):
    output: str | None = None


class RestoreRequest(BaseModel):
    snapshot: str
    mock: bool = True
    provider_name: str | None = None


class AgentInfo(BaseModel):
    id: str
    name: str
    status: str
    source_path: str
    last_output: str
    last_error: str


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Lifespan state
# ---------------------------------------------------------------------------

class ServerState:
    """Shared runtime state for the FastAPI app."""

    def __init__(self) -> None:
        self.lifecycle = AgentLifecycleManager()
        self.metrics = MetricsCollector()
        self.supervisors: dict[str, AgentSupervisor] = {}
        self.api_key: str | None = None


_state = ServerState()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    yield
    # Shutdown: terminate all running agents
    for inst in _state.lifecycle.list_agents():
        if inst.status != AgentStatus.TERMINATED:
            _state.lifecycle.terminate(inst.name)
    for sup in list(_state.supervisors.values()):
        sup.stop()


app = FastAPI(
    title="AXON Runtime API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

from fastapi import Header, Depends


def require_api_key(x_api_key: str | None = Header(None)) -> None:
    if _state.api_key is None:
        return
    if x_api_key != _state.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


# ---------------------------------------------------------------------------
# Agent endpoints
# ---------------------------------------------------------------------------

@app.post("/agents", dependencies=[Depends(require_api_key)], response_model=AgentInfo, status_code=201)
async def spawn_agent(req: SpawnRequest) -> dict[str, Any]:
    result = _state.lifecycle.spawn(
        source_path=Path(req.source),
        name=req.name,
        args=req.args,
        mock=req.mock,
        provider_name=req.provider_name,
        trace_output=Path(req.trace_output) if req.trace_output else None,
        memory_path=Path(req.memory_path) if req.memory_path else None,
        checkpoint=req.checkpoint,
        stream=req.stream,
    )
    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.err_value)

    status_res = _state.lifecycle.status(req.name)
    if isinstance(status_res, Err):
        raise HTTPException(status_code=500, detail=status_res.err_value)
    inst = status_res.ok_value
    return inst.to_dict()


@app.get("/agents", dependencies=[Depends(require_api_key)])
async def list_agents() -> list[dict[str, Any]]:
    return [a.to_dict() for a in _state.lifecycle.list_agents()]


@app.get("/agents/{name}", dependencies=[Depends(require_api_key)])
async def get_agent(name: str) -> dict[str, Any]:
    result = _state.lifecycle.status(name)
    if isinstance(result, Err):
        raise HTTPException(status_code=404, detail=result.err_value)
    return result.ok_value.to_dict()


@app.post("/agents/{name}/pause", dependencies=[Depends(require_api_key)])
async def pause_agent(name: str) -> dict[str, str]:
    result = _state.lifecycle.pause(name)
    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.err_value)
    return {"status": "paused", "name": name}


@app.post("/agents/{name}/resume", dependencies=[Depends(require_api_key)])
async def resume_agent(name: str) -> dict[str, str]:
    result = _state.lifecycle.resume(name)
    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.err_value)
    return {"status": "resumed", "name": name}


@app.post("/agents/{name}/terminate", dependencies=[Depends(require_api_key)])
async def terminate_agent(name: str, reason: str = Query(default="api_request")) -> dict[str, str]:
    result = _state.lifecycle.terminate(name, reason=reason)
    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.err_value)
    return {"status": "terminated", "name": name}


@app.post("/agents/{name}/checkpoint", dependencies=[Depends(require_api_key)])
async def checkpoint_agent(name: str, req: CheckpointRequest) -> dict[str, Any]:
    cm = CheckpointManager(_state.lifecycle)
    output = Path(req.output) if req.output else None
    result = cm.checkpoint(name, output_path=output)
    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.err_value)
    return {"status": "checkpoint_saved", "path": str(result.ok_value)}


@app.post("/agents/{name}/restore", dependencies=[Depends(require_api_key)])
async def restore_agent(name: str, req: RestoreRequest) -> dict[str, Any]:
    cm = CheckpointManager(_state.lifecycle)
    result = cm.restore(
        name,
        snapshot_path=Path(req.snapshot),
        mock=req.mock,
        provider_name=req.provider_name,
    )
    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.err_value)
    return {"status": "restored", "name": name, "id": result.ok_value}


# ---------------------------------------------------------------------------
# Supervisor endpoints
# ---------------------------------------------------------------------------

@app.post("/supervisors", dependencies=[Depends(require_api_key)], status_code=201)
async def start_supervisor(req: SupervisorStartRequest) -> dict[str, Any]:
    if req.name in _state.supervisors:
        raise HTTPException(status_code=409, detail=f"Supervisor '{req.name}' already exists")

    strategy = RestartStrategy(req.strategy)
    supervisor = AgentSupervisor(
        name=req.name,
        strategy=strategy,
        max_restarts=req.max_restarts,
        max_seconds=req.max_seconds,
    )

    for child_spec in req.children:
        if "::" not in child_spec:
            raise HTTPException(status_code=400, detail=f"Invalid child spec: {child_spec}")
        source_str, child_name = child_spec.split("::", 1)
        supervisor.add_child(source_path=Path(source_str), name=child_name)

    start_result = supervisor.start()
    if isinstance(start_result, Err):
        raise HTTPException(status_code=400, detail=start_result.err_value)

    _state.supervisors[req.name] = supervisor
    return {"status": "started", "name": req.name, "strategy": req.strategy}


@app.post("/supervisors/{name}/stop", dependencies=[Depends(require_api_key)])
async def stop_supervisor(name: str) -> dict[str, str]:
    supervisor = _state.supervisors.pop(name, None)
    if supervisor is None:
        raise HTTPException(status_code=404, detail=f"Supervisor '{name}' not found")
    supervisor.stop()
    return {"status": "stopped", "name": name}


@app.get("/supervisors/{name}", dependencies=[Depends(require_api_key)])
async def get_supervisor(name: str) -> dict[str, Any]:
    supervisor = _state.supervisors.get(name)
    if supervisor is None:
        raise HTTPException(status_code=404, detail=f"Supervisor '{name}' not found")
    return {
        "name": supervisor.name,
        "strategy": supervisor.strategy.value,
        "running": supervisor.is_running,
        "children": [c.name for c in supervisor.children],
    }


# ---------------------------------------------------------------------------
# Metrics & Health
# ---------------------------------------------------------------------------

@app.get("/metrics", dependencies=[Depends(require_api_key)])
async def get_metrics() -> dict[str, Any]:
    exporter = MetricsExporter(_state.metrics)
    return exporter.to_dict()


@app.get("/health")
async def health_check() -> dict[str, Any]:
    from axon.health_check import HealthChecker
    checker = HealthChecker(lifecycle=_state.lifecycle)
    report = checker.check()
    return report.to_dict()


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------

@app.websocket("/ws/agents/{name}")
async def agent_stream(websocket: WebSocket, name: str) -> None:
    await websocket.accept()
    collector = StreamingCollector()

    try:
        while True:
            # Poll for chunks from the agent's output
            result = _state.lifecycle.status(name)
            if isinstance(result, Ok):
                inst = result.ok_value
                # Simple polling: send last_output if changed
                if inst.last_output:
                    await websocket.send_text(inst.last_output)
            # Client can also send commands
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "pause":
                _state.lifecycle.pause(name)
            elif msg.get("action") == "terminate":
                _state.lifecycle.terminate(name)
                break
            elif msg.get("action") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
