"""Small & Micro-Cap Scout Agent — discovers and analyses opportunities.

This agent specialises in identifying undervalued small-cap and micro-cap
stocks across US and European markets.  It combines systematic screening
(fundamentals + technicals) with an LLM-driven narrative analysis layer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

import config
from utils.agent_utils import parse_json_response
from utils.screener import fetch_fundamentals, get_universe, screen_stocks, score_opportunity

logger = logging.getLogger("arcanix.smallcap_scout")

_SYSTEM_PROMPT = (
    "You are a specialist investment analyst focused exclusively on small-cap and "
    "micro-cap stocks in the US and European markets. You have deep expertise in "
    "identifying undervalued growth companies before they gain mainstream attention. "
    "You always structure your analysis as valid JSON and provide actionable insights."
)

_ANALYSIS_FALLBACK: Dict[str, Any] = {
    "investment_thesis": "",
    "key_catalysts": [],
    "key_risks": [],
    "entry_strategy": "",
    "target_price_rationale": "",
    "comparable_companies": [],
    "recommendation": "WATCH",
    "conviction": "medium",
}

_REPORT_FALLBACK: Dict[str, Any] = {
    "title": "Small/Micro-Cap Opportunity Report",
    "executive_summary": "",
    "top_picks": [],
    "market_context": "",
    "risk_warnings": [],
}

_COMPARISON_FALLBACK: Dict[str, Any] = {
    "best_value": "",
    "best_growth": "",
    "best_overall": "",
    "comparative_analysis": "",
    "recommendation": [],
}


class SmallCapScoutAgent:
    """Identifies and analyses small/micro-cap stock opportunities.

    Combines quantitative screening (via :mod:`utils.screener`) with
    LLM-generated qualitative analysis to produce actionable opportunity
    reports and individual stock deep-dives.
    """

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.3,
            api_key=config.OPENAI_API_KEY,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_opportunities(
        self,
        market: str = "US",
        cap_type: str = "small",
        sector: Optional[str] = None,
        min_growth: Optional[float] = None,
        strategy: Optional[str] = None,
        extra_tickers: Optional[List[str]] = None,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Screen the market and return the top-N ranked opportunities.

        Args:
            market: ``"US"`` or ``"EU"`` (or a two-letter country code).
            cap_type: ``"micro"`` (< $300 M), ``"small"`` ($300 M–$2 B),
                ``"mid"``, or ``"all"``.
            sector: Optional sector keyword filter (partial, case-insensitive).
            min_growth: Minimum revenue growth as a decimal (e.g. ``0.15``).
            strategy: ``"value"``, ``"growth"``, or ``None`` for balanced.
            extra_tickers: Additional tickers to include in the screen.
            top_n: Number of top results to return.

        Returns:
            Dictionary with:
            - ``opportunities``: Ranked list of opportunity dicts.
            - ``market``, ``cap_type``, ``sector``, ``strategy``: Echo of inputs.
            - ``total_screened``: How many tickers were evaluated.
            - ``ai_report``: LLM-generated narrative report.
        """
        universe = get_universe(market, cap_type)
        if extra_tickers:
            universe = list(dict.fromkeys(universe + [t.upper() for t in extra_tickers]))

        if not universe:
            logger.warning("Empty universe for market=%s cap=%s", market, cap_type)
            return {
                "opportunities": [],
                "market": market,
                "cap_type": cap_type,
                "sector": sector,
                "strategy": strategy,
                "total_screened": 0,
                "ai_report": _REPORT_FALLBACK,
            }

        logger.info(
            "Screening %d tickers | market=%s cap=%s sector=%s min_growth=%s",
            len(universe), market, cap_type, sector, min_growth,
        )

        ranked = screen_stocks(
            universe,
            cap_type=cap_type,
            sector=sector,
            min_growth=min_growth,
            strategy=strategy,
        )

        top_results = ranked[:top_n]
        ai_report = self._generate_opportunity_report(
            top_results, market=market, cap_type=cap_type
        )

        return {
            "opportunities": top_results,
            "market": market,
            "cap_type": cap_type,
            "sector": sector,
            "strategy": strategy,
            "total_screened": len(ranked),
            "ai_report": ai_report,
        }

    def analyze_stock(self, ticker: str) -> Dict[str, Any]:
        """Perform a deep-dive analysis on a single stock.

        Args:
            ticker: Ticker symbol (e.g. ``"MVIS"``, ``"BMW.DE"``).

        Returns:
            Combined dict with all fundamental data plus an ``ai_analysis``
            key containing the LLM-generated investment thesis.
        """
        logger.info("Deep-dive analysis for %s", ticker)
        fund = fetch_fundamentals(ticker.upper())

        if "error" in fund:
            return fund

        opp_score = score_opportunity(fund)
        fund["opportunity_score"] = opp_score
        fund["recommendation_action"] = (
            "BUY" if opp_score >= 70 else "WATCH" if opp_score >= 50 else "AVOID"
        )

        ai_analysis = self._generate_stock_analysis(fund)
        return {**fund, "ai_analysis": ai_analysis}

    def compare_stocks(self, tickers: List[str]) -> Dict[str, Any]:
        """Compare multiple stocks side-by-side.

        Args:
            tickers: List of ticker symbols to compare.

        Returns:
            Dictionary with ``stocks`` (list of scored fundamentals) and
            ``ai_comparison`` (LLM narrative comparison).
        """
        logger.info("Comparing %d stocks: %s", len(tickers), tickers)
        stocks = []
        for ticker in tickers:
            fund = fetch_fundamentals(ticker.upper())
            if "error" not in fund:
                fund["opportunity_score"] = score_opportunity(fund)
                stocks.append(fund)

        ai_comparison = self._generate_comparison(stocks)
        return {"stocks": sorted(stocks, key=lambda x: x.get("opportunity_score", 0), reverse=True),
                "ai_comparison": ai_comparison}

    # ------------------------------------------------------------------
    # Private LLM helpers
    # ------------------------------------------------------------------

    def _generate_opportunity_report(
        self,
        opportunities: List[Dict[str, Any]],
        market: str,
        cap_type: str,
    ) -> Dict[str, Any]:
        """Generate a narrative opportunity report for the top results."""
        if not opportunities:
            return _REPORT_FALLBACK

        # Trim payload to keep within context limits
        slim = [
            {
                "symbol": o.get("symbol"),
                "name": o.get("name"),
                "sector": o.get("sector"),
                "market_cap": o.get("market_cap"),
                "pe_ratio": o.get("pe_ratio"),
                "peg_ratio": o.get("peg_ratio"),
                "revenue_growth": o.get("revenue_growth"),
                "earnings_growth": o.get("earnings_growth"),
                "opportunity_score": o.get("opportunity_score"),
                "recommendation_action": o.get("recommendation_action"),
            }
            for o in opportunities
        ]

        prompt = (
            f"You are analysing {cap_type}-cap stocks in the {market} market.\n\n"
            "Here are the top-ranked opportunities from a quantitative screen:\n\n"
            f"{json.dumps(slim, indent=2)}\n\n"
            "Generate a professional investment opportunity report as JSON with keys:\n"
            "- title: report title string\n"
            "- executive_summary: 2–3 sentence overall market commentary\n"
            "- top_picks: list of objects {symbol, thesis, key_catalyst, risk, action}\n"
            "- market_context: brief paragraph on small/micro-cap conditions in this market\n"
            "- risk_warnings: list of 2–3 macro/sector risks to watch\n\n"
            "Respond ONLY with valid JSON."
        )

        response = self.llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        return parse_json_response(response.content, _REPORT_FALLBACK)

    def _generate_stock_analysis(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a deep-dive investment thesis for a single stock."""
        slim = {k: v for k, v in fund.items() if k not in ("error",)}

        prompt = (
            f"Provide a deep-dive investment analysis for {fund.get('symbol')} "
            f"({fund.get('name', '')}).\n\n"
            f"Fundamental Data:\n{json.dumps(slim, indent=2)}\n\n"
            "Return a JSON object with keys:\n"
            "- investment_thesis: 2–3 paragraph investment case\n"
            "- key_catalysts: list of 3–5 potential near-term catalysts\n"
            "- key_risks: list of 3–5 key risks investors should monitor\n"
            "- entry_strategy: suggested entry approach (e.g. scale-in, limit order levels)\n"
            "- target_price_rationale: explanation of fair-value estimate\n"
            "- comparable_companies: list of 2–3 comparable tickers with brief notes\n"
            "- recommendation: 'BUY' | 'WATCH' | 'AVOID'\n"
            "- conviction: 'high' | 'medium' | 'low'\n\n"
            "Respond ONLY with valid JSON."
        )

        response = self.llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        return parse_json_response(response.content, _ANALYSIS_FALLBACK)

    def _generate_comparison(self, stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a comparative analysis for multiple stocks."""
        if not stocks:
            return _COMPARISON_FALLBACK

        slim = [
            {
                "symbol": s.get("symbol"),
                "name": s.get("name"),
                "sector": s.get("sector"),
                "pe_ratio": s.get("pe_ratio"),
                "revenue_growth": s.get("revenue_growth"),
                "opportunity_score": s.get("opportunity_score"),
            }
            for s in stocks
        ]

        prompt = (
            "Compare these small/micro-cap stocks for a portfolio manager:\n\n"
            f"{json.dumps(slim, indent=2)}\n\n"
            "Return a JSON object with keys:\n"
            "- best_value: ticker symbol with best value metrics\n"
            "- best_growth: ticker symbol with best growth profile\n"
            "- best_overall: recommended top pick overall\n"
            "- comparative_analysis: paragraph comparing the stocks\n"
            "- recommendation: list of {symbol, action, rationale} for each stock\n\n"
            "Respond ONLY with valid JSON."
        )

        response = self.llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        return parse_json_response(response.content, _COMPARISON_FALLBACK)
