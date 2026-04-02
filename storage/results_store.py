"""Analysis results persistence."""

import json
from typing import Any, Dict, List, Optional

from storage.database import db
from utils.logger import get_logger

logger = get_logger("arcanix.storage.results_store")


class ResultsStore:
    """Store and retrieve analysis results by type."""

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_result(self, result_type: str, data: Any) -> None:
        """Persist an analysis result.

        Args:
            result_type: Logical category (e.g. ``"market_data"``,
                ``"risk_assessment"``).
            data: JSON-serialisable payload.
        """
        db.execute(
            "INSERT INTO analysis_results (result_type, data, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (result_type, json.dumps(data)),
        )
        logger.debug("Saved result of type '%s'", result_type)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_latest_result(self, result_type: str) -> Optional[Dict[str, Any]]:
        """Return the most recent result for *result_type*, or *None*."""
        row = db.fetchone(
            "SELECT data, created_at FROM analysis_results "
            "WHERE result_type = ? ORDER BY id DESC LIMIT 1",
            (result_type,),
        )
        if row is None:
            return None
        return {"data": json.loads(row["data"]), "created_at": row["created_at"]}

    def get_results(
        self, result_type: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return recent results for *result_type* (newest first).

        Args:
            result_type: Logical category to filter by.
            limit: Maximum number of records to return.
        """
        rows = db.fetchall(
            "SELECT data, created_at FROM analysis_results "
            "WHERE result_type = ? ORDER BY id DESC LIMIT ?",
            (result_type, limit),
        )
        return [
            {"data": json.loads(row["data"]), "created_at": row["created_at"]}
            for row in rows
        ]

    def get_all_latest(self) -> Dict[str, Any]:
        """Return the latest result of every distinct result_type."""
        rows = db.fetchall(
            "SELECT result_type, data, created_at FROM analysis_results "
            "WHERE id IN ("
            "  SELECT MAX(id) FROM analysis_results GROUP BY result_type"
            ")"
        )
        return {
            row["result_type"]: {
                "data": json.loads(row["data"]),
                "created_at": row["created_at"],
            }
            for row in rows
        }


# Module-level singleton
results_store = ResultsStore()
