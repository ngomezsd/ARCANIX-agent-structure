"""Shared utilities used across ARCANIX agent modules."""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger("arcanix.agent_utils")


def parse_json_response(content: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to parse an LLM response as JSON, returning *fallback* on failure.

    Args:
        content: Raw string content returned by the LLM.
        fallback: Dictionary to return when ``content`` is not valid JSON.

    Returns:
        Parsed dictionary or the provided fallback.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(
            "LLM returned non-JSON response (first 120 chars: %s …); using fallback.",
            content[:120],
        )
        return {**fallback, "_raw_response": content}
