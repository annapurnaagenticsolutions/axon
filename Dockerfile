# AXON Runtime — Production Dockerfile
# Multi-stage build with security hardening

# ---------------------------------------------------------------------------
# Build stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security: create non-root user
RUN groupadd -r axon && \
    useradd -r -g axon -u 10001 -s /sbin/nologin -d /app axon

WORKDIR /app

# Install runtime dependencies and the built wheel
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl[serve,db] && \
    rm -rf /tmp/*.whl /root/.cache

# Switch to non-root user
USER axon

# Expose API port
EXPOSE 8000

# Health check using the built-in /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command: start the API server
CMD ["axon", "serve-api", "--host", "0.0.0.0", "--port", "8000"]
