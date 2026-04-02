"""Reporter Agent — aggregates data from all agents and generates reports."""

import queue
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from utils.logger import get_logger

logger = get_logger("arcanix.agents.reporter")

_DEFAULT_INTERVAL = 900  # 15 minutes


class ReporterAgent(BaseAgent):
    """Collects data from other agents and produces structured text reports.

    Subscribes to ``"market_data_updated"``, ``"risk_alert"``,
    ``"optimization_recommendation"``, and ``"opportunity_found"`` events.
    On each :meth:`run_cycle` call it compiles the latest data into a
    human-readable report and publishes a ``"report_generated"`` event.

    Args:
        event_bus: Shared :class:`EventBus` instance.
        interval: Seconds between report-generation cycles.
    """

    def __init__(self, event_bus: Any, interval: int = _DEFAULT_INTERVAL) -> None:
        super().__init__(
            agent_name="reporter",
            event_bus=event_bus,
            interval=interval,
        )
        self.latest_report: Optional[Dict[str, Any]] = None
        self.capabilities = ["reporting", "aggregation"]

        self._market_data: Dict[str, Dict] = {}
        self._risk_assessment: Optional[Dict[str, Any]] = None
        self._recommendation: Optional[Dict[str, Any]] = None
        self._opportunities: List[Dict[str, Any]] = []

        self._report_lock = threading.Lock()
        self._dirty = False  # tracks whether new data has arrived

        self.subscribe_event("market_data_updated", self._on_market_data)
        self.subscribe_event("risk_alert", self._on_risk_alert)
        self.subscribe_event("optimization_recommendation", self._on_recommendation)
        self.subscribe_event("opportunity_found", self._on_opportunity)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_market_data(self, message: Any) -> None:
        self._market_data = (
            message.payload.get("data", {}).get("market_data", {})
        )
        self._dirty = True

    def _on_risk_alert(self, message: Any) -> None:
        self._risk_assessment = message.payload.get("data", {})
        self._dirty = True

    def _on_recommendation(self, message: Any) -> None:
        self._recommendation = message.payload.get("data", {})
        self._dirty = True

    def _on_opportunity(self, message: Any) -> None:
        self._opportunities = (
            message.payload.get("data", {}).get("opportunities", [])
        )
        self._dirty = True

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        """Generate a report if any new data has arrived since the last cycle."""
        if self._dirty:
            self._generate_report()
            self._dirty = False

    def _generate_report(self) -> None:
        """Compile a structured report from aggregated agent data."""
        try:
            timestamp = datetime.utcnow().isoformat()
            lines = [
                "=" * 60,
                f"ARCANIX Investment Report — {timestamp}",
                "=" * 60,
            ]

            # Market data section
            if self._market_data:
                lines.append("\n📊 MARKET DATA SUMMARY")
                lines.append("-" * 40)
                for symbol, data in self._market_data.items():
                    trend_emoji = "📈" if data.get("trend") == "bullish" else "📉"
                    lines.append(
                        f"  {trend_emoji} {symbol}: "
                        f"${data.get('current_price', 0):.2f} | "
                        f"RSI={data.get('rsi', 0):.1f} | "
                        f"Trend={data.get('trend', 'N/A')}"
                    )

            # Risk section
            if self._risk_assessment:
                score = self._risk_assessment.get("risk_score", 0)
                level = self._risk_assessment.get("risk_level", "unknown")
                alert_icon = "⚠️ " if self._risk_assessment.get("alert") else "✅"
                lines.append("\n⚠️  RISK ASSESSMENT")
                lines.append("-" * 40)
                lines.append(
                    f"  {alert_icon} Risk Score: {score:.1f}/10 — {level.upper()}"
                )
                metrics = self._risk_assessment.get("portfolio_metrics", {})
                if metrics:
                    lines.append(
                        f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')} | "
                        f"VaR 95%: ${metrics.get('value_at_risk_95', 0):.2f} | "
                        f"Diversification: "
                        f"{metrics.get('diversification_score', 0)}/10"
                    )

            # Recommendations section
            if self._recommendation:
                suggestions = self._recommendation.get("suggestions", [])
                lines.append("\n📈 PORTFOLIO RECOMMENDATIONS")
                lines.append("-" * 40)
                for s in suggestions:
                    action_emoji = {
                        "buy": "🟢",
                        "accumulate": "🟢",
                        "hold": "🟡",
                        "trim": "🟠",
                        "reduce": "🔴",
                    }.get(s.get("action", "hold"), "🔵")
                    lines.append(
                        f"  {action_emoji} {s.get('symbol')}: "
                        f"{s.get('action', '').upper()} — {s.get('reason', '')}"
                    )

            # Opportunities section
            if self._opportunities:
                lines.append("\n🔍 BUYING OPPORTUNITIES")
                lines.append("-" * 40)
                for opp in self._opportunities:
                    lines.append(
                        f"  ⭐ {opp.get('symbol')}: "
                        f"${opp.get('current_price', 0):.2f} | "
                        f"Strength={opp.get('strength', 'N/A')} | "
                        + " | ".join(opp.get("signals", []))
                    )

            lines.append("\n" + "=" * 60)
            report_text = "\n".join(lines)

            report = {
                "timestamp": timestamp,
                "text": report_text,
                "market_data": self._market_data,
                "risk_assessment": self._risk_assessment,
                "recommendation": self._recommendation,
                "opportunities": self._opportunities,
            }

            with self._report_lock:
                self.latest_report = report

            self.publish_event("report_generated", {"report": report})
            self.log_info("Report generated successfully.")
        except Exception as exc:
            self.log_error(f"Report generation error: {exc}")

    def generate_on_demand(self) -> Optional[Dict[str, Any]]:
        """Immediately generate and return a report regardless of dirty flag."""
        self._generate_report()
        return self.get_latest_report()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest_report(self) -> Optional[Dict[str, Any]]:
        """Return the most recently generated report, or *None*."""
        with self._report_lock:
            return self.latest_report
