"""Market Monitor Agent — periodically fetches live market data."""

import threading
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from utils.data_fetcher import get_market_summary
from utils.logger import get_logger

logger = get_logger("arcanix.agents.market_monitor")

_DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "TSLA"]
_DEFAULT_INTERVAL = 300  # 5 minutes


class MarketMonitorAgent(BaseAgent):
    """Fetches market data on a configurable schedule.

    On each :meth:`run_cycle` call the agent retrieves technical
    indicators for every configured symbol and publishes a
    ``"market_data_updated"`` event so that downstream agents can react.

    Args:
        event_bus: Shared :class:`EventBus` instance.
        symbols: Ticker symbols to monitor.
        interval: Seconds between data-fetch cycles.
    """

    def __init__(
        self,
        event_bus: Any,
        symbols: Optional[List[str]] = None,
        interval: int = _DEFAULT_INTERVAL,
    ) -> None:
        super().__init__(
            agent_name="market_monitor",
            event_bus=event_bus,
            interval=interval,
        )
        self.symbols: List[str] = symbols or _DEFAULT_SYMBOLS
        self.latest_data: Dict[str, Dict] = {}
        self.capabilities = ["market_data", "technical_indicators"]
        self._data_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        """Fetch market data and publish ``"market_data_updated"`` event."""
        self.log_info(f"Fetching market data for: {self.symbols}")
        try:
            data = get_market_summary(self.symbols)
            if not data:
                self.log_warning("Market summary returned empty data.")
                return

            with self._data_lock:
                self.latest_data = data

            self.publish_event(
                "market_data_updated",
                {"symbols": self.symbols, "market_data": data},
            )
            self.log_info(
                f"Market data updated for {len(data)} symbols."
            )
        except Exception as exc:
            self.log_error(f"Error fetching market data: {exc}")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest_data(self) -> Dict[str, Dict]:
        """Return the most recently fetched market-data snapshot."""
        with self._data_lock:
            return dict(self.latest_data)
