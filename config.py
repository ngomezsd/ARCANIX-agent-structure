"""Configuration management for ARCANIX Investment Fund System."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("arcanix")


def get_required(key: str) -> str:
    """Retrieve a required environment variable, raising an error if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Please copy .env.example to .env and fill in your values."
        )
    return value


# --- Required ---
OPENAI_API_KEY: str = get_required("OPENAI_API_KEY")

# --- Optional with defaults ---
FUND_NAME: str = os.getenv("FUND_NAME", "My Investment Fund")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DATA_PERIOD: str = os.getenv("DATA_PERIOD", "1y")
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.02"))
