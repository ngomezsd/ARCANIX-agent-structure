"""Flask middleware: request logging, CORS, error handlers, request IDs."""

import time
import uuid
from typing import Any

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from api.models import error_response
from utils.logger import get_logger

logger = get_logger("arcanix.api.middleware")


def setup_middleware(app: Flask) -> None:
    """Attach request logging, CORS, error handlers, and request-ID injection.

    Args:
        app: The Flask application instance to configure.
    """
    CORS(app)

    # ------------------------------------------------------------------
    # Request ID + timing
    # ------------------------------------------------------------------

    @app.before_request
    def _before_request() -> None:
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()

    @app.after_request
    def _after_request(response: Any) -> Any:
        duration_ms = (time.time() - g.start_time) * 1000
        request_id = getattr(g, "request_id", "-")
        logger.info(
            "[%s] %s %s → %d (%.1f ms)",
            request_id,
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
        return response

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def _not_found(exc: Any) -> Any:
        return jsonify(error_response(f"Resource not found: {request.path}", 404)), 404

    @app.errorhandler(500)
    def _internal_error(exc: Any) -> Any:
        logger.error("Unhandled server error: %s", exc)
        return (
            jsonify(error_response("Internal server error.", 500)),
            500,
        )
