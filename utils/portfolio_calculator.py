"""Portfolio metrics calculations (Sharpe ratio, VaR, drawdown, etc.)."""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger("arcanix.portfolio_calculator")

# Implied annual return assumptions by market trend (simple proxy)
_RETURN_BY_TREND: Dict[str, float] = {
    "bullish": 0.10,   # 10 % p.a.
    "neutral": 0.07,   # 7  % p.a.
    "bearish": 0.04,   # 4  % p.a.
}
_DEFAULT_RETURN: float = _RETURN_BY_TREND["neutral"]

# Fallback annualised volatility when market data is unavailable
_DEFAULT_VOLATILITY: float = 0.15  # 15 % p.a.


def calculate_diversification_score(weights: Dict[str, float]) -> float:
    """Return a diversification score in [0, 10].

    Uses the Herfindahl–Hirschman Index: perfectly concentrated portfolio
    scores 0, a fully equal-weight portfolio scores 10.

    Args:
        weights: Mapping of symbol → portfolio weight (must sum to ≈ 1).

    Returns:
        Diversification score between 0 and 10.
    """
    n = len(weights)
    if n <= 1:
        return 0.0
    hhi = sum(w ** 2 for w in weights.values())
    min_hhi = 1.0 / n  # equal-weight HHI
    if hhi <= min_hhi:
        return 10.0
    score = (1 - hhi) / (1 - min_hhi) * 10
    return round(min(max(score, 0.0), 10.0), 2)


def calculate_portfolio_metrics(
    portfolio: Dict[str, float],
    market_data: Dict[str, Dict],
    risk_free_rate: float = 0.02,
) -> Dict:
    """Compute key portfolio metrics.

    Args:
        portfolio: Mapping of symbol → dollar value invested.
        market_data: Technical indicator data returned by
            :func:`~utils.data_fetcher.get_market_summary`.
        risk_free_rate: Annual risk-free rate used for Sharpe ratio
            calculation (default ``0.02``).

    Returns:
        Dictionary containing:
        - ``total_value``: Total portfolio value.
        - ``weights``: Per-symbol portfolio weights.
        - ``expected_annual_return``: Weighted sum of implied returns.
        - ``volatility``: Weighted portfolio volatility.
        - ``sharpe_ratio``: Annualised Sharpe ratio.
        - ``value_at_risk_95``: Daily 95 % VaR in dollars.
        - ``max_position_size``: Largest single-asset weight.
        - ``diversification_score``: Score between 0 and 10.
    """
    total_value = sum(portfolio.values())
    if total_value <= 0:
        raise ValueError("Portfolio total value must be positive.")

    weights = {symbol: value / total_value for symbol, value in portfolio.items()}

    # Per-symbol annualised volatility from market data (fallback to default)
    symbol_vols = {
        symbol: market_data.get(symbol, {}).get("volatility", _DEFAULT_VOLATILITY)
        for symbol in portfolio
    }

    # Simplified expected return: use recent trend as a proxy.
    # See _RETURN_BY_TREND for the assumed return per trend category.
    symbol_returns = {
        symbol: _RETURN_BY_TREND.get(
            market_data.get(symbol, {}).get("trend", "neutral"), _DEFAULT_RETURN
        )
        for symbol in portfolio
    }

    expected_return = sum(
        weights[s] * symbol_returns[s] for s in portfolio
    )

    # Portfolio volatility.
    # NOTE: This assumes zero correlation between assets, which tends to
    # underestimate true portfolio volatility. It serves as a conservative
    # lower-bound estimate suitable for initial screening.
    volatility = float(
        np.sqrt(sum((weights[s] * symbol_vols[s]) ** 2 for s in portfolio))
    )

    sharpe_ratio = (
        (expected_return - risk_free_rate) / volatility if volatility > 0 else 0.0
    )

    # Daily 95 % Value at Risk (parametric, normal approximation)
    daily_vol = volatility / np.sqrt(252)
    var_95 = float(total_value * 1.645 * daily_vol)

    return {
        "total_value": round(total_value, 2),
        "weights": {s: round(w, 4) for s, w in weights.items()},
        "expected_annual_return": round(expected_return, 4),
        "volatility": round(volatility, 4),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "value_at_risk_95": round(var_95, 2),
        "max_position_size": round(max(weights.values()), 4),
        "diversification_score": calculate_diversification_score(weights),
    }


def calculate_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical Value at Risk.

    Args:
        returns: Series of periodic returns (e.g. daily).
        confidence: Confidence level (default ``0.95``).

    Returns:
        VaR as a positive fraction (e.g. ``0.025`` means 2.5 % loss).
    """
    return float(-np.percentile(returns.dropna(), (1 - confidence) * 100))


def calculate_max_drawdown(prices: pd.Series) -> float:
    """Calculate the maximum drawdown of a price series.

    Args:
        prices: Series of asset prices.

    Returns:
        Maximum drawdown as a negative fraction (e.g. ``-0.35`` means 35 %).
    """
    cumulative = (1 + prices.pct_change()).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())
