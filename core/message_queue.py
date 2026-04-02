"""Low-level message queue with pub/sub support."""

import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("arcanix.core.message_queue")


@dataclass
class Message:
    """Immutable message envelope passed between system components."""

    type: str
    payload: Dict[str, Any]
    sender_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class MessageQueue:
    """Thread-safe publish/subscribe message queue.

    Subscribers register callbacks for specific message types.  A
    background daemon thread dispatches messages to matching callbacks as
    they arrive on the internal :class:`queue.Queue`.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Message] = queue.Queue()
        self._subscribers: Dict[str, List[Callable[[Message], None]]] = {}
        self._history: List[Message] = []
        self._max_history = 500
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(
        self, message_type: str, payload: Dict[str, Any], sender_id: str = ""
    ) -> Message:
        """Put a new message onto the queue.

        Args:
            message_type: Logical event/message type string.
            payload: Arbitrary JSON-serialisable data.
            sender_id: Identifier of the publishing component.

        Returns:
            The created :class:`Message` instance.
        """
        msg = Message(type=message_type, payload=payload, sender_id=sender_id)
        self._queue.put(msg)
        return msg

    def subscribe(
        self, message_type: str, callback: Callable[[Message], None]
    ) -> None:
        """Register *callback* to be invoked for every *message_type* message.

        Args:
            message_type: The message type to listen for.
            callback: Callable that receives a :class:`Message` instance.
        """
        with self._lock:
            self._subscribers.setdefault(message_type, []).append(callback)

    def get_all_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent messages from the history buffer.

        Args:
            limit: Maximum number of messages to return (newest last).
        """
        with self._lock:
            messages = self._history[-limit:]
        return [
            {
                "id": m.id,
                "type": m.type,
                "payload": m.payload,
                "sender_id": m.sender_id,
                "timestamp": m.timestamp,
            }
            for m in messages
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background dispatch thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._dispatch_loop, daemon=True, name="MessageQueue"
        )
        self._thread.start()
        logger.info("MessageQueue started")

    def stop(self) -> None:
        """Signal the dispatch thread to stop and wait for it to finish."""
        self._running = False
        # Unblock the queue.get() call with a sentinel
        self._queue.put(
            Message(type="__stop__", payload={}, sender_id="system")
        )
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("MessageQueue stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dispatch_loop(self) -> None:
        while self._running:
            try:
                msg = self._queue.get(timeout=1)
                if msg.type == "__stop__":
                    break
                self._record(msg)
                self._dispatch(msg)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("Dispatch error: %s", exc)

    def _record(self, msg: Message) -> None:
        with self._lock:
            self._history.append(msg)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

    def _dispatch(self, msg: Message) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(msg.type, []))
        for cb in callbacks:
            try:
                cb(msg)
            except Exception as exc:
                logger.error(
                    "Subscriber callback error for '%s': %s", msg.type, exc
                )
