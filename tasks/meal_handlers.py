"""
tasks/meal_handlers.py — Handler xử lý các task báo cơm.

Mỗi handler:
  1. Đọc payload từ Task
  2. Gọi MealRepository để đọc/ghi MongoDB
  3. bot.send_message() để trả kết quả về user
"""

from __future__ import annotations

import logging

import telebot

from db import MealRepository
from task_queue.models import Task

logger = logging.getLogger(__name__)


def _repo() -> MealRepository:
    """Factory: tạo MealRepository mới mỗi lần gọi (dùng chung connection pool)."""
    return MealRepository()


# ─────────────────────────────────────────────────────────────────────────────
# MEAL_REGISTER — đăng ký / huỷ 1 bữa cụ thể
# payload: {user_id, username, day, meal, value}
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_register(task: Task, bot: telebot.TeleBot) -> None:
    p        = task.payload
    repo     = _repo()
    doc      = repo.set_meal(
        user_id  = p["user_id"],
        username = p["username"],
        day      = p["day"],
        meal     = p["meal"],
        value    = p["value"],
    )
    summary = _format_meal_summary(doc)
    status  = "✅ Đã đăng ký" if p["value"] else "❌ Đã huỷ"
    bot.send_message(
        task.chat_id,
        f"{status} *{p['meal_vi']}* ngày *{p['day_vi']}*\n\n{summary}",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MEAL_DAY — đăng ký cả ngày (sáng + trưa + tối)
# payload: {user_id, username, day, values: {morning, afternoon, evening}}
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_day(task: Task, bot: telebot.TeleBot) -> None:
    p    = task.payload
    repo = _repo()
    doc  = repo.set_day(
        user_id  = p["user_id"],
        username = p["username"],
        day      = p["day"],
        values   = p["values"],
    )
    summary = _format_meal_summary(doc)
    bot.send_message(
        task.chat_id,
        f"✅ Đã cập nhật *{p['day_vi']}*\n\n{summary}",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MEAL_ALL — đăng ký hoặc huỷ toàn bộ tuần
# payload: {user_id, username, value}
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_all(task: Task, bot: telebot.TeleBot) -> None:
    p    = task.payload
    repo = _repo()
    doc  = repo.set_all(
        user_id  = p["user_id"],
        username = p["username"],
        value    = p["value"],
    )
    action  = "✅ Đã đăng ký" if p["value"] else "❌ Đã huỷ"
    summary = _format_meal_summary(doc)
    bot.send_message(
        task.chat_id,
        f"{action} *toàn bộ bữa trong tuần*\n\n{summary}",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MEAL_VIEW — xem báo cơm tuần này của chính mình
# payload: {user_id, username}
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_view(task: Task, bot: telebot.TeleBot) -> None:
    p       = task.payload
    repo    = _repo()
    summary = repo.get_my_report(p["user_id"], p["username"])
    bot.send_message(task.chat_id, summary, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────────────────
# MEAL_SUMMARY — tổng hợp cả tuần (admin)
# payload: {}
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_summary(task: Task, bot: telebot.TeleBot) -> None:
    repo    = _repo()
    summary = repo.get_week_summary()
    bot.send_message(task.chat_id, summary, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────────────────
# MEAL_STAFF — danh sách nhân viên đã báo cơm
# payload: {}
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_staff(task: Task, bot: telebot.TeleBot) -> None:
    repo    = _repo()
    summary = repo.get_staff_list()
    bot.send_message(task.chat_id, summary, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────────────────
# Private helper — dùng lại format từ db/models.py
# ─────────────────────────────────────────────────────────────────────────────

def _format_meal_summary(doc: dict) -> str:
    from db.models import format_meal_summary
    return format_meal_summary(doc)