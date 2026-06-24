"""Health check endpoint for AXON runtime.

Provides an HTTP health endpoint that reports agent status, memory usage,
and readiness for load balancers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from axon.agent_lifecycle import AgentLifecycleManager, AgentStatus


@dataclass
class HealthReport:
    """Health status report for the AXON runtime."""

    status: str  # "healthy", "degraded", "unhealthy"
    uptime_seconds: float
    agent_count: int
    running_agents: int
    paused_agents: int
    error_agents: int
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "agents": {
                "total": self.agent_count,
                "running": self.running_agents,
                "paused": self.paused_agents,
                "error": self.error_agents,
            },
            "checks": self.checks,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class HealthChecker:
    """Monitors AXON runtime health."""

    def __init__(
        self,
        lifecycle: AgentLifecycleManager | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self._start_time = time.time()

    def check(self) -> HealthReport:
        """Run all health checks and return a report."""
        checks: dict[str, Any] = {}
        status = "healthy"

        agent_count = 0
        running = 0
        paused = 0
        error = 0

        if self.lifecycle is not None:
            agents = self.lifecycle.list_agents()
            agent_count = len(agents)
            running = sum(1 for a in agents if a.status == AgentStatus.RUNNING)
            paused = sum(1 for a in agents if a.status == AgentStatus.PAUSED)
            error = sum(1 for a in agents if a.status == AgentStatus.ERROR)
            checks["lifecycle"] = "ok"
        else:
            checks["lifecycle"] = "not_configured"

        if error > 0:
            status = "degraded"
        if agent_count > 0 and running == 0 and error > 0:
            status = "unhealthy"

        return HealthReport(
            status=status,
            uptime_seconds=time.time() - self._start_time,
            agent_count=agent_count,
            running_agents=running,
            paused_agents=paused,
            error_agents=error,
            checks=checks,
        )
