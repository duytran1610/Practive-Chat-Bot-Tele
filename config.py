"""
config.py — Centralized configuration.
"""

from __future__ import annotations

import logging
import os

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

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Admin ─────────────────────────────────────────────────────────────────
    ADMIN_CHAT_ID: int | None = (
        int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
    )

    def validate(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set.")


settings = Settings()


def setup_logging() -> None:
    logging.basicConfig(
        level  = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt= "%Y-%m-%d %H:%M:%S",
    )