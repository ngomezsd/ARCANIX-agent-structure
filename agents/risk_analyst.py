"""Risk Analyst Agent — assesses portfolio risk and flags compliance concerns."""

import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

import config
from utils.agent_utils import parse_json_response

logger = logging.getLogger("arcanix.risk_analyst")

_SYSTEM_PROMPT = (
    "You are a rigorous risk analyst specialising in investment portfolio risk "
    "management. You assess market, concentration, and volatility risks, and "
    "always output structured JSON reports."
)

_FALLBACK: Dict[str, Any] = {
    "risk_level": "medium",
    "risk_score": 5,
    "concentration_risk": "",
    "volatility_concerns": [],
    "mitigation_strategies": [],
    "compliance_flags": [],
}


class RiskAnalystAgent:
    """Evaluates portfolio risk across multiple dimensions."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.2,
            api_key=config.OPENAI_API_KEY,
        )

    def assess_risk(
        self,
        portfolio_metrics: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assess the risk profile of the current portfolio.

        Args:
            portfolio_metrics: Output of
                :func:`~utils.portfolio_calculator.calculate_portfolio_metrics`.
            market_data: Output of
                :func:`~utils.data_fetcher.get_market_summary`.

        Returns:
            Dictionary with keys:
            - ``risk_level``: "low" | "medium" | "high"
            - ``risk_score``: Integer 1–10 (10 = highest risk)
            - ``concentration_risk``: Description of concentration concerns
            - ``volatility_concerns``: List of volatility-related flags
            - ``mitigation_strategies``: List of recommended mitigations
            - ``compliance_flags``: List of compliance issues (may be empty)
        """
        prompt = (
            "Assess the risk profile of the following investment portfolio.\n\n"
            f"Portfolio Metrics:\n{json.dumps(portfolio_metrics, indent=2)}\n\n"
            f"Market Data:\n{json.dumps(market_data, indent=2)}\n\n"
            "Return a JSON object with these keys:\n"
            "- risk_level: 'low' | 'medium' | 'high'\n"
            "- risk_score: integer from 1 (lowest) to 10 (highest)\n"
            "- concentration_risk: string describing concentration concerns\n"
            "- volatility_concerns: list of strings\n"
            "- mitigation_strategies: list of recommended actions\n"
            "- compliance_flags: list of any compliance issues (empty list if none)\n\n"
            "Respond ONLY with valid JSON."
        )

        logger.info("Assessing portfolio risk")
        response = self.llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

        return parse_json_response(response.content, _FALLBACK)
