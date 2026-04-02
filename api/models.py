"""Response model helpers for the ARCANIX REST API."""

from datetime import datetime
from typing import Any, Dict, Optional


def success_response(
    data: Any, message: str = ""
) -> Dict[str, Any]:
    """Build a standardised success envelope.

    Args:
        data: The response payload.
        message: Optional human-readable description.

    Returns:
        Dict with keys: ``status``, ``data``, ``message``, ``timestamp``.
    """
    return {
        "status": "success",
        "data": data,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }


def error_response(
    message: str, code: int = 400
) -> Dict[str, Any]:
    """Build a standardised error envelope.

    Args:
        message: Human-readable error description.
        code: HTTP-style status code (default 400).

    Returns:
        Dict with keys: ``status``, ``message``, ``code``, ``timestamp``.
    """
    return {
        "status": "error",
        "message": message,
        "code": code,
        "timestamp": datetime.utcnow().isoformat(),
    }
