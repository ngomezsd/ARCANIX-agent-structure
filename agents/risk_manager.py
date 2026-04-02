"""Risk Manager Agent — rule-based portfolio risk assessment."""

import queue
import threading
from typing import Any, Dict, Optional

from agents.base_agent import BaseAgent
from utils.portfolio_calculator import calculate_portfolio_metrics
from utils.logger import get_logger

logger = get_logger("arcanix.agents.risk_manager")

_DEFAULT_INTERVAL = 60
_HIGH_RISK_THRESHOLD = 7.0  # score out of 10


class RiskManagerAgent(BaseAgent):
    """Assesses portfolio risk whenever fresh market data arrives.

    Subscribes to ``"market_data_updated"`` events.  On each
    :meth:`run_cycle` call it drains the internal event queue and
    computes risk metrics using :func:`calculate_portfolio_metrics`.
    When the computed risk score exceeds the configured threshold a
    ``"risk_alert"`` event is published.

    Args:
        event_bus: Shared :class:`EventBus` instance.
        risk_threshold: Risk score (0–10) above which an alert is raised.
        interval: Seconds between processing cycles.
    """

    def __init__(
        self,
        event_bus: Any,
        risk_threshold: float = _HIGH_RISK_THRESHOLD,
        interval: int = _DEFAULT_INTERVAL,
    ) -> None:
        super().__init__(
            agent_name="risk_manager",
            event_bus=event_bus,
            interval=interval,
        )
        self.risk_threshold = risk_threshold
        self.portfolio: Dict[str, float] = {}
        self.latest_assessment: Optional[Dict[str, Any]] = None
        self.capabilities = ["risk_assessment", "portfolio_metrics"]

        self._event_queue: queue.Queue = queue.Queue()
        self._assessment_lock = threading.Lock()

        # Subscribe to market data events
        self.subscribe_event("market_data_updated", self._on_market_data)

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_market_data(self, message: Any) -> None:
        """Queue incoming market-data events for processing in run_cycle."""
        self._event_queue.put(message.payload)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        """Drain the event queue and compute risk for each new dataset."""
        processed = 0
        while not self._event_queue.empty():
            try:
                payload = self._event_queue.get_nowait()
                market_data = payload.get("data", {}).get("market_data", {})
                if not market_data:
                    continue
                self._assess_risk(market_data)
                processed += 1
            except queue.Empty:
                break
            except Exception as exc:
                self.log_error(f"Error processing market data event: {exc}")

        if processed:
            self.log_info(f"Processed {processed} market data event(s).")

    def _assess_risk(self, market_data: Dict[str, Dict]) -> None:
        """Compute risk metrics and publish an alert if risk is high.

        If no portfolio positions exist a uniform dummy portfolio is
        constructed from the available symbols so that metrics can still
        be computed.
        """
        try:
            portfolio = self.portfolio if self.portfolio else {
                symbol: 10_000.0 for symbol in market_data
            }
            if not portfolio:
                return

            metrics = calculate_portfolio_metrics(portfolio, market_data)
            risk_score = self._compute_risk_score(metrics)

            assessment = {
                "portfolio_metrics": metrics,
                "risk_score": risk_score,
                "risk_level": self._risk_level(risk_score),
                "threshold": self.risk_threshold,
                "alert": risk_score > self.risk_threshold,
            }

            with self._assessment_lock:
                self.latest_assessment = assessment

            if risk_score > self.risk_threshold:
                self.log_warning(
                    f"HIGH RISK detected! Score={risk_score:.1f} "
                    f"(threshold={self.risk_threshold})"
                )
                self.publish_event("risk_alert", assessment)
            else:
                self.log_info(
                    f"Risk assessment complete. Score={risk_score:.1f}"
                )
        except Exception as exc:
            self.log_error(f"Risk assessment error: {exc}")

    # ------------------------------------------------------------------
    # Risk scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_risk_score(metrics: Dict[str, Any]) -> float:
        """Derive a 0–10 risk score from portfolio metrics.

        Higher score → higher risk.  Factors considered:

        * Volatility (annualised)
        * Sharpe ratio (inverse relationship)
        * Max position concentration
        * Diversification score (inverse)
        """
        score = 0.0

        vol = metrics.get("volatility", 0.15)
        score += min(vol / 0.30 * 4, 4.0)  # up to 4 pts for volatility

        sharpe = metrics.get("sharpe_ratio", 1.0)
        if sharpe < 0.5:
            score += 3.0
        elif sharpe < 1.0:
            score += 1.5
        # sharpe >= 1.0 → 0 pts

        max_pos = metrics.get("max_position_size", 0.25)
        if max_pos > 0.5:
            score += 2.0
        elif max_pos > 0.3:
            score += 1.0

        div = metrics.get("diversification_score", 5.0)
        score += max(0.0, (5.0 - div) / 5.0)  # up to 1 pt for poor diversification

        return round(min(score, 10.0), 2)

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 7:
            return "high"
        if score >= 4:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest_assessment(self) -> Optional[Dict[str, Any]]:
        """Return the most recent risk assessment, or *None*."""
        with self._assessment_lock:
            return self.latest_assessment
