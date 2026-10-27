"""Shared environment configuration for the API and import commands."""

from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> None:
    """Load App/.env while preserving explicit environment variables."""
    load_dotenv(APP_ROOT / ".env", override=False)
