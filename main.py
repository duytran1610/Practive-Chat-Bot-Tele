"""
main.py — Entry point.

Lifecycle:
  1. Validate config & setup logging
  2. Tạo TaskQueue dùng chung
  3. Build TeleBot + đăng ký handlers
  4. Start WorkerPool (N threads)
  5. infinity_polling (block tại đây)
  6. SIGINT/SIGTERM → graceful shutdown

Run:
    cp .env.example .env   # điền BOT_TOKEN
    pip install -r requirements.txt
    python main.py
"""

from __future__ import annotations

import logging
import signal
import sys

from config import setup_logging, settings
from bot import build_bot
from task_queue import TaskQueue, WorkerPool

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    settings.validate()

    logger.info("=" * 50)
    logger.info("  Telegram Queue Bot  (pyTelegramBotAPI)")
    logger.info("  Workers   : %d", settings.NUM_WORKERS)
    logger.info("  Queue max : %d", settings.QUEUE_MAX_SIZE)
    logger.info("=" * 50)

    task_queue  = TaskQueue(maxsize=settings.QUEUE_MAX_SIZE)
    bot         = build_bot(task_queue)
    worker_pool = WorkerPool(task_queue, bot, num_workers=settings.NUM_WORKERS)

    def _shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — shutting down…", sig_name)
        bot.stop_polling()
        worker_pool.stop(drain_timeout=30.0)
        logger.info("Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    worker_pool.start()

    logger.info("Bot started. Ctrl+C to stop.")
    bot.infinity_polling(
        timeout=20,
        long_polling_timeout=20,
        logger_level=logging.WARNING,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    main()