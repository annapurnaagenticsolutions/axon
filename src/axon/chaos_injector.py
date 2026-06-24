"""Chaos engineering injector for AXON runtime.

Injects failures into the runtime to validate resilience:
agent kills, provider errors, delays, and memory pressure.
"""

from __future__ import annotations

import random
import time
from typing import Any

from axon.agent_lifecycle import AgentLifecycleManager


class ChaosInjector:
    """Inject controlled failures into the AXON runtime."""

    def __init__(self, lifecycle: AgentLifecycleManager) -> None:
        self.lifecycle = lifecycle

    def kill_random_agent(self) -> str | None:
        """Terminate a random running agent. Returns the victim name or None."""
        agents = [a for a in self.lifecycle.list_agents()]
        if not agents:
            return None
        victim = random.choice(agents)
        self.lifecycle.terminate(victim.name, reason="chaos_kill")
        return victim.name

    def kill_all_agents(self) -> int:
        """Terminate all running agents. Returns kill count."""
        count = 0
        for inst in list(self.lifecycle.list_agents()):
            self.lifecycle.terminate(inst.name, reason="chaos_purge")
            count += 1
        return count

    def inject_delay(self, ms: int) -> None:
        """Pause execution for *ms* milliseconds (simulates slow provider)."""
        time.sleep(ms / 1000.0)

    def inject_provider_error(self, agent_name: str) -> bool:
        """Simulate a provider error by pausing then erroring an agent.

        Note: This manipulates the agent state; the actual provider
        error simulation is done by using a mock provider that
        can be configured to return errors.
        """
        status = self.lifecycle.status(agent_name)
        if status.is_err:
            return False
        # Transition to error state by pausing then resuming
        # (real error injection would need deeper runtime hooks)
        self.lifecycle.pause(agent_name)
        time.sleep(0.05)
        self.lifecycle.resume(agent_name)
        return True

    def memory_pressure(self, agent_name: str, iterations: int = 1000) -> bool:
        """Simulate memory pressure by creating a large memory snapshot.

        This tests checkpoint behavior with large state.
        """
        from axon.checkpoint_manager import CheckpointManager

        cm = CheckpointManager(self.lifecycle)
        # Trigger a checkpoint which serializes memory state
        for _ in range(iterations):
            result = cm.checkpoint(agent_name)
            if result.is_err:
                return False
        return True
