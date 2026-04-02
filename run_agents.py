"""Entry point — starts the ARCANIX multi-agent system."""

import json
import signal
import sys
import time

from core.event_bus import event_bus
from core.agent_registry import registry
from core.coordinator import AgentCoordinator, set_coordinator
from core.scheduler import scheduler
from storage.database import db

from agents.market_monitor import MarketMonitorAgent
from agents.risk_manager import RiskManagerAgent
from agents.portfolio_optimizer import PortfolioOptimizerAgent
from agents.opportunity_scout import OpportunityScoutAgent
from agents.reporter import ReporterAgent

from utils.logger import get_logger

logger = get_logger("arcanix.run_agents")


def load_config(path: str = "config/agent_config.json") -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning("Config file not found at %s — using defaults.", path)
        return {}


def build_agents(cfg: dict, eb: object) -> list:
    """Instantiate all agents from configuration."""
    mm_cfg = cfg.get("market_monitor", {})
    rm_cfg = cfg.get("risk_manager", {})
    po_cfg = cfg.get("portfolio_optimizer", {})
    os_cfg = cfg.get("opportunity_scout", {})
    rp_cfg = cfg.get("reporter", {})

    agents = []

    if mm_cfg.get("enabled", True):
        agents.append(
            MarketMonitorAgent(
                event_bus=eb,
                symbols=mm_cfg.get("symbols"),
                interval=mm_cfg.get("interval_seconds", 300),
            )
        )

    if rm_cfg.get("enabled", True):
        agents.append(
            RiskManagerAgent(
                event_bus=eb,
                risk_threshold=rm_cfg.get("risk_threshold", 7),
                interval=rm_cfg.get("interval_seconds", 60),
            )
        )

    if po_cfg.get("enabled", True):
        agents.append(
            PortfolioOptimizerAgent(
                event_bus=eb,
                interval=po_cfg.get("interval_seconds", 600),
            )
        )

    if os_cfg.get("enabled", True):
        agents.append(
            OpportunityScoutAgent(
                event_bus=eb,
                rsi_oversold_threshold=os_cfg.get("rsi_oversold_threshold", 35),
                interval=os_cfg.get("interval_seconds", 300),
            )
        )

    if rp_cfg.get("enabled", True):
        agents.append(
            ReporterAgent(
                event_bus=eb,
                interval=rp_cfg.get("interval_seconds", 900),
            )
        )

    return agents


def load_task_config(path: str = "config/task_config.json") -> list:
    try:
        with open(path) as fh:
            return json.load(fh).get("tasks", [])
    except FileNotFoundError:
        return []


def main() -> None:
    logger.info("=" * 60)
    logger.info("ARCANIX Multi-Agent Investment System — Starting")
    logger.info("=" * 60)

    # Initialise storage
    db.initialize()

    # Load config
    cfg = load_config()

    # Start event bus
    event_bus.start()
    logger.info("Event bus started.")

    # Build agents
    agents = build_agents(cfg, event_bus)

    # Create coordinator and register agents
    coordinator = AgentCoordinator(event_bus=event_bus, registry=registry)
    for agent in agents:
        coordinator.add_agent(agent)
    set_coordinator(coordinator)

    # Start all agents
    coordinator.start_all()
    logger.info("All agents started.")

    # Set up scheduler for periodic task execution
    task_configs = load_task_config()
    agent_map = {a.agent_name: a for a in agents}
    for task in task_configs:
        if not task.get("enabled", True):
            continue
        agent_name = task.get("agent")
        agent = agent_map.get(agent_name)
        if agent is None:
            continue
        scheduler.add_task(
            name=task["name"],
            func=agent.run_cycle,
            interval_seconds=task["interval_seconds"],
        )
    scheduler.start()
    logger.info("Scheduler started with %d task(s).", len(scheduler.get_tasks()))

    # Graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Shutdown signal received — stopping agents …")
        coordinator.stop_all()
        scheduler.stop()
        event_bus.stop()
        logger.info("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("System running. Press Ctrl+C to stop.")
    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()
