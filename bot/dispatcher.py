"""
bot/dispatcher.py — Đăng ký tất cả handlers vào TeleBot instance.
"""

from __future__ import annotations

import functools
import logging

import telebot

from bot.handlers import (
    cmd_echo, cmd_joke, cmd_reverse, cmd_slow, cmd_start,
    cmd_status, on_text_message,
)
from bot.meal_handlers import (
    cmd_baocom, cmd_dangky, cmd_danhsach, cmd_huydangky,
    cmd_tonghop, cmd_xemcua, handle_meal_callback,
)
from config import settings
from task_queue.producer import TaskQueue

logger = logging.getLogger(__name__)


def build_bot(task_queue: TaskQueue) -> telebot.TeleBot:
    bot = telebot.TeleBot(
        token      = settings.BOT_TOKEN,
        parse_mode = None,
        threaded   = True,
        num_threads= 4,
    )

    def bind(fn):
        @functools.wraps(fn)
        def wrapper(message):
            fn(message, bot, task_queue)
        return wrapper

    # ── Lệnh cũ ──────────────────────────────────────────────────────────────
    bot.register_message_handler(lambda m: cmd_start(m, bot), commands=["start"])
    bot.register_message_handler(bind(cmd_echo),    commands=["echo"])
    bot.register_message_handler(bind(cmd_reverse), commands=["reverse"])
    bot.register_message_handler(bind(cmd_joke),    commands=["joke"])
    bot.register_message_handler(bind(cmd_slow),    commands=["slow"])
    bot.register_message_handler(bind(cmd_status),  commands=["status"])

    # ── Lệnh báo cơm ─────────────────────────────────────────────────────────
    bot.register_message_handler(bind(cmd_baocom),    commands=["baocom"])
    bot.register_message_handler(bind(cmd_xemcua),    commands=["xemcua"])
    bot.register_message_handler(bind(cmd_dangky),    commands=["dangky"])
    bot.register_message_handler(bind(cmd_huydangky), commands=["huydangky"])
    bot.register_message_handler(bind(cmd_tonghop),   commands=["tonghop"])
    bot.register_message_handler(bind(cmd_danhsach),  commands=["danhsach"])

    # ── Callback từ InlineKeyboard ────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda call: call.data.startswith("meal_"))
    def on_meal_callback(call):
        handle_meal_callback(call, bot, task_queue)

    # ── Fallback text ─────────────────────────────────────────────────────────
    bot.register_message_handler(
        bind(on_text_message),
        content_types=["text"],
        func=lambda msg: msg.text is not None and not msg.text.startswith("/"),
    )

    logger.info("Bot handlers registered (meal feature enabled).")
    return bot