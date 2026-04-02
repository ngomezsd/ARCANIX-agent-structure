"""Market data fetching and technical indicator calculation."""

import logging
from typing import Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger("arcanix.data_fetcher")


def fetch_market_data(symbols: List[str], period: str = "1y") -> pd.DataFrame:
    """Fetch historical OHLCV data for the given symbols.

    Args:
        symbols: List of ticker symbols (e.g. ["AAPL", "MSFT"]).
        period: Lookback period accepted by yfinance (e.g. "1y", "6mo").

    Returns:
        A multi-level DataFrame with columns keyed by (field, symbol).
    """
    logger.info("Fetching market data for %s (period=%s)", symbols, period)
    data = yf.download(symbols, period=period, progress=False, auto_adjust=True)
    if data.empty:
        raise ValueError(f"No market data returned for symbols: {symbols}")
    return data


def _get_close_series(data: pd.DataFrame, symbol: str) -> pd.Series:
    """Extract the closing-price series for a single symbol."""
    if isinstance(data.columns, pd.MultiIndex):
        return data[("Close", symbol)].dropna()
    return data["Close"].dropna()


def calculate_technical_indicators(data: pd.DataFrame, symbol: str) -> Dict:
    """Calculate technical indicators for a single symbol.

    Indicators computed:
    - 20-day and 50-day simple moving averages
    - RSI (14-day)
    - MACD (12/26/9)
    - Annualised volatility

    Args:
        data: DataFrame returned by :func:`fetch_market_data`.
        symbol: Ticker symbol to analyse.

    Returns:
        Dictionary of indicator values.
    """
    close = _get_close_series(data, symbol)

    if len(close) < 50:
        raise ValueError(
            f"Not enough data to compute indicators for {symbol} "
            f"(got {len(close)} rows, need at least 50)."
        )

    # Moving averages
    ma20 = float(close.rolling(window=20).mean().iloc[-1])
    ma50 = float(close.rolling(window=50).mean().iloc[-1])
    current_price = float(close.iloc[-1])

    # RSI (14-day)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = float((100 - (100 / (1 + rs))).iloc[-1])

    # MACD (12 / 26 / 9)
    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp12 - exp26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    # Annualised volatility
    volatility = float(close.pct_change().std() * np.sqrt(252))

    return {
        "symbol": symbol,
        "current_price": current_price,
        "ma20": ma20,
        "ma50": ma50,
        "rsi": rsi,
        "macd": float(macd_line.iloc[-1]),
        "macd_signal": float(signal_line.iloc[-1]),
        "trend": "bullish" if ma20 > ma50 else "bearish",
        "volatility": volatility,
    }


def get_market_summary(symbols: List[str], period: str = "1y") -> Dict[str, Dict]:
    """Fetch data and compute technical indicators for multiple symbols.

    Args:
        symbols: List of ticker symbols.
        period: Lookback period (default ``"1y"``).

    Returns:
        Mapping of symbol → indicator dictionary.
    """
    data = fetch_market_data(symbols, period=period)
    summary: Dict[str, Dict] = {}
    for symbol in symbols:
        try:
            summary[symbol] = calculate_technical_indicators(data, symbol)
        except Exception as exc:
            logger.warning("Could not compute indicators for %s: %s", symbol, exc)
    return summary
