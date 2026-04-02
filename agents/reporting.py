"""Reporting Agent — compiles all analyses into a professional fund report."""

import json
import logging
from datetime import date
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

import config

logger = logging.getLogger("arcanix.reporting")

_SYSTEM_PROMPT = (
    "You are a senior financial reporting specialist. You write clear, professional "
    "investment reports suitable for fund managers and institutional investors. "
    "Your reports are well-structured, data-driven, and include actionable insights."
)


class ReportingAgent:
    """Generates comprehensive, executive-quality investment fund reports."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.5,
            api_key=config.OPENAI_API_KEY,
        )

    def generate_report(
        self,
        market_analysis: Dict[str, Any],
        recommendations: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        portfolio_metrics: Dict[str, Any],
    ) -> str:
        """Produce a narrative investment report.

        Args:
            market_analysis: Output of :class:`~agents.market_analyst.MarketAnalystAgent`.
            recommendations: Output of :class:`~agents.portfolio_manager.PortfolioManagerAgent`.
            risk_assessment: Output of :class:`~agents.risk_analyst.RiskAnalystAgent`.
            portfolio_metrics: Output of
                :func:`~utils.portfolio_calculator.calculate_portfolio_metrics`.

        Returns:
            A formatted markdown string containing the full investment report.
        """
        report_date = date.today().isoformat()

        prompt = (
            f"Generate a professional investment fund report dated {report_date} "
            f"for **{config.FUND_NAME}**.\n\n"
            "Use the following data sources:\n\n"
            f"### Market Analysis\n{json.dumps(market_analysis, indent=2)}\n\n"
            f"### Portfolio Metrics\n{json.dumps(portfolio_metrics, indent=2)}\n\n"
            f"### Risk Assessment\n{json.dumps(risk_assessment, indent=2)}\n\n"
            f"### Portfolio Recommendations\n{json.dumps(recommendations, indent=2)}\n\n"
            "Structure the report with these sections:\n"
            "1. Executive Summary\n"
            "2. Market Overview\n"
            "3. Portfolio Performance & Metrics\n"
            "4. Risk Assessment\n"
            "5. Recommendations & Action Plan\n"
            "6. Conclusion\n\n"
            "Use markdown formatting. Be concise but comprehensive."
        )

        logger.info("Generating investment report for %s", config.FUND_NAME)
        response = self.llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

        return response.content
