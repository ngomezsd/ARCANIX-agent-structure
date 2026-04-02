"""Market Analyst Agent — analyses market data and provides stock insights."""

import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

import config
from utils.agent_utils import parse_json_response

logger = logging.getLogger("arcanix.market_analyst")

_SYSTEM_PROMPT = (
    "You are an expert financial market analyst with deep knowledge of technical "
    "analysis, macroeconomics, and equity markets. You provide concise, data-driven "
    "analysis and always structure your response as valid JSON."
)

_FALLBACK: Dict[str, Any] = {
    "overall_sentiment": "neutral",
    "stocks": {},
    "summary": "",
}


class MarketAnalystAgent:
    """Analyses technical indicators and market trends using an LLM."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.3,
            api_key=config.OPENAI_API_KEY,
        )

    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse market data and return structured insights.

        Args:
            market_data: Dictionary of symbol → technical indicator data as
                returned by :func:`~utils.data_fetcher.get_market_summary`.

        Returns:
            Dictionary with keys:
            - ``overall_sentiment``: "bullish" | "neutral" | "bearish"
            - ``stocks``: Per-symbol analysis (trend, signal, key_observations)
            - ``summary``: Short executive summary string
        """
        prompt = (
            "Analyse the following market data and provide investment insights.\n\n"
            f"Market Data:\n{json.dumps(market_data, indent=2)}\n\n"
            "Return a JSON object with these keys:\n"
            "- overall_sentiment: 'bullish', 'neutral', or 'bearish'\n"
            "- stocks: object where each key is a ticker and the value contains:\n"
            "    - trend: 'bullish' | 'neutral' | 'bearish'\n"
            "    - signal: 'buy' | 'hold' | 'sell'\n"
            "    - key_observations: list of 2–3 short bullet points\n"
            "- summary: one-paragraph executive summary\n\n"
            "Respond ONLY with valid JSON."
        )

        logger.info("Running market analysis for %d symbols", len(market_data))
        response = self.llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

        return parse_json_response(response.content, _FALLBACK)
