# RFC #017 — REST API Server

**Status:** Draft  
**Phase:** 6 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Expose the AXON runtime via a FastAPI HTTP server so that agents can be managed, executed, monitored, and streamed remotely. The server reuses the existing `AgentLifecycleManager`, `AgentSupervisor`, `MetricsCollector`, and `CheckpointManager` but presents them through authenticated REST and WebSocket endpoints.

## Motivation

The CLI is developer-friendly but insufficient for production deployments:
- Remote services cannot invoke `axon agent spawn` over SSH
- Web UIs need streaming output via WebSocket/SSE
- Monitoring systems need a pull endpoint for metrics
- Multi-tenant deployments need authenticated access

## Goals

- FastAPI application with lifecycle endpoints (`/agents`, `/supervisors`, `/metrics`, `/checkpoints`)
- WebSocket endpoint `/ws/agents/{name}` for real-time streaming output
- API key authentication via `X-API-Key` header
- CLI command `axon serve-api [--host] [--port] [--api-key]`
- Reuse all existing managers; no new state machine

## Non-Goals

- OAuth2 / SSO (API key only for this sprint)
- TLS termination (use reverse proxy)
- Multi-node clustering (single process only)
- GraphQL or gRPC

## API Surface

### Agents

| Method | Path | Description |
|---|---|---|
| POST | `/agents` | Spawn an agent |
| POST | `/agents/{name}/pause` | Pause an agent |
| POST | `/agents/{name}/resume` | Resume an agent |
| POST | `/agents/{name}/terminate` | Terminate an agent |
| GET | `/agents/{name}` | Get agent status |
| GET | `/agents` | List all agents |
| POST | `/agents/{name}/checkpoint` | Save checkpoint |
| POST | `/agents/{name}/restore` | Restore from checkpoint |

### Supervisors

| Method | Path | Description |
|---|---|---|
| POST | `/supervisors` | Start a supervisor |
| POST | `/supervisors/{name}/stop` | Stop a supervisor |
| GET | `/supervisors/{name}` | Get supervisor status |

### Metrics & Health

| Method | Path | Description |
|---|---|---|
| GET | `/metrics` | Runtime metrics |
| GET | `/health` | Health check |

### Streaming

| Protocol | Path | Description |
|---|---|---|
| WebSocket | `/ws/agents/{name}` | Real-time output stream |

## Authentication

A single global API key passed via `X-API-Key` header. If no key is configured (`--api-key` omitted), the server runs unauthenticated for local dev.

## Testing Strategy

- Unit test each endpoint with TestClient
- Unit test WebSocket streaming
- Unit test 401 on missing API key
- Verify no regressions in existing tests
