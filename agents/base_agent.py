"""Abstract base class for all ARCANIX autonomous agents."""

import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("arcanix.agents.base")


class BaseAgent(ABC):
    """Abstract agent with lifecycle management and event-bus integration.

    Sub-classes must implement :meth:`run_cycle` which contains the
    agent's core logic.  The base class handles:

    * Thread-based start / stop lifecycle.
    * Structured log accumulation (accessible via :meth:`get_status`).
    * Publishing and subscribing to the shared :class:`EventBus`.

    Attributes:
        agent_id: Unique UUID string assigned at construction time.
        agent_name: Human-readable agent identifier.
        status: One of ``"idle"``, ``"running"``, ``"stopped"``, ``"error"``.
        logs: Ordered list of log entry dicts.
        interval: Seconds to sleep between :meth:`run_cycle` calls.
        capabilities: Optional list of capability strings.
    """

    def __init__(
        self,
        agent_name: str,
        event_bus: Any,
        interval: int = 60,
    ) -> None:
        self.agent_id: str = str(uuid.uuid4())
        self.agent_name: str = agent_name
        self.status: str = "idle"
        self.logs: List[Dict[str, Any]] = []
        self.interval: int = interval
        self.capabilities: List[str] = []

        self._event_bus = event_bus
        self._running: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._logger = get_logger(f"arcanix.agents.{agent_name}")

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run_cycle(self) -> None:
        """Execute one unit of work.

        Called repeatedly by the agent thread with :attr:`interval`
        seconds of sleep between calls.  Implementations must be
        exception-safe: errors should be logged and the method should
        return normally so the loop continues.
        """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the agent background thread."""
        if self._running:
            logger.warning("Agent '%s' is already running.", self.agent_name)
            return
        self._running = True
        self._stop_event.clear()
        self.status = "running"
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name=f"agent-{self.agent_name}",
        )
        self._thread.start()
        self.log_info(f"Agent '{self.agent_name}' started.")

    def stop(self) -> None:
        """Signal the agent thread to stop and wait for it to finish."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        self.status = "stopped"
        if self._thread:
            self._thread.join(timeout=10)
        self.log_info(f"Agent '{self.agent_name}' stopped.")

    # ------------------------------------------------------------------
    # Event bus helpers
    # ------------------------------------------------------------------

    def publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish *event_type* with *data* to the shared event bus.

        Args:
            event_type: Named event (e.g. ``"market_data_updated"``).
            data: Arbitrary payload dict.
        """
        self._event_bus.publish(event_type, data, source=self.agent_id)

    def subscribe_event(self, event_type: str, callback: Any) -> None:
        """Subscribe *callback* to *event_type* on the shared event bus."""
        self._event_bus.subscribe(event_type, callback)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of agent status suitable for serialisation."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "interval": self.interval,
            "capabilities": self.capabilities,
            "log_count": len(self.logs),
        }

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    def log_info(self, msg: str) -> None:
        """Record an INFO-level log entry."""
        self._add_log("INFO", msg)
        self._logger.info(msg)

    def log_error(self, msg: str) -> None:
        """Record an ERROR-level log entry."""
        self._add_log("ERROR", msg)
        self._logger.error(msg)

    def log_warning(self, msg: str) -> None:
        """Record a WARNING-level log entry."""
        self._add_log("WARNING", msg)
        self._logger.warning(msg)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_log(self, level: str, message: str) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
        }
        with self._lock:
            self.logs.append(entry)
            # Keep only the most recent 500 log entries in memory
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]

    def _loop(self) -> None:
        """Internal thread loop — calls :meth:`run_cycle` then sleeps."""
        while self._running:
            try:
                self.run_cycle()
            except Exception as exc:
                self.status = "error"
                self.log_error(f"Unhandled exception in run_cycle: {exc}")
            finally:
                # Use an event-based wait so stop() can interrupt the sleep immediately
                self._stop_event.wait(timeout=self.interval)
