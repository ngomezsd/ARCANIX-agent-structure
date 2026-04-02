"""Entry point — starts the ARCANIX REST API server."""

import json
import sys

from storage.database import db
from core.event_bus import event_bus
from core.agent_registry import registry
from core.coordinator import AgentCoordinator, set_coordinator

from agents.market_monitor import MarketMonitorAgent
from agents.risk_manager import RiskManagerAgent
from agents.portfolio_optimizer import PortfolioOptimizerAgent
from agents.opportunity_scout import OpportunityScoutAgent
from agents.reporter import ReporterAgent

from api.app import create_app
from utils.logger import get_logger

logger = get_logger("arcanix.run_api")


def load_config(path: str) -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning("Config not found at %s — using defaults.", path)
        return {}


def main() -> None:
    logger.info("=" * 60)
    logger.info("ARCANIX REST API — Starting")
    logger.info("=" * 60)

    # Initialise SQLite storage
    db.initialize()

    # Load configs
    agent_cfg = load_config("config/agent_config.json")
    api_cfg = load_config("config/api_config.json")

    # Start event bus
    event_bus.start()

    # Build agents
    mm_cfg = agent_cfg.get("market_monitor", {})
    rm_cfg = agent_cfg.get("risk_manager", {})
    po_cfg = agent_cfg.get("portfolio_optimizer", {})
    os_cfg = agent_cfg.get("opportunity_scout", {})
    rp_cfg = agent_cfg.get("reporter", {})

    agents = [
        MarketMonitorAgent(
            event_bus=event_bus,
            symbols=mm_cfg.get("symbols"),
            interval=mm_cfg.get("interval_seconds", 300),
        ),
        RiskManagerAgent(
            event_bus=event_bus,
            risk_threshold=rm_cfg.get("risk_threshold", 7),
            interval=rm_cfg.get("interval_seconds", 60),
        ),
        PortfolioOptimizerAgent(
            event_bus=event_bus,
            interval=po_cfg.get("interval_seconds", 600),
        ),
        OpportunityScoutAgent(
            event_bus=event_bus,
            rsi_oversold_threshold=os_cfg.get("rsi_oversold_threshold", 35),
            interval=os_cfg.get("interval_seconds", 300),
        ),
        ReporterAgent(
            event_bus=event_bus,
            interval=rp_cfg.get("interval_seconds", 900),
        ),
    ]

    # Wire coordinator
    coordinator = AgentCoordinator(event_bus=event_bus, registry=registry)
    for agent in agents:
        coordinator.add_agent(agent)
    set_coordinator(coordinator)

    # Start all agents in background threads
    coordinator.start_all()
    logger.info("All agents started.")

    # Create Flask app
    flask_config = {
        "SECRET_KEY": api_cfg.get("secret_key", "arcanix-dev-secret-key"),
        "DEBUG": api_cfg.get("debug", False),
    }
    app = create_app(config=flask_config)

    host = api_cfg.get("host", "0.0.0.0")
    port = api_cfg.get("port", 5000)
    debug = api_cfg.get("debug", False)

    logger.info("Starting Flask server on %s:%d (debug=%s)", host, port, debug)
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — stopping agents …")
        coordinator.stop_all()
        event_bus.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
