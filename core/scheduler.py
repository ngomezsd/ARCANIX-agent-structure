"""Task scheduler backed by the ``schedule`` library."""

import threading
import time
from typing import Any, Callable, Dict, List, Optional

import schedule

from utils.logger import get_logger

logger = get_logger("arcanix.core.scheduler")


class TaskScheduler:
    """Wrapper around the ``schedule`` library with a background thread.

    Tasks are identified by a string *name* so they can be added and
    removed by name at runtime.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, schedule.Job] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def add_task(
        self, name: str, func: Callable, interval_seconds: int
    ) -> None:
        """Schedule *func* to run every *interval_seconds* seconds.

        If a task with the same *name* already exists it is replaced.

        Args:
            name: Unique task identifier.
            func: Zero-argument callable to invoke.
            interval_seconds: Interval between invocations.
        """
        with self._lock:
            if name in self._jobs:
                schedule.cancel_job(self._jobs[name])

            job = schedule.every(interval_seconds).seconds.do(func)
            self._jobs[name] = job
        logger.info(
            "Scheduled task '%s' every %d seconds.", name, interval_seconds
        )

    def remove_task(self, name: str) -> None:
        """Cancel and remove the scheduled task called *name*.

        Args:
            name: Task identifier to remove.
        """
        with self._lock:
            job = self._jobs.pop(name, None)
        if job:
            schedule.cancel_job(job)
            logger.info("Removed scheduled task '%s'.", name)

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Return a list of currently scheduled task descriptors."""
        with self._lock:
            return [
                {
                    "name": name,
                    "next_run": str(job.next_run),
                    "interval": job.interval,
                    "unit": job.unit,
                }
                for name, job in self._jobs.items()
            ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="TaskScheduler"
        )
        self._thread.start()
        logger.info("TaskScheduler started.")

    def stop(self) -> None:
        """Stop the scheduling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("TaskScheduler stopped.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while self._running:
            schedule.run_pending()
            time.sleep(1)


# Module-level singleton
scheduler = TaskScheduler()
