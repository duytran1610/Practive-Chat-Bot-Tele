"""
config.py — Centralized configuration loaded from environment / .env file.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str      = os.getenv("BOT_TOKEN", "")

    # ── Queue / Worker ────────────────────────────────────────────────────────
    NUM_WORKERS: int    = int(os.getenv("NUM_WORKERS", "3"))
    QUEUE_MAX_SIZE: int = int(os.getenv("QUEUE_MAX_SIZE", "500"))

    # ── Retry ─────────────────────────────────────────────────────────────────
    MAX_RETRIES: int        = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "2.0"))

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Admin alert (optional) ────────────────────────────────────────────────
    ADMIN_CHAT_ID: int | None = (
        int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
    )

    def validate(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set. Check your .env file.")
        if self.NUM_WORKERS < 1:
            raise ValueError("NUM_WORKERS must be >= 1")


settings = Settings()


def setup_logging() -> None:
    """Configure root logger with a readable format."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )