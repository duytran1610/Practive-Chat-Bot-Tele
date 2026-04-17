"""
tasks/handlers.py - Business logic cho cac TaskType con duoc su dung.

Convention:
  - Signature: handle_<name>(task: Task, bot: TeleBot) -> None
  - Raise exception khi that bai -> worker xu ly retry
  - time.sleep() OK vi chay trong worker thread
"""

from __future__ import annotations

import logging
import time

import telebot

from task_queue.models import Task

logger = logging.getLogger(__name__)


def handle_slow_task(task: Task, bot: telebot.TeleBot) -> None:
    """Mo phong tac vu nang (ML inference, xu ly anh, v.v.)."""
    duration = task.payload.get("duration", 5)
    bot.send_message(task.chat_id, f"⚙️ Đang xử lý... (khoảng {duration}s)")
    time.sleep(duration)
    bot.send_message(task.chat_id, f"✅ Xong! Hoàn thành sau {duration}s.")
