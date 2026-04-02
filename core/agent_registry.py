"""Registry for runtime agent instances."""

import threading
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("arcanix.core.agent_registry")


class AgentRegistry:
    """Thread-safe store that tracks running agent instances.

    Agents register themselves on start-up so that the coordinator,
    scheduler, and REST API can query and control them by name or ID.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, Any] = {}  # agent_id → agent instance
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent: Any) -> None:
        """Add *agent* to the registry.

        Args:
            agent: An instance with at least ``agent_id`` and
                ``agent_name`` attributes.
        """
        with self._lock:
            self._agents[agent.agent_id] = agent
        logger.info(
            "Registered agent '%s' (id=%s)", agent.agent_name, agent.agent_id
        )

    def unregister(self, agent_id: str) -> None:
        """Remove the agent with *agent_id* from the registry.

        Args:
            agent_id: UUID string of the agent to remove.
        """
        with self._lock:
            removed = self._agents.pop(agent_id, None)
        if removed:
            logger.info("Unregistered agent id=%s", agent_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> Optional[Any]:
        """Return the agent instance for *agent_id*, or *None*."""
        with self._lock:
            return self._agents.get(agent_id)

    def get_agent_by_name(self, name: str) -> Optional[Any]:
        """Return the first agent whose ``agent_name`` matches *name*, or *None*."""
        with self._lock:
            for agent in self._agents.values():
                if agent.agent_name == name:
                    return agent
        return None

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Return a list of status dictionaries for all registered agents."""
        with self._lock:
            agents = list(self._agents.values())
        return [agent.get_status() for agent in agents]

    def get_capabilities(self) -> Dict[str, List[str]]:
        """Return a mapping of agent_id → capabilities list.

        Agents may optionally expose a ``capabilities`` attribute.  If
        the attribute is absent an empty list is returned for that agent.
        """
        with self._lock:
            return {
                agent_id: getattr(agent, "capabilities", [])
                for agent_id, agent in self._agents.items()
            }


# Module-level singleton
registry = AgentRegistry()
