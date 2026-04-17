"""
main.py — Entry point.
"""

from __future__ import annotations

import logging
import signal
import sys

from config import setup_logging, settings
from bot import build_bot
from db import close as db_close, ping as db_ping
from task_queue import TaskQueue, WorkerPool

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    settings.validate()

    logger.info("=" * 55)
    logger.info("  Telegram Meal Bot")
    logger.info("  MongoDB : %s / %s", settings.safe_mongo_uri, settings.MONGO_DB_NAME)
    logger.info("  Workers : %d", settings.NUM_WORKERS)
    logger.info("=" * 55)

    # Kiểm tra kết nối MongoDB trước khi chạy
    if not db_ping():
        logger.error("Cannot connect to MongoDB. Check MONGO_URI in .env")
        sys.exit(1)

    task_queue  = TaskQueue(maxsize=settings.QUEUE_MAX_SIZE)
    bot         = build_bot(task_queue)
    worker_pool = WorkerPool(task_queue, bot, num_workers=settings.NUM_WORKERS)

    def _shutdown(signum, frame):
        logger.info("Received %s — shutting down…", signal.Signals(signum).name)
        bot.stop_polling()
        worker_pool.stop(drain_timeout=30.0)
        db_close()
        logger.info("Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    worker_pool.start()

    logger.info("Bot started. Press Ctrl+C to stop.")
    bot.infinity_polling(
        timeout             = 20,
        long_polling_timeout= 20,
        logger_level        = logging.WARNING,
        allowed_updates     = ["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
