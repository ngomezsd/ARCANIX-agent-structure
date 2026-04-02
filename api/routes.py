"""REST API route definitions for the ARCANIX multi-agent system."""

import uuid
from typing import Any

from flask import Blueprint, jsonify, request

from api.models import error_response, success_response
from core.event_bus import event_bus
from core.agent_registry import registry
from core.coordinator import get_coordinator
from storage.portfolio_store import portfolio_store
from storage.results_store import results_store
from utils.logger import get_logger

logger = get_logger("arcanix.api.routes")

api_blueprint = Blueprint("api", __name__, url_prefix="/api")


# ======================================================================
# Agent Management
# ======================================================================


@api_blueprint.route("/agents/start", methods=["POST"])
def start_agents() -> Any:
    """Start one or all agents.

    Body (optional):
        ``{"agent_name": "market_monitor"}``  — start a single agent.
        ``{}`` or omitted — start all agents.
    """
    try:
        coordinator = get_coordinator()
        if coordinator is None:
            return jsonify(error_response("Coordinator not initialised.", 503)), 503

        body = request.get_json(silent=True) or {}
        agent_name = body.get("agent_name")

        if agent_name:
            ok = coordinator.start_agent(agent_name)
            if not ok:
                return (
                    jsonify(error_response(f"Agent '{agent_name}' not found.", 404)),
                    404,
                )
            return jsonify(
                success_response(
                    {"agent_name": agent_name, "status": "started"},
                    f"Agent '{agent_name}' started.",
                )
            )

        coordinator.start_all()
        return jsonify(
            success_response(coordinator.get_status(), "All agents started.")
        )
    except Exception as exc:
        logger.error("start_agents error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


@api_blueprint.route("/agents/stop", methods=["POST"])
def stop_agents() -> Any:
    """Stop one or all agents.

    Body (optional):
        ``{"agent_name": "risk_manager"}``  — stop a single agent.
        ``{}`` or omitted — stop all agents.
    """
    try:
        coordinator = get_coordinator()
        if coordinator is None:
            return jsonify(error_response("Coordinator not initialised.", 503)), 503

        body = request.get_json(silent=True) or {}
        agent_name = body.get("agent_name")

        if agent_name:
            ok = coordinator.stop_agent(agent_name)
            if not ok:
                return (
                    jsonify(error_response(f"Agent '{agent_name}' not found.", 404)),
                    404,
                )
            return jsonify(
                success_response(
                    {"agent_name": agent_name, "status": "stopped"},
                    f"Agent '{agent_name}' stopped.",
                )
            )

        coordinator.stop_all()
        return jsonify(
            success_response(coordinator.get_status(), "All agents stopped.")
        )
    except Exception as exc:
        logger.error("stop_agents error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


@api_blueprint.route("/agents/status", methods=["GET"])
def agent_status() -> Any:
    """Return status for all registered agents."""
    try:
        return jsonify(success_response(registry.get_all_agents()))
    except Exception as exc:
        logger.error("agent_status error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


@api_blueprint.route("/agents/<agent_id>/logs", methods=["GET"])
def agent_logs(agent_id: str) -> Any:
    """Return recent log entries for a specific agent.

    Query params:
        ``limit`` (int, default 50) — number of log entries to return.
    """
    try:
        limit = int(request.args.get("limit", 50))
        agent = registry.get_agent(agent_id)
        if agent is None:
            return (
                jsonify(error_response(f"Agent '{agent_id}' not found.", 404)),
                404,
            )
        logs = agent.logs[-limit:]
        return jsonify(
            success_response(
                {"agent_id": agent_id, "logs": logs, "count": len(logs)}
            )
        )
    except Exception as exc:
        logger.error("agent_logs error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


# ======================================================================
# Analysis
# ======================================================================


@api_blueprint.route("/analysis/run", methods=["POST"])
def run_analysis() -> Any:
    """Trigger a full analysis cycle.

    Body:
        ``{"portfolio": {"AAPL": 10000}, "symbols": ["AAPL"]}``

    Returns a ``job_id`` immediately; results are stored asynchronously.
    """
    try:
        coordinator = get_coordinator()
        if coordinator is None:
            return jsonify(error_response("Coordinator not initialised.", 503)), 503

        body = request.get_json(silent=True) or {}
        portfolio = body.get("portfolio")
        symbols = body.get("symbols")

        job_id = str(uuid.uuid4())
        results = coordinator.run_analysis(portfolio=portfolio, symbols=symbols)

        # Persist results
        for key, value in results.items():
            if value is not None:
                try:
                    results_store.save_result(key, value)
                except Exception as store_exc:
                    logger.warning("Could not persist '%s': %s", key, store_exc)

        return jsonify(
            success_response(
                {"job_id": job_id, "results": results},
                "Analysis completed.",
            )
        )
    except Exception as exc:
        logger.error("run_analysis error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


@api_blueprint.route("/analysis/results", methods=["GET"])
def analysis_results() -> Any:
    """Return stored analysis results.

    Query params:
        ``type`` (str, optional) — filter by result type.
        ``limit`` (int, default 10) — number of results to return.
    """
    try:
        result_type = request.args.get("type")
        limit = int(request.args.get("limit", 10))

        if result_type:
            data = results_store.get_results(result_type, limit=limit)
        else:
            data = results_store.get_all_latest()

        return jsonify(success_response(data))
    except Exception as exc:
        logger.error("analysis_results error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


# ======================================================================
# Portfolio
# ======================================================================


@api_blueprint.route("/portfolio/metrics", methods=["GET"])
def portfolio_metrics() -> Any:
    """Return the latest portfolio metrics from the results store."""
    try:
        result = results_store.get_latest_result("risk_assessment")
        portfolio = portfolio_store.get_portfolio()
        portfolio_metrics = None
        if result:
            portfolio_metrics = result.get("data", {}).get("portfolio_metrics")
        return jsonify(
            success_response(
                {
                    "portfolio": portfolio,
                    "metrics": portfolio_metrics,
                    "risk_assessment": result,
                }
            )
        )
    except Exception as exc:
        logger.error("portfolio_metrics error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


@api_blueprint.route("/portfolio/update", methods=["POST"])
def update_portfolio() -> Any:
    """Update the stored portfolio.

    Body:
        ``{"portfolio": {"AAPL": 10000, "MSFT": 15000}}``
    """
    try:
        body = request.get_json(silent=True) or {}
        portfolio = body.get("portfolio")
        if not isinstance(portfolio, dict) or not portfolio:
            return (
                jsonify(error_response("'portfolio' must be a non-empty dict.")),
                400,
            )
        portfolio_store.save_portfolio(portfolio)
        return jsonify(
            success_response(
                {"portfolio": portfolio}, "Portfolio updated successfully."
            )
        )
    except Exception as exc:
        logger.error("update_portfolio error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


# ======================================================================
# Events
# ======================================================================


@api_blueprint.route("/events", methods=["GET"])
def get_events() -> Any:
    """Return recent events from the event bus history.

    Query params:
        ``limit`` (int, default 50)
    """
    try:
        limit = int(request.args.get("limit", 50))
        events = event_bus.get_event_history(limit=limit)
        return jsonify(success_response({"events": events, "count": len(events)}))
    except Exception as exc:
        logger.error("get_events error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500


# ======================================================================
# Health
# ======================================================================


@api_blueprint.route("/health", methods=["GET"])
def health() -> Any:
    """Return system health status."""
    try:
        coordinator = get_coordinator()
        agent_statuses = coordinator.get_status() if coordinator else []
        running = [a for a in agent_statuses if a.get("status") == "running"]
        return jsonify(
            success_response(
                {
                    "system": "ok",
                    "coordinator": coordinator is not None,
                    "agents_total": len(agent_statuses),
                    "agents_running": len(running),
                    "agent_statuses": agent_statuses,
                },
                "System is healthy.",
            )
        )
    except Exception as exc:
        logger.error("health error: %s", exc)
        return jsonify(error_response("An internal error occurred.", 500)), 500
