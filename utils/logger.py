"""Centralised logging configuration for ARCANIX."""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Return a consistently configured logger for the given *name*.

    All loggers share the same root handler so that log output format is
    uniform across the system.  Calling this function multiple times with
    the same *name* returns the same logger instance (standard Python
    behaviour).

    Args:
        name: Logger name (usually ``__name__`` or a descriptive string).
        level: Logging level override.  Defaults to ``logging.INFO``.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level or logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level or logging.INFO)
    logger.propagate = False
    return logger
