"""Stock screening and opportunity scoring engine.

Provides functions to screen stocks by market-cap tier, sector, and
fundamental/technical criteria, and to score each opportunity on a
0–100 composite scale.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import yfinance as yf

logger = logging.getLogger("arcanix.screener")

# ---------------------------------------------------------------------------
# Market-cap thresholds (USD)
# Boundaries are inclusive on the lower end and exclusive on the upper end:
#   micro : [0, 300M)
#   small : [300M, 2B)
#   mid   : [2B, 10B)
#   large : [10B, ∞)
# ---------------------------------------------------------------------------
MICRO_CAP_MAX: int = 300_000_000
SMALL_CAP_MIN: int = MICRO_CAP_MAX
SMALL_CAP_MAX: int = 2_000_000_000
MID_CAP_MIN: int = SMALL_CAP_MAX
MID_CAP_MAX: int = 10_000_000_000
LARGE_CAP_MIN: int = MID_CAP_MAX

_CAP_LIMITS: Dict[str, Dict[str, Optional[float]]] = {
    "micro": {"min": 0, "max": MICRO_CAP_MAX},
    "small": {"min": SMALL_CAP_MIN, "max": SMALL_CAP_MAX},
    "mid":   {"min": MID_CAP_MIN, "max": MID_CAP_MAX},
    "large": {"min": LARGE_CAP_MIN, "max": None},
}

# ---------------------------------------------------------------------------
# Built-in stock universe
# ---------------------------------------------------------------------------
# A curated, representative set of US and EU small/micro-cap tickers.
# Users can extend the universe via the watchlist or by adding tickers
# directly to their own screening calls.

_US_UNIVERSE: List[str] = [
    # Technology
    "MVIS", "CLSK", "BKNG", "KOPN", "INPX", "ATER", "VNCE", "AIOT",
    "GFAI", "GNSS", "GRWG", "HCDI", "IDEX", "INKW", "IONQ", "IRAAS",
    "KOSS", "LIQT", "LUCY", "MBOT", "MINM", "MOTS", "NRXP", "NVFY",
    # Healthcare / Biotech
    "ACMR", "ACRX", "ADXS", "ALBT", "ALCO", "ALIM", "ALNA", "ALRN",
    "ALTM", "ANIK", "ANIX", "ANTE", "APLP", "APRE", "APTX", "ARCT",
    # Energy
    "AMPY", "BORR", "CDEV", "CEQP", "CLMT", "CRK", "CRIS", "DNOW",
    "DUNE", "ENVA", "GENIE", "GETR", "GPRE", "HPNN", "IMPP",
    # Consumer
    "ACNB", "ALTG", "AMCX", "AMRK", "AMRS", "AMTB", "AMTX", "ANF",
    "ANGI", "AOUT", "ARRY", "ASLE", "ASPS", "ATLC", "ATNI", "ATRC",
    # Financial
    "AROW", "ARTL", "AMSF", "AMNB", "AMRB", "AMTB", "ANCX", "ANFC",
    # Industrials
    "AEIS", "AEYE", "AFCG", "AFRI", "AGIO", "AGEN", "AGFS", "AGIL",
]

_EU_UNIVERSE: Dict[str, List[str]] = {
    # London Stock Exchange (.L)
    "GB": [
        "AIM.L", "ABDN.L", "ABF.L", "ADM.L", "AHT.L", "AIBG.L",
        "AIR.L", "ALFA.L", "ALGN.L", "ALPH.L", "AMFW.L", "AML.L",
        "AO.L", "APAX.L", "APEO.L", "APGN.L", "ASHM.L", "ASL.L",
        "ATG.L", "ATM.L", "AUTO.L", "AV.L", "AVV.L", "AZN.L",
        "BKS.L", "BLND.L", "BMT.L", "BNZL.L", "BOO.L", "BOTB.L",
        "BRK.L", "BUR.L", "CAL.L", "CARD.L", "CBG.L", "CBOX.L",
    ],
    # Deutsche Börse / XETRA (.DE)
    "DE": [
        "SAP.DE", "SIE.DE", "BMW.DE", "ADS.DE", "DTE.DE", "IFX.DE",
        "MBG.DE", "1COV.DE", "SHL.DE", "EVD.DE", "FNTN.DE", "HFG.DE",
        "HOME24.DE", "KWS.DE", "MOR.DE", "NDA.DE", "NDX1.DE", "OHB.DE",
        "PVA.DE", "RRTL.DE", "S92.DE", "SDAX.DE", "SGL.DE", "SLT.DE",
        "SNW.DE", "STO3.DE", "SZG.DE", "TUI1.DE", "ULC.DE", "VBK.DE",
    ],
    # Euronext Paris (.PA)
    "FR": [
        "AI.PA", "AIR.PA", "ALO.PA", "ATO.PA", "BN.PA", "BNP.PA",
        "BOL.PA", "CAP.PA", "CS.PA", "DEC.PA", "DG.PA", "DSY.PA",
        "EDF.PA", "EI.PA", "ENGI.PA", "ERF.PA", "FTI.PA", "GFC.PA",
        "HO.PA", "IMP.PA", "LDL.PA", "LHN.PA", "LR.PA", "MC.PA",
        "MF.PA", "ML.PA", "MMB.PA", "MRP.PA", "NK.PA", "ORA.PA",
    ],
    # Euronext Amsterdam (.AS)
    "NL": [
        "ASML.AS", "HEIA.AS", "ING.AS", "PHIA.AS", "REN.AS", "RD.AS",
        "IMCD.AS", "ABN.AS", "AKZA.AS", "AMG.AS", "BAMNB.AS", "BESI.AS",
        "CTRL.AS", "DSMN.AS", "FFARM.AS", "FUR.AS", "HEIJM.AS",
        "HYDRA.AS", "ICT.AS", "INPST.AS", "KENDR.AS", "LIGHT.AS",
    ],
    # Borsa Italiana (.MI)
    "IT": [
        "ENI.MI", "ENEL.MI", "ISP.MI", "UCG.MI", "STM.MI", "TIT.MI",
        "AMP.MI", "BMED.MI", "BPE.MI", "BSRN.MI", "CALT.MI", "CEM.MI",
        "CPR.MI", "CRDI.MI", "DAN.MI", "ELN.MI", "ERG.MI", "FALCK.MI",
    ],
    # BME / Spain (.MC)
    "ES": [
        "SAN.MC", "BBVA.MC", "ITX.MC", "IBE.MC", "TEF.MC", "CABK.MC",
        "ACS.MC", "AMS.MC", "ACX.MC", "AENA.MC", "ALM.MC", "ANA.MC",
        "AND.MC", "AZK.MC", "BKT.MC", "BME.MC", "CIE.MC", "COL.MC",
    ],
}


def get_universe(market: str, cap_type: str = "all") -> List[str]:
    """Return the built-in ticker universe for a market.

    Args:
        market: ``"US"`` or a two-letter EU country code (``"GB"``, ``"DE"``,
            ``"FR"``, ``"NL"``, ``"IT"``, ``"ES"``) or ``"EU"`` for all European
            markets.
        cap_type: ``"micro"``, ``"small"``, ``"mid"``, or ``"all"``.

    Returns:
        List of ticker symbols to screen.
    """
    market = market.upper()
    if market == "US":
        return list(_US_UNIVERSE)
    if market == "EU":
        tickers: List[str] = []
        for country_tickers in _EU_UNIVERSE.values():
            tickers.extend(country_tickers)
        return tickers
    if market in _EU_UNIVERSE:
        return list(_EU_UNIVERSE[market])
    logger.warning("Unknown market '%s'; returning empty universe.", market)
    return []


def fetch_fundamentals(ticker: str) -> Dict[str, Any]:
    """Fetch fundamental data for a single ticker via yfinance.

    Returns a flat dictionary with the most useful fields for screening.
    Missing fields default to ``None``.

    Args:
        ticker: Ticker symbol (e.g. ``"AAPL"``, ``"BMW.DE"``).

    Returns:
        Dictionary of fundamental metrics.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception as exc:
        logger.warning("Could not fetch info for %s: %s", ticker, exc)
        return {"symbol": ticker, "error": str(exc)}

    return {
        "symbol": ticker,
        "name": info.get("longName") or info.get("shortName", ticker),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "currency": info.get("currency", "USD"),
        # Valuation
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        # Growth
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "profit_margins": info.get("profitMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        # Market data
        "volume": info.get("volume"),
        "avg_volume": info.get("averageVolume"),
        "float_shares": info.get("floatShares"),
        "short_ratio": info.get("shortRatio"),
        "inst_ownership": info.get("heldPercentInstitutions"),
        # 52-week performance
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_day_avg": info.get("fiftyDayAverage"),
        "two_hundred_day_avg": info.get("twoHundredDayAverage"),
        # Analyst coverage
        "recommendation": info.get("recommendationKey"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "target_price": info.get("targetMeanPrice"),
    }


def _cap_matches(market_cap: Optional[float], cap_type: str) -> bool:
    """Return True if market_cap falls within the requested cap-type range.

    Boundaries: lower-inclusive, upper-exclusive — e.g. small-cap is [300M, 2B).
    """
    if cap_type == "all" or market_cap is None:
        return True
    limits = _CAP_LIMITS.get(cap_type.lower())
    if limits is None:
        return True
    lo = limits["min"] or 0
    hi = limits["max"]
    return lo <= market_cap and (hi is None or market_cap < hi)


def score_opportunity(fund: Dict[str, Any]) -> float:
    """Compute a composite 0–100 opportunity score.

    Higher is better. The score is a weighted combination of:
    - **Value** (35 %): P/E, Forward P/E, PEG, P/B, EV/EBITDA
    - **Growth** (35 %): Revenue growth, Earnings growth, Profit margins
    - **Momentum** (20 %): Price vs 50-day MA, 52-week range position
    - **Quality** (10 %): Institutional ownership, analyst target upside

    Args:
        fund: Dictionary returned by :func:`fetch_fundamentals`.

    Returns:
        Float in [0, 100].
    """
    score = 50.0  # neutral baseline

    # --- Value (35 points) ---
    value_pts = 0.0

    pe = fund.get("pe_ratio")
    if pe is not None and pe > 0:
        if pe < 10:
            value_pts += 12
        elif pe < 20:
            value_pts += 8
        elif pe < 30:
            value_pts += 4
        else:
            value_pts -= 2

    peg = fund.get("peg_ratio")
    if peg is not None and peg > 0:
        if peg < 1:
            value_pts += 10
        elif peg < 2:
            value_pts += 5
        else:
            value_pts -= 3

    pb = fund.get("price_to_book")
    if pb is not None and pb > 0:
        if pb < 1:
            value_pts += 8
        elif pb < 3:
            value_pts += 4
        else:
            value_pts -= 2

    ev_ebitda = fund.get("ev_to_ebitda")
    if ev_ebitda is not None and ev_ebitda > 0:
        if ev_ebitda < 8:
            value_pts += 5
        elif ev_ebitda < 15:
            value_pts += 2
        else:
            value_pts -= 2

    # --- Growth (35 points) ---
    growth_pts = 0.0

    rev_growth = fund.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.30:
            growth_pts += 15
        elif rev_growth > 0.15:
            growth_pts += 10
        elif rev_growth > 0.05:
            growth_pts += 5
        elif rev_growth < 0:
            growth_pts -= 5

    earn_growth = fund.get("earnings_growth")
    if earn_growth is not None:
        if earn_growth > 0.30:
            growth_pts += 12
        elif earn_growth > 0.15:
            growth_pts += 7
        elif earn_growth > 0:
            growth_pts += 3
        else:
            growth_pts -= 3

    margins = fund.get("profit_margins")
    if margins is not None:
        if margins > 0.20:
            growth_pts += 8
        elif margins > 0.10:
            growth_pts += 4
        elif margins < 0:
            growth_pts -= 5

    # --- Momentum (20 points) ---
    momentum_pts = 0.0

    price = fund.get("current_price")
    ma50 = fund.get("fifty_day_avg")
    if price is not None and ma50 is not None and ma50 > 0:
        ratio = price / ma50
        if ratio > 1.10:
            momentum_pts += 10
        elif ratio > 1.00:
            momentum_pts += 5
        elif ratio < 0.90:
            momentum_pts -= 5

    hi_52 = fund.get("fifty_two_week_high")
    lo_52 = fund.get("fifty_two_week_low")
    if price is not None and hi_52 is not None and lo_52 is not None:
        rng = hi_52 - lo_52
        if rng > 0:
            position = (price - lo_52) / rng
            # Mid-range is a sweet spot for small-cap recovery plays
            if 0.3 <= position <= 0.7:
                momentum_pts += 10
            elif position < 0.15:
                momentum_pts += 5  # Near 52-week low — potential reversal

    # --- Quality (10 points) ---
    quality_pts = 0.0

    inst_own = fund.get("inst_ownership")
    if inst_own is not None:
        if 0.10 <= inst_own <= 0.60:
            quality_pts += 5  # Healthy institutional interest without crowding
        elif inst_own > 0.80:
            quality_pts -= 2  # Heavily held — less room for discovery upside

    target = fund.get("target_price")
    if price is not None and target is not None and price > 0:
        upside = (target - price) / price
        if upside > 0.30:
            quality_pts += 5
        elif upside > 0.10:
            quality_pts += 2
        elif upside < 0:
            quality_pts -= 3

    score = 50.0 + value_pts + growth_pts + momentum_pts + quality_pts
    return round(max(0.0, min(100.0, score)), 1)


def screen_stocks(
    tickers: List[str],
    cap_type: str = "all",
    sector: Optional[str] = None,
    min_growth: Optional[float] = None,
    strategy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Screen a list of tickers and return ranked opportunities.

    Args:
        tickers: List of ticker symbols to evaluate.
        cap_type: ``"micro"``, ``"small"``, ``"mid"``, or ``"all"``.
        sector: Optional sector filter (case-insensitive, partial match).
        min_growth: Minimum revenue growth as a decimal (e.g. ``0.15`` = 15 %).
        strategy: ``"value"``, ``"growth"``, or ``None`` for balanced.

    Returns:
        List of opportunity dictionaries sorted by ``opportunity_score``
        descending. Each dict contains all fields from :func:`fetch_fundamentals`
        plus ``opportunity_score`` and ``recommendation_action``.
    """
    results: List[Dict[str, Any]] = []
    total = len(tickers)

    for idx, ticker in enumerate(tickers, 1):
        logger.info("Screening %s (%d/%d) …", ticker, idx, total)
        fund = fetch_fundamentals(ticker)

        if "error" in fund:
            continue

        market_cap = fund.get("market_cap")
        if not _cap_matches(market_cap, cap_type):
            continue

        if sector:
            stock_sector = (fund.get("sector") or "").lower()
            if sector.lower() not in stock_sector:
                continue

        if min_growth is not None:
            rev_growth = fund.get("revenue_growth")
            if rev_growth is None or rev_growth < min_growth:
                continue

        opp_score = score_opportunity(fund)

        # Adjust score based on strategy bias
        if strategy == "value":
            pe = fund.get("pe_ratio") or 999
            pb = fund.get("price_to_book") or 999
            if pe < 15 or pb < 1.5:
                opp_score = min(100, opp_score + 10)
        elif strategy == "growth":
            rev_growth = fund.get("revenue_growth") or 0
            if rev_growth > 0.20:
                opp_score = min(100, opp_score + 10)

        # Derive recommendation action from score
        if opp_score >= 70:
            action = "BUY"
        elif opp_score >= 50:
            action = "WATCH"
        else:
            action = "AVOID"

        results.append({**fund, "opportunity_score": opp_score, "recommendation_action": action})

    results.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    return results
