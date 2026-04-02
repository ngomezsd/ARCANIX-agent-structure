"""Opportunity Scout Agent — scans for buying opportunities."""

import queue
import threading
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from utils.logger import get_logger

logger = get_logger("arcanix.agents.opportunity_scout")

_DEFAULT_INTERVAL = 300
_DEFAULT_RSI_OVERSOLD = 35


class OpportunityScoutAgent(BaseAgent):
    """Scans market data for technical buying signals.

    Subscribes to ``"market_data_updated"`` events.  On each
    :meth:`run_cycle` call it evaluates each symbol for:

    * Oversold RSI (below :attr:`rsi_oversold_threshold`).
    * Price above its 50-day moving average (uptrend confirmation).
    * Positive MACD crossover (momentum confirmation).

    When one or more opportunities are found an ``"opportunity_found"``
    event is published.

    Args:
        event_bus: Shared :class:`EventBus` instance.
        rsi_oversold_threshold: RSI below this value flags as oversold.
        interval: Seconds between scanning cycles.
    """

    def __init__(
        self,
        event_bus: Any,
        rsi_oversold_threshold: float = _DEFAULT_RSI_OVERSOLD,
        interval: int = _DEFAULT_INTERVAL,
    ) -> None:
        super().__init__(
            agent_name="opportunity_scout",
            event_bus=event_bus,
            interval=interval,
        )
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.latest_opportunities: List[Dict[str, Any]] = []
        self.capabilities = ["opportunity_detection", "technical_signals"]

        self._event_queue: queue.Queue = queue.Queue()
        self._opp_lock = threading.Lock()

        self.subscribe_event("market_data_updated", self._on_market_data)

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_market_data(self, message: Any) -> None:
        self._event_queue.put(message.payload)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        """Drain the event queue and scan each dataset for opportunities."""
        while not self._event_queue.empty():
            try:
                payload = self._event_queue.get_nowait()
                market_data = payload.get("data", {}).get("market_data", {})
                if market_data:
                    self._scan_opportunities(market_data)
            except queue.Empty:
                break
            except Exception as exc:
                self.log_error(f"Error processing market data: {exc}")

    def _scan_opportunities(self, market_data: Dict[str, Dict]) -> None:
        """Identify opportunities and publish an event if any are found."""
        try:
            opportunities: List[Dict[str, Any]] = []
            for symbol, indicators in market_data.items():
                opp = self._evaluate_symbol(symbol, indicators)
                if opp:
                    opportunities.append(opp)

            with self._opp_lock:
                self.latest_opportunities = opportunities

            if opportunities:
                self.publish_event(
                    "opportunity_found",
                    {"opportunities": opportunities, "count": len(opportunities)},
                )
                self.log_info(
                    f"Found {len(opportunities)} opportunity(ies): "
                    + ", ".join(o["symbol"] for o in opportunities)
                )
            else:
                self.log_info("No opportunities detected in this scan.")
        except Exception as exc:
            self.log_error(f"Opportunity scan error: {exc}")

    def _evaluate_symbol(
        self, symbol: str, indicators: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Return an opportunity dict for *symbol*, or *None*."""
        rsi = indicators.get("rsi", 50)
        current_price = indicators.get("current_price", 0)
        ma50 = indicators.get("ma50", 0)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)

        signals = []

        if rsi < self.rsi_oversold_threshold:
            signals.append(f"oversold RSI ({rsi:.1f})")

        if ma50 and current_price > ma50:
            signals.append(f"price above MA50 ({current_price:.2f} > {ma50:.2f})")

        if macd > macd_signal:
            signals.append("positive MACD crossover")

        # Require at least two signals for a valid opportunity
        if len(signals) < 2:
            return None

        return {
            "symbol": symbol,
            "current_price": current_price,
            "rsi": rsi,
            "ma50": ma50,
            "trend": indicators.get("trend"),
            "signals": signals,
            "signal_count": len(signals),
            "strength": "strong" if len(signals) == 3 else "moderate",
        }

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest_opportunities(self) -> List[Dict[str, Any]]:
        """Return the opportunities identified in the last scan."""
        with self._opp_lock:
            return list(self.latest_opportunities)
