"""
tasks/handlers.py — Business logic cho từng TaskType.

Convention:
  - Signature: handle_<name>(task: Task, bot: TeleBot) -> None
  - Raise exception khi thất bại → worker xử lý retry
  - time.sleep() OK vì chạy trong worker thread (không phải async)
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request

import telebot

from task_queue.models import Task

logger = logging.getLogger(__name__)


def handle_echo(task: Task, bot: telebot.TeleBot) -> None:
    """Echo text của user trả lại."""
    text = task.payload.get("text", "(no text)")
    bot.send_message(task.chat_id, f"🔊 Echo: {text}")


def handle_reverse_text(task: Task, bot: telebot.TeleBot) -> None:
    """Đảo ngược chuỗi của user."""
    text = task.payload.get("text", "")
    bot.send_message(
        task.chat_id,
        f"🔄 Reversed: `{text[::-1]}`",
        parse_mode="Markdown",
    )


JOKE_API_URL = "https://official-joke-api.appspot.com/random_joke"

def handle_fetch_joke(task: Task, bot: telebot.TeleBot) -> None:
    """Lấy joke ngẫu nhiên từ public API."""
    req = urllib.request.Request(JOKE_API_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    bot.send_message(
        task.chat_id,
        f"😂 *{data.get('setup', '...')}*\n\n_{data.get('punchline', '...')}_",
        parse_mode="Markdown",
    )


def handle_slow_task(task: Task, bot: telebot.TeleBot) -> None:
    """Mô phỏng tác vụ nặng (ML inference, xử lý ảnh, v.v.)"""
    duration = task.payload.get("duration", 5)
    bot.send_message(task.chat_id, f"⚙️ Đang xử lý... (khoảng {duration}s)")
    time.sleep(duration)
    bot.send_message(task.chat_id, f"✅ Xong! Hoàn thành sau {duration}s.")