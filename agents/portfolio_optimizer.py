"""Portfolio Optimizer Agent — rule-based allocation recommendations."""

import queue
import threading
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from utils.logger import get_logger

logger = get_logger("arcanix.agents.portfolio_optimizer")

_DEFAULT_INTERVAL = 600  # 10 minutes


class PortfolioOptimizerAgent(BaseAgent):
    """Generates rule-based portfolio optimisation recommendations.

    Subscribes to ``"market_data_updated"`` and ``"risk_alert"`` events.
    On each :meth:`run_cycle` call it processes queued events and derives
    actionable allocation suggestions, then publishes an
    ``"optimization_recommendation"`` event.

    Args:
        event_bus: Shared :class:`EventBus` instance.
        interval: Seconds between optimisation cycles.
    """

    def __init__(self, event_bus: Any, interval: int = _DEFAULT_INTERVAL) -> None:
        super().__init__(
            agent_name="portfolio_optimizer",
            event_bus=event_bus,
            interval=interval,
        )
        self.latest_recommendation: Optional[Dict[str, Any]] = None
        self.capabilities = ["portfolio_optimization", "allocation_advice"]

        self._market_data: Dict[str, Dict] = {}
        self._risk_alert: Optional[Dict[str, Any]] = None
        self._event_queue: queue.Queue = queue.Queue()
        self._rec_lock = threading.Lock()

        self.subscribe_event("market_data_updated", self._on_market_data)
        self.subscribe_event("risk_alert", self._on_risk_alert)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_market_data(self, message: Any) -> None:
        self._event_queue.put(("market_data", message.payload))

    def _on_risk_alert(self, message: Any) -> None:
        self._event_queue.put(("risk_alert", message.payload))

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        """Drain the event queue, then generate a recommendation if data exists."""
        updated = False
        while not self._event_queue.empty():
            try:
                event_type, payload = self._event_queue.get_nowait()
                if event_type == "market_data":
                    self._market_data = payload.get("data", {}).get(
                        "market_data", {}
                    )
                    updated = True
                elif event_type == "risk_alert":
                    self._risk_alert = payload.get("data", {})
                    updated = True
            except queue.Empty:
                break
            except Exception as exc:
                self.log_error(f"Error processing event: {exc}")

        if updated and self._market_data:
            self._generate_recommendation()

    def _generate_recommendation(self) -> None:
        """Produce allocation recommendations based on technicals and risk."""
        try:
            suggestions: List[Dict[str, Any]] = []
            risk_level = (
                self._risk_alert.get("risk_level", "low")
                if self._risk_alert
                else "low"
            )

            for symbol, indicators in self._market_data.items():
                action, reason = self._decide_action(indicators, risk_level)
                suggestions.append(
                    {
                        "symbol": symbol,
                        "action": action,
                        "reason": reason,
                        "current_price": indicators.get("current_price"),
                        "trend": indicators.get("trend"),
                        "rsi": indicators.get("rsi"),
                    }
                )

            rec = {
                "suggestions": suggestions,
                "risk_context": risk_level,
                "rebalance_needed": risk_level == "high",
            }

            with self._rec_lock:
                self.latest_recommendation = rec

            self.publish_event("optimization_recommendation", rec)
            self.log_info(
                f"Published optimization recommendation for "
                f"{len(suggestions)} symbol(s)."
            )
        except Exception as exc:
            self.log_error(f"Optimization error: {exc}")

    @staticmethod
    def _decide_action(
        indicators: Dict[str, Any], risk_level: str
    ) -> tuple:
        """Return (action, reason) for a single symbol.

        Rules:
        * High risk → suggest reducing all positions.
        * RSI > 70 → overbought, suggest trim.
        * RSI < 30 → oversold, suggest accumulate.
        * Bullish trend + RSI 30-50 → buy.
        * Otherwise → hold.
        """
        rsi = indicators.get("rsi", 50)
        trend = indicators.get("trend", "neutral")

        if risk_level == "high":
            return "reduce", "Portfolio risk is elevated — reduce exposure."
        if rsi > 70:
            return "trim", f"Overbought (RSI={rsi:.1f}), consider trimming."
        if rsi < 30:
            return "accumulate", f"Oversold (RSI={rsi:.1f}), buying opportunity."
        if trend == "bullish" and rsi < 50:
            return "buy", f"Bullish trend with RSI={rsi:.1f} — momentum entry."
        return "hold", "No clear signal — hold current position."

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest_recommendation(self) -> Optional[Dict[str, Any]]:
        """Return the most recent optimisation recommendation, or *None*."""
        with self._rec_lock:
            return self.latest_recommendation
