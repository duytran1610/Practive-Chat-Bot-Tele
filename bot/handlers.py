"""
bot/handlers.py — Telegram command handlers (THIN layer).

Rule: handler chỉ parse input → build Task → enqueue → ack user.
Không được làm heavy work ở đây.
"""

from __future__ import annotations

import logging

import telebot

from config import settings
from task_queue.models import Task, TaskType
from task_queue.producer import TaskQueue

logger = logging.getLogger(__name__)


def cmd_start(message: telebot.types.Message, bot: telebot.TeleBot) -> None:
    bot.send_message(
        message.chat.id,
        "👋 *Welcome to QueueBot!*\n\n"
        "Requests được xử lý bất đồng bộ bởi worker pool.\n\n"
        "*Commands:*\n"
        "/echo `<text>`     — Echo lại text\n"
        "/reverse `<text>`  — Đảo ngược text\n"
        "/joke              — Lấy joke ngẫu nhiên\n"
        "/slow `[seconds]`  — Giả lập tác vụ chậm (1–30s)\n"
        "/status            — Thống kê queue\n",
        parse_mode="Markdown",
    )


def cmd_echo(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /echo <text>")
        return
    _enqueue_and_ack(
        Task(task_type=TaskType.ECHO, chat_id=message.chat.id,
             payload={"text": parts[1]}, max_retries=settings.MAX_RETRIES),
        task_queue, message, bot,
    )


def cmd_reverse(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /reverse <text>")
        return
    _enqueue_and_ack(
        Task(task_type=TaskType.REVERSE_TEXT, chat_id=message.chat.id,
             payload={"text": parts[1]}, max_retries=settings.MAX_RETRIES),
        task_queue, message, bot,
    )


def cmd_joke(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    _enqueue_and_ack(
        Task(task_type=TaskType.FETCH_JOKE, chat_id=message.chat.id,
             max_retries=settings.MAX_RETRIES),
        task_queue, message, bot,
    )


def cmd_slow(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    parts = message.text.split()
    duration = 5
    if len(parts) >= 2:
        try:
            duration = max(1, min(int(parts[1]), 30))
        except ValueError:
            bot.reply_to(message, "Usage: /slow [seconds]  (1–30)")
            return
    _enqueue_and_ack(
        Task(task_type=TaskType.SLOW_TASK, chat_id=message.chat.id,
             payload={"duration": duration}, max_retries=settings.MAX_RETRIES),
        task_queue, message, bot,
    )


def cmd_status(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    s = task_queue.stats
    bot.send_message(
        message.chat.id,
        "📊 *Queue Status*\n\n"
        f"• Current size  : `{s['current_size']}`\n"
        f"• Max size      : `{s['max_size']}`\n"
        f"• Total enqueued: `{s['enqueued_total']}`\n"
        f"• Total dropped : `{s['dropped_total']}`\n"
        f"• Workers       : `{settings.NUM_WORKERS}`\n",
        parse_mode="Markdown",
    )


def on_text_message(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    """Plain text không phải command → xử lý như echo."""
    _enqueue_and_ack(
        Task(task_type=TaskType.ECHO, chat_id=message.chat.id,
             payload={"text": message.text or ""}, max_retries=settings.MAX_RETRIES),
        task_queue, message, bot,
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _enqueue_and_ack(
    task: Task,
    task_queue: TaskQueue,
    message: telebot.types.Message,
    bot: telebot.TeleBot,
) -> None:
    if task_queue.enqueue(task):
        bot.reply_to(
            message,
            f"✅ Đã nhận! ID: `{task.short_id()}`\nSẽ trả lời khi xong.",
            parse_mode="Markdown",
        )
    else:
        bot.reply_to(message, "⚠️ Server đang bận. Vui lòng thử lại sau.")