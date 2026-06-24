# RFC #020 — Docker Hardening & Production Deployment

**Status:** Draft  
**Phase:** 9 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

Provide hardened Docker images, docker-compose stacks, and Kubernetes manifests for deploying AXON in production. The artifacts support the full AXON stack: API server, PostgreSQL, Redis (future message bus), with security hardening (non-root user, read-only root filesystem, health checks, resource limits).

## Motivation

Current state:
- No Dockerfile exists
- No deployment automation
- The API server is started manually via `axon serve-api`

Production requirements:
- Immutable container images with version pinning
- Non-root execution for security
- Health checks for orchestrators (K8s, Docker Swarm)
- Environment-based configuration (no secrets in images)
- Multi-service orchestration (API + database + cache)

## Goals

- Multi-stage Dockerfile with Python 3.12 slim base
- Non-root user (`axon` UID 10001)
- Health check endpoint (`/health`) wired into Dockerfile
- Docker Compose stack: API server + PostgreSQL + Redis
- Kubernetes manifests: Deployment, Service, ConfigMap, Secret, Ingress
- `.dockerignore` for minimal image size
- No secrets baked into images

## Non-Goals

- Helm charts (plain K8s YAML only; Helm is a future sprint)
- Terraform / Pulumi infrastructure provisioning
- CI/CD pipeline (GitHub Actions is a future sprint)
- Multi-arch builds (amd64 only for now)

## Design

### Dockerfile

```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build
COPY src/ src/
RUN python -m build --wheel

# Runtime stage
FROM python:3.12-slim AS runtime
RUN groupadd -r axon && useradd -r -g axon -u 10001 axon
WORKDIR /app
COPY --from=builder /app/dist/*.whl .
RUN pip install --no-cache-dir *.whl[serve,db] && rm *.whl
USER axon
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["axon", "serve-api", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

- `axon-api` service: built from Dockerfile, depends on `postgres` and `redis`
- `postgres` service: official PostgreSQL 16 image with volume
- `redis` service: official Redis 7 image (for future message bus persistence)

### Kubernetes Manifests

- `axon-deployment.yaml`: Deployment with 2 replicas, resource limits, liveness/readiness probes
- `axon-service.yaml`: ClusterIP service on port 8000
- `axon-configmap.yaml`: Non-sensitive config (log level, timeouts)
- `axon-secret.yaml`: Sensitive config (API key, DB password)
- `axon-ingress.yaml`: Ingress for external access

## Testing Strategy

- Build Dockerfile locally and verify `docker run` responds to `/health`
- Run `docker-compose up` and verify API + PostgreSQL connectivity
- Validate K8s manifests with `kubectl apply --dry-run=client`

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Large image size | Multi-stage build, slim base, `.dockerignore` |
| Secret leakage in layers | Build secrets via `--secret`, non-root user |
| Health check fails on slow startup | `start-period=5s`, readiness probe |
