"""
bot/handlers.py - Telegram command handlers (THIN layer).

Rule: handler chi parse input -> build Task -> enqueue -> ack user.
Khong duoc lam heavy work o day.
"""

from __future__ import annotations

import logging

import telebot

from bot.meal_handlers import show_meal_home
from config import settings
from task_queue.models import Task, TaskType
from task_queue.producer import TaskQueue

logger = logging.getLogger(__name__)


def cmd_start(message: telebot.types.Message, bot: telebot.TeleBot) -> None:
    show_meal_home(
        message.chat.id,
        bot,
        intro_text=(
            "👋 *Chào mừng đến QueueBot*\n"
            "Bot hỗ trợ báo cơm theo tuần ngay trong Telegram."
        ),
    )


def cmd_slow(message: telebot.types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    parts = message.text.split()
    duration = 5
    if len(parts) >= 2:
        try:
            duration = max(1, min(int(parts[1]), 30))
        except ValueError:
            bot.reply_to(message, "Usage: /slow [seconds]  (1-30)")
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
    """Plain text khong phai command -> huong dan user dung menu dung chuc nang."""
    del task_queue
    bot.reply_to(
        message,
        "Chỉ hỗ trợ các lệnh đã đăng ký. Gõ `/` để xem danh sách lệnh hoặc dùng /baocom.",
        parse_mode="Markdown",
    )


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
