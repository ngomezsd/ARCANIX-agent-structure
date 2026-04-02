"""Local JSON storage for portfolio holdings and watchlist.

Data is persisted under a ``data/`` directory in the project root.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger("arcanix.storage")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_PORTFOLIO_FILE = os.path.join(_DATA_DIR, "portfolio.json")
_WATCHLIST_FILE = os.path.join(_DATA_DIR, "watchlist.json")


def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _load(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        logger.error("Corrupt storage file %s: %s", path, exc)
        return default


def _save(path: str, data: Any) -> None:
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

def load_portfolio() -> Dict[str, Dict[str, Any]]:
    """Return the stored portfolio.

    Returns:
        Mapping of ticker → ``{quantity, avg_cost, market, notes}``.
    """
    return _load(_PORTFOLIO_FILE, {})


def save_portfolio(portfolio: Dict[str, Dict[str, Any]]) -> None:
    """Persist the portfolio to disk."""
    _save(_PORTFOLIO_FILE, portfolio)


def add_position(
    ticker: str,
    quantity: float,
    avg_cost: float,
    market: str = "US",
    notes: str = "",
) -> None:
    """Add or update a portfolio position.

    Args:
        ticker: Ticker symbol (upper-cased automatically).
        quantity: Number of shares.
        avg_cost: Average cost per share in local currency.
        market: Market identifier (e.g. ``"US"``, ``"GB"``, ``"DE"``).
        notes: Optional freeform notes.
    """
    portfolio = load_portfolio()
    ticker = ticker.upper()
    portfolio[ticker] = {
        "quantity": quantity,
        "avg_cost": avg_cost,
        "market": market.upper(),
        "notes": notes,
        "added_date": portfolio.get(ticker, {}).get("added_date", date.today().isoformat()),
        "updated_date": date.today().isoformat(),
    }
    save_portfolio(portfolio)
    logger.info("Portfolio position saved: %s × %.2f @ %.4f", ticker, quantity, avg_cost)


def remove_position(ticker: str) -> bool:
    """Remove a ticker from the portfolio.

    Returns:
        True if the ticker was present and removed; False otherwise.
    """
    portfolio = load_portfolio()
    ticker = ticker.upper()
    if ticker in portfolio:
        del portfolio[ticker]
        save_portfolio(portfolio)
        logger.info("Removed portfolio position: %s", ticker)
        return True
    return False


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def load_watchlist() -> Dict[str, Dict[str, Any]]:
    """Return the stored watchlist.

    Returns:
        Mapping of ticker → ``{added_date, target_price, notes, market}``.
    """
    return _load(_WATCHLIST_FILE, {})


def save_watchlist(watchlist: Dict[str, Dict[str, Any]]) -> None:
    """Persist the watchlist to disk."""
    _save(_WATCHLIST_FILE, watchlist)


def add_to_watchlist(
    ticker: str,
    market: str = "US",
    target_price: Optional[float] = None,
    notes: str = "",
) -> None:
    """Add a ticker to the watchlist.

    Args:
        ticker: Ticker symbol (upper-cased automatically).
        market: Market identifier.
        target_price: Optional price target.
        notes: Optional notes.
    """
    watchlist = load_watchlist()
    ticker = ticker.upper()
    watchlist[ticker] = {
        "market": market.upper(),
        "target_price": target_price,
        "notes": notes,
        "added_date": watchlist.get(ticker, {}).get("added_date", date.today().isoformat()),
        "updated_date": date.today().isoformat(),
    }
    save_watchlist(watchlist)
    logger.info("Watchlist updated: %s", ticker)


def remove_from_watchlist(ticker: str) -> bool:
    """Remove a ticker from the watchlist.

    Returns:
        True if removed; False if it was not present.
    """
    watchlist = load_watchlist()
    ticker = ticker.upper()
    if ticker in watchlist:
        del watchlist[ticker]
        save_watchlist(watchlist)
        logger.info("Removed from watchlist: %s", ticker)
        return True
    return False
