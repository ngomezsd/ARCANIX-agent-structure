"""Event bus — thin pub/sub wrapper over MessageQueue."""

from typing import Any, Callable, Dict, List

from core.message_queue import MessageQueue, Message
from utils.logger import get_logger

logger = get_logger("arcanix.core.event_bus")


class EventBus:
    """Application-level event bus backed by :class:`MessageQueue`.

    Components publish named events with arbitrary payloads; other
    components subscribe to event types and receive callbacks on each
    matching event.
    """

    def __init__(self) -> None:
        self._mq = MessageQueue()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(
        self, event_type: str, data: Dict[str, Any], source: str = ""
    ) -> None:
        """Publish an event.

        Args:
            event_type: Event name (e.g. ``"market_data_updated"``).
            data: Arbitrary event payload.
            source: Identifier of the publishing agent / component.
        """
        self._mq.publish(
            message_type=event_type,
            payload={"event_type": event_type, "data": data, "source": source},
            sender_id=source,
        )
        logger.debug("Event published: %s from %s", event_type, source)

    def subscribe(
        self, event_type: str, callback: Callable[[Message], None]
    ) -> None:
        """Register *callback* for *event_type* events.

        Args:
            event_type: Event name to listen for.
            callback: Callable that receives a :class:`Message` instance.
        """
        self._mq.subscribe(event_type, callback)

    def get_event_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent events from the internal history buffer.

        Args:
            limit: Maximum number of events to return.
        """
        return self._mq.get_all_messages(limit=limit)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the underlying message queue dispatch thread."""
        self._mq.start()

    def stop(self) -> None:
        """Stop the underlying message queue dispatch thread."""
        self._mq.stop()


# Module-level singleton
event_bus = EventBus()
