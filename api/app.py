"""Flask application factory."""

from flask import Flask

from api.routes import api_blueprint
from api.middleware import setup_middleware


def create_app(config: dict = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional dict of Flask config overrides.

    Returns:
        Configured :class:`Flask` instance.
    """
    app = Flask(__name__)

    if config:
        app.config.update(config)

    setup_middleware(app)  # CORS is applied inside setup_middleware
    app.register_blueprint(api_blueprint)

    return app
