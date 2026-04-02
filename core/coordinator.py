"""AgentCoordinator — orchestrates the full analysis workflow."""

import time
import threading
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("arcanix.core.coordinator")

_MAX_RETRIES = 3
_WAIT_TIMEOUT = 30  # seconds to wait for analysis results
_EVENT_PROCESSING_DELAY = 2  # seconds to let event handlers propagate


class AgentCoordinator:
    """Orchestrates agent start/stop and drives on-demand analysis cycles.

    Args:
        event_bus: Shared :class:`EventBus` instance.
        registry: Shared :class:`AgentRegistry` instance.
    """

    def __init__(self, event_bus: Any, registry: Any) -> None:
        self._event_bus = event_bus
        self._registry = registry
        self._agents: Dict[str, Any] = {}  # name → agent instance

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    def add_agent(self, agent: Any) -> None:
        """Register *agent* with the coordinator and the registry."""
        self._agents[agent.agent_name] = agent
        self._registry.register(agent)

    def start_all(self) -> None:
        """Start every registered agent."""
        for name, agent in self._agents.items():
            try:
                agent.start()
                logger.info("Started agent '%s'", name)
            except Exception as exc:
                logger.error("Failed to start agent '%s': %s", name, exc)

    def stop_all(self) -> None:
        """Stop every registered agent."""
        for name, agent in self._agents.items():
            try:
                agent.stop()
                logger.info("Stopped agent '%s'", name)
            except Exception as exc:
                logger.error("Failed to stop agent '%s': %s", name, exc)

    def start_agent(self, agent_name: str) -> bool:
        """Start a specific agent by name.

        Returns:
            ``True`` if the agent was found and started, ``False`` otherwise.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            logger.warning("Agent '%s' not found.", agent_name)
            return False
        agent.start()
        return True

    def stop_agent(self, agent_name: str) -> bool:
        """Stop a specific agent by name.

        Returns:
            ``True`` if the agent was found and stopped, ``False`` otherwise.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            logger.warning("Agent '%s' not found.", agent_name)
            return False
        agent.stop()
        return True

    def get_status(self) -> List[Dict[str, Any]]:
        """Return status dictionaries for all managed agents."""
        return [agent.get_status() for agent in self._agents.values()]

    # ------------------------------------------------------------------
    # On-demand analysis
    # ------------------------------------------------------------------

    def run_analysis(
        self,
        portfolio: Optional[Dict[str, float]] = None,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run a complete analysis cycle and return collected results.

        Steps:
        1. Push the portfolio to the risk manager and optimizer.
        2. Trigger the market monitor to fetch fresh data.
        3. Wait up to :data:`_WAIT_TIMEOUT` seconds for results.
        4. Collect outputs from each agent.

        The cycle is retried up to :data:`_MAX_RETRIES` times on failure.

        Args:
            portfolio: Mapping of symbol → dollar value (optional).
            symbols: Ticker symbols to analyse (optional; falls back to
                the market monitor's configured symbols).

        Returns:
            Dict with keys: ``market_data``, ``risk_assessment``,
            ``recommendation``, ``opportunities``, ``report``.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return self._do_analysis(portfolio, symbols)
            except Exception as exc:
                logger.error(
                    "Analysis attempt %d/%d failed: %s",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(2)
        return {"error": "Analysis failed after all retries."}

    def _do_analysis(
        self,
        portfolio: Optional[Dict[str, float]],
        symbols: Optional[List[str]],
    ) -> Dict[str, Any]:
        # Push portfolio to relevant agents
        risk_agent = self._agents.get("risk_manager")
        optimizer = self._agents.get("portfolio_optimizer")
        if portfolio:
            if risk_agent:
                risk_agent.portfolio = portfolio
            if optimizer:
                pass  # optimizer derives its own suggestions from market data

        # Override symbols on the market monitor if provided
        monitor = self._agents.get("market_monitor")
        if monitor and symbols:
            monitor.symbols = symbols

        # Manually trigger one market-data cycle (synchronous)
        results: Dict[str, Any] = {}
        if monitor:
            monitor.run_cycle()
            time.sleep(1)  # brief pause to let event handlers fire
            results["market_data"] = monitor.get_latest_data()

        # Give downstream agents a moment to process events
        time.sleep(_EVENT_PROCESSING_DELAY)

        if risk_agent:
            risk_agent.run_cycle()
            results["risk_assessment"] = risk_agent.get_latest_assessment()

        if optimizer:
            optimizer.run_cycle()
            results["recommendation"] = optimizer.get_latest_recommendation()

        scout = self._agents.get("opportunity_scout")
        if scout:
            scout.run_cycle()
            results["opportunities"] = scout.get_latest_opportunities()

        reporter = self._agents.get("reporter")
        if reporter:
            reporter.run_cycle()
            results["report"] = reporter.get_latest_report()

        return results


# Module-level singleton (lazily initialised by run_api.py / run_agents.py)
_coordinator_instance: Optional[AgentCoordinator] = None


def get_coordinator() -> Optional[AgentCoordinator]:
    """Return the module-level coordinator singleton (may be *None*)."""
    return _coordinator_instance


def set_coordinator(instance: AgentCoordinator) -> None:
    """Set the module-level coordinator singleton."""
    global _coordinator_instance
    _coordinator_instance = instance
