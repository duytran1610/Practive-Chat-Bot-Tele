"""
config.py — Centralized configuration.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import SplitResult, urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str       = os.getenv("BOT_TOKEN", "")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI    : str   = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str   = os.getenv("MONGO_DB_NAME", "meal_bot")

    # ── Worker ────────────────────────────────────────────────────────────────
    NUM_WORKERS  : int   = int(os.getenv("NUM_WORKERS", "3"))
    QUEUE_MAX_SIZE: int  = int(os.getenv("QUEUE_MAX_SIZE", "500"))

    # ── Retry ─────────────────────────────────────────────────────────────────
    MAX_RETRIES      : int   = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BASE_DELAY : float = float(os.getenv("RETRY_BASE_DELAY", "2.0"))
    MEAL_REGISTRATION_CUTOFF_HOUR: int = int(os.getenv("MEAL_REGISTRATION_CUTOFF_HOUR", "16"))

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Admin ─────────────────────────────────────────────────────────────────
    ADMIN_CHAT_ID: int | None = (
        int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
    )

    @property
    def safe_mongo_uri(self) -> str:
        """Tra ve Mongo URI da an mat khau de ghi log."""
        return redact_mongo_uri(self.MONGO_URI)

    def validate(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set.")
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI is not set.")
        if not self.MONGO_DB_NAME:
            raise ValueError("MONGO_DB_NAME is not set.")


settings = Settings()


def redact_mongo_uri(uri: str) -> str:
    """An password trong Mongo URI truoc khi dua vao log."""
    if not uri:
        return uri

    parsed = urlsplit(uri)
    if "@" not in parsed.netloc or ":" not in parsed.netloc.split("@", maxsplit=1)[0]:
        return uri

    credentials, host = parsed.netloc.rsplit("@", maxsplit=1)
    username, _password = credentials.split(":", maxsplit=1)
    safe_netloc = f"{username}:***@{host}"
    safe_uri = SplitResult(
        scheme=parsed.scheme,
        netloc=safe_netloc,
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return urlunsplit(safe_uri)


def setup_logging() -> None:
    logging.basicConfig(
        level  = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt= "%Y-%m-%d %H:%M:%S",
    )
