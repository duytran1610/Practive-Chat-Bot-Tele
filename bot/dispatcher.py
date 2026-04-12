"""
bot/dispatcher.py — Tạo TeleBot và đăng ký tất cả handlers.

Dùng register_message_handler() (programmatic) thay vì decorator
để tách biệt config khỏi logic và dễ test hơn.

Dependency injection: task_queue được bind vào handler qua functools.partial.
"""

from __future__ import annotations

import functools
import logging

import telebot

from bot.handlers import (
    cmd_echo,
    cmd_joke,
    cmd_reverse,
    cmd_slow,
    cmd_start,
    cmd_status,
    on_text_message,
)
from config import settings
from task_queue.producer import TaskQueue

logger = logging.getLogger(__name__)


def build_bot(task_queue: TaskQueue) -> telebot.TeleBot:
    """
    Factory: tạo và cấu hình TeleBot hoàn chỉnh.

    Args:
        task_queue: Queue dùng chung, inject vào mỗi handler.

    Returns:
        TeleBot đã đăng ký handlers, chưa polling.
    """
    bot = telebot.TeleBot(
        token=settings.BOT_TOKEN,
        parse_mode=None,
        threaded=True,
        num_threads=4,
    )

    def bind(fn):
        """Bind (bot, task_queue) vào handler, trả về wrapper nhận (message,)."""
        @functools.wraps(fn)
        def wrapper(message):
            fn(message, bot, task_queue)
        return wrapper

    # Commands
    bot.register_message_handler(
        lambda msg: cmd_start(msg, bot),
        commands=["start"],
    )
    bot.register_message_handler(bind(cmd_echo),    commands=["echo"])
    bot.register_message_handler(bind(cmd_reverse), commands=["reverse"])
    bot.register_message_handler(bind(cmd_joke),    commands=["joke"])
    bot.register_message_handler(bind(cmd_slow),    commands=["slow"])
    bot.register_message_handler(bind(cmd_status),  commands=["status"])

    # Fallback: text không phải command
    bot.register_message_handler(
        bind(on_text_message),
        content_types=["text"],
        func=lambda msg: msg.text is not None and not msg.text.startswith("/"),
    )

    logger.info("Bot handlers registered.")
    return bot