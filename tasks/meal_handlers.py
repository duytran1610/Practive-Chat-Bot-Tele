"""
tasks/meal_handlers.py - Handler xu ly cac task bao com.

Moi handler:
  1. Doc payload tu Task
  2. Goi MealRepository de doc/ghi MongoDB
  3. bot.send_message() de tra ket qua ve user
"""

from __future__ import annotations

import logging
from datetime import datetime

import telebot

from db import MealRepository
from db.meal_rules import (
    MealRegistrationError,
    ensure_week_has_open_days,
    format_days_vi,
)
from db.models import TZ_VN
from task_queue.models import Task

logger = logging.getLogger(__name__)


def _repo() -> MealRepository:
    """Factory: tao MealRepository moi moi lan goi."""
    return MealRepository()


def _send_business_error(task: Task, bot: telebot.TeleBot, error: MealRegistrationError) -> None:
    """Gui loi nghiep vu cho user ma khong retry."""
    bot.send_message(task.chat_id, f"⛔ {error}", parse_mode="Markdown")


def _refresh_day_menu(task: Task, bot: telebot.TeleBot, day: str, doc: dict) -> None:
    """Cap nhat lai menu cua ngay sau khi doi trang thai."""
    message_id = task.payload.get("message_id")
    if not message_id:
        return

    from bot.meal_handlers import build_day_menu_keyboard, build_day_menu_text

    meal_states = doc.get("meals", {}).get(day, {})
    bot.edit_message_text(
        chat_id=task.chat_id,
        message_id=message_id,
        text=build_day_menu_text(day, meal_states=meal_states),
        parse_mode="Markdown",
        reply_markup=build_day_menu_keyboard(day, meal_states=meal_states),
    )


def handle_meal_register(task: Task, bot: telebot.TeleBot) -> None:
    p = task.payload
    repo = _repo()
    now = datetime.now(TZ_VN)
    try:
        doc = repo.set_meal(
            user_id=p["user_id"],
            username=p["username"],
            day=p["day"],
            meal=p["meal"],
            value=p["value"],
            now=now,
        )
    except MealRegistrationError as error:
        _send_business_error(task, bot, error)
        return

    _refresh_day_menu(task, bot, p["day"], doc)


def handle_meal_day(task: Task, bot: telebot.TeleBot) -> None:
    p = task.payload
    repo = _repo()
    now = datetime.now(TZ_VN)
    try:
        doc = repo.set_day(
            user_id=p["user_id"],
            username=p["username"],
            day=p["day"],
            values=p["values"],
            now=now,
        )
    except MealRegistrationError as error:
        _send_business_error(task, bot, error)
        return

    _refresh_day_menu(task, bot, p["day"], doc)


def handle_meal_all(task: Task, bot: telebot.TeleBot) -> None:
    p = task.payload
    repo = _repo()
    now = datetime.now(TZ_VN)
    try:
        open_days = ensure_week_has_open_days(now=now)
        doc = repo.set_all(
            user_id=p["user_id"],
            username=p["username"],
            value=p["value"],
            now=now,
        )
    except MealRegistrationError as error:
        _send_business_error(task, bot, error)
        return

    action = "✅ Đã đăng ký" if p["value"] else "❌ Đã hủy"
    summary = _format_meal_summary(doc)
    bot.send_message(
        task.chat_id,
        f"{action} các ngày còn mở: *{format_days_vi(open_days)}*\n\n{summary}",
        parse_mode="Markdown",
    )


def handle_meal_view(task: Task, bot: telebot.TeleBot) -> None:
    p = task.payload
    repo = _repo()
    summary = repo.get_my_report(p["user_id"], p["username"])
    bot.send_message(task.chat_id, summary, parse_mode="Markdown")


def handle_meal_summary(task: Task, bot: telebot.TeleBot) -> None:
    repo = _repo()
    summary = repo.get_week_summary()
    bot.send_message(task.chat_id, summary, parse_mode="Markdown")


def handle_meal_staff(task: Task, bot: telebot.TeleBot) -> None:
    repo = _repo()
    summary = repo.get_staff_list()
    bot.send_message(task.chat_id, summary, parse_mode="Markdown")


def _format_meal_summary(doc: dict) -> str:
    from db.models import format_meal_summary
    return format_meal_summary(doc)
