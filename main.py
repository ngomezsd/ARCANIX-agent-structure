"""ARCANIX Investment Fund Multi-Agent System — orchestration entry point.

Run:
    python main.py

Environment:
    Requires a valid .env file.  Copy .env.example → .env and fill in your
    OPENAI_API_KEY before running.
"""

import json
import logging
from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph

import config  # noqa: F401 — triggers env validation early
from agents.market_analyst import MarketAnalystAgent
from agents.portfolio_manager import PortfolioManagerAgent
from agents.reporting import ReportingAgent
from agents.risk_analyst import RiskAnalystAgent
from utils.data_fetcher import get_market_summary
from utils.portfolio_calculator import calculate_portfolio_metrics

logger = logging.getLogger("arcanix.main")


# ---------------------------------------------------------------------------
# Shared workflow state
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict):
    """State passed between LangGraph nodes."""

    portfolio: Dict[str, float]
    symbols: list
    market_data: Dict[str, Any]
    portfolio_metrics: Dict[str, Any]
    market_analysis: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    recommendations: Dict[str, Any]
    report: str


# ---------------------------------------------------------------------------
# Agent instances (created once at module level)
# ---------------------------------------------------------------------------

_market_analyst = MarketAnalystAgent()
_portfolio_manager = PortfolioManagerAgent()
_risk_analyst = RiskAnalystAgent()
_reporter = ReportingAgent()


# ---------------------------------------------------------------------------
# Workflow node functions
# ---------------------------------------------------------------------------

def node_fetch_market_data(state: WorkflowState) -> WorkflowState:
    """Fetch real-time market data and compute technical indicators."""
    print("\n📊  Fetching market data ...")
    market_data = get_market_summary(state["symbols"], period=config.DATA_PERIOD)
    return {**state, "market_data": market_data}


def node_calculate_metrics(state: WorkflowState) -> WorkflowState:
    """Compute portfolio-level metrics (Sharpe, VaR, diversification …)."""
    print("💼  Calculating portfolio metrics ...")
    metrics = calculate_portfolio_metrics(
        state["portfolio"],
        state["market_data"],
        risk_free_rate=config.RISK_FREE_RATE,
    )
    return {**state, "portfolio_metrics": metrics}


def node_market_analysis(state: WorkflowState) -> WorkflowState:
    """Market Analyst Agent: interpret technical indicators."""
    print("🔍  Running market analysis ...")
    analysis = _market_analyst.analyze_market(state["market_data"])
    return {**state, "market_analysis": analysis}


def node_risk_assessment(state: WorkflowState) -> WorkflowState:
    """Risk Analyst Agent: assess portfolio risk."""
    print("⚠️   Assessing portfolio risk ...")
    assessment = _risk_analyst.assess_risk(
        state["portfolio_metrics"], state["market_data"]
    )
    return {**state, "risk_assessment": assessment}


def node_recommendations(state: WorkflowState) -> WorkflowState:
    """Portfolio Manager Agent: generate rebalancing recommendations."""
    print("📈  Generating recommendations ...")
    recs = _portfolio_manager.make_recommendations(
        state["market_analysis"], state["portfolio_metrics"]
    )
    return {**state, "recommendations": recs}


def node_generate_report(state: WorkflowState) -> WorkflowState:
    """Reporting Agent: compile a comprehensive investment report."""
    print("📋  Generating investment report ...")
    report = _reporter.generate_report(
        state["market_analysis"],
        state["recommendations"],
        state["risk_assessment"],
        state["portfolio_metrics"],
    )
    return {**state, "report": report}


# ---------------------------------------------------------------------------
# LangGraph workflow builder
# ---------------------------------------------------------------------------

def build_workflow() -> Any:
    """Assemble and compile the LangGraph multi-agent workflow.

    The execution order is:
        fetch_market_data → calculate_metrics → market_analysis
        → risk_assessment → recommendations → generate_report → END
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("fetch_market_data", node_fetch_market_data)
    graph.add_node("calculate_metrics", node_calculate_metrics)
    graph.add_node("market_analysis", node_market_analysis)
    graph.add_node("risk_assessment", node_risk_assessment)
    graph.add_node("recommendations", node_recommendations)
    graph.add_node("generate_report", node_generate_report)

    graph.set_entry_point("fetch_market_data")
    graph.add_edge("fetch_market_data", "calculate_metrics")
    graph.add_edge("calculate_metrics", "market_analysis")
    graph.add_edge("market_analysis", "risk_assessment")
    graph.add_edge("risk_assessment", "recommendations")
    graph.add_edge("recommendations", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full investment fund analysis workflow."""

    # ── Portfolio configuration ────────────────────────────────────────────
    # Edit these values to match your actual portfolio holdings.
    # Keys are ticker symbols; values are dollar amounts invested.
    portfolio: Dict[str, float] = {
        "AAPL": 10_000,
        "MSFT": 15_000,
        "GOOGL": 12_000,
        "TSLA": 8_000,
    }

    print("=" * 60)
    print(f"🏦  {config.FUND_NAME.upper()}")
    print("    ARCANIX Multi-Agent Investment Analysis")
    print("=" * 60)

    workflow = build_workflow()

    initial_state: WorkflowState = {
        "portfolio": portfolio,
        "symbols": list(portfolio.keys()),
        "market_data": {},
        "portfolio_metrics": {},
        "market_analysis": {},
        "risk_assessment": {},
        "recommendations": {},
        "report": "",
    }

    final_state: WorkflowState = workflow.invoke(initial_state)

    # ── Display results ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📊  FINAL INVESTMENT REPORT")
    print("=" * 60)
    print(final_state["report"])

    # ── Save report to file ────────────────────────────────────────────────
    output_file = "investment_report.md"
    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write(final_state["report"])

    print(f"\n✅  Report saved to {output_file}")

    # ── Print quick portfolio summary ──────────────────────────────────────
    metrics = final_state["portfolio_metrics"]
    print("\n📌  Portfolio Snapshot")
    print(f"    Total Value  : ${metrics.get('total_value', 0):,.2f}")
    print(f"    Sharpe Ratio : {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"    Daily VaR 95%: ${metrics.get('value_at_risk_95', 0):,.2f}")
    print(f"    Diversif. Score: {metrics.get('diversification_score', 0):.1f}/10")


if __name__ == "__main__":
    main()
