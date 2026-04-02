"""Portfolio Manager Agent — makes allocation and rebalancing recommendations."""

import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

import config
from utils.agent_utils import parse_json_response

logger = logging.getLogger("arcanix.portfolio_manager")

_SYSTEM_PROMPT = (
    "You are a seasoned portfolio manager responsible for maximising risk-adjusted "
    "returns. You base every decision on quantitative data and always output "
    "structured JSON recommendations."
)

_FALLBACK: Dict[str, Any] = {
    "action": "hold",
    "allocations": {},
    "changes": [],
    "rationale": "",
}


class PortfolioManagerAgent:
    """Makes data-driven portfolio allocation and rebalancing recommendations."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.3,
            api_key=config.OPENAI_API_KEY,
        )

    def make_recommendations(
        self,
        market_analysis: Dict[str, Any],
        portfolio_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate portfolio allocation recommendations.

        Args:
            market_analysis: Output of :class:`~agents.market_analyst.MarketAnalystAgent`.
            portfolio_metrics: Output of
                :func:`~utils.portfolio_calculator.calculate_portfolio_metrics`.

        Returns:
            Dictionary with keys:
            - ``action``: Overall recommended action ("rebalance" | "hold" | "reduce_risk")
            - ``allocations``: Symbol → suggested target weight (decimals summing to 1)
            - ``changes``: List of specific recommended trades
            - ``rationale``: Short explanation of the strategy
        """
        prompt = (
            "Based on the following market analysis and portfolio metrics, "
            "provide actionable allocation recommendations.\n\n"
            f"Market Analysis:\n{json.dumps(market_analysis, indent=2)}\n\n"
            f"Current Portfolio Metrics:\n{json.dumps(portfolio_metrics, indent=2)}\n\n"
            "Return a JSON object with these keys:\n"
            "- action: 'rebalance' | 'hold' | 'reduce_risk'\n"
            "- allocations: object where each key is a ticker and value is the "
            "suggested target weight (all weights must sum to 1.0)\n"
            "- changes: list of strings describing specific buy/sell actions\n"
            "- rationale: one-paragraph explanation\n\n"
            "Respond ONLY with valid JSON."
        )

        logger.info("Generating portfolio recommendations")
        response = self.llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

        return parse_json_response(response.content, _FALLBACK)
