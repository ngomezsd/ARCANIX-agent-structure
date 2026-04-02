"""SQLite-backed persistent storage for ARCANIX."""

import json
import os
import sqlite3
import threading
from typing import Any, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger("arcanix.storage.database")

_DB_PATH = os.environ.get("ARCANIX_DB_PATH", "storage/arcanix.db")


class Database:
    """Thread-safe SQLite wrapper with lazy table initialisation."""

    def __init__(self, db_path: str = _DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create all application tables if they do not already exist."""
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                data        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                result_type TEXT    NOT NULL,
                data        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id    TEXT    NOT NULL,
                agent_name  TEXT    NOT NULL,
                level       TEXT    NOT NULL,
                message     TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT    NOT NULL,
                source      TEXT,
                data        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """,
        ]
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                for stmt in ddl_statements:
                    conn.execute(stmt)
                conn.commit()
                logger.info("Database initialised at %s", self.db_path)
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def execute(self, query: str, params: Tuple = ()) -> None:
        """Execute a write statement (INSERT / UPDATE / DELETE)."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(query, params)
                conn.commit()
            finally:
                conn.close()

    def fetchall(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT and return all rows."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(query, params)
                return cursor.fetchall()
            finally:
                conn.close()

    def fetchone(self, query: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        """Execute a SELECT and return a single row (or *None*)."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(query, params)
                return cursor.fetchone()
            finally:
                conn.close()


# Module-level singleton
db = Database()
