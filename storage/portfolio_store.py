"""Portfolio snapshot persistence."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from storage.database import db
from utils.logger import get_logger

logger = get_logger("arcanix.storage.portfolio_store")


class PortfolioStore:
    """Read / write portfolio snapshots to the database."""

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_portfolio(self, portfolio_dict: Dict[str, float]) -> None:
        """Persist the current portfolio state.

        Args:
            portfolio_dict: Mapping of symbol → dollar value.
        """
        db.execute(
            "INSERT INTO portfolio_snapshots (data, created_at) VALUES (?, datetime('now'))",
            (json.dumps(portfolio_dict),),
        )
        logger.debug("Saved portfolio snapshot (%d positions)", len(portfolio_dict))

    def update_portfolio(self, symbol: str, value: float) -> None:
        """Update a single position, saving a new snapshot.

        Loads the latest portfolio, updates *symbol*, and saves a fresh
        snapshot so that history is preserved.

        Args:
            symbol: Ticker symbol to update.
            value: New dollar value for the position.
        """
        current = self.get_portfolio() or {}
        current[symbol] = value
        self.save_portfolio(current)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_portfolio(self) -> Optional[Dict[str, float]]:
        """Return the most recently saved portfolio, or *None*."""
        row = db.fetchone(
            "SELECT data FROM portfolio_snapshots ORDER BY id DESC LIMIT 1"
        )
        if row is None:
            return None
        return json.loads(row["data"])

    def get_portfolio_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return historical portfolio snapshots (newest first).

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of dicts with keys ``data`` and ``created_at``.
        """
        rows = db.fetchall(
            "SELECT data, created_at FROM portfolio_snapshots "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {"data": json.loads(row["data"]), "created_at": row["created_at"]}
            for row in rows
        ]


# Module-level singleton
portfolio_store = PortfolioStore()
