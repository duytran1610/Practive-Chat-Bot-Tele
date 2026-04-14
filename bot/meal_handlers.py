"""
bot/meal_handlers.py — Telegram handlers cho tính năng báo cơm.

Luồng:
  User gõ lệnh
    → handler parse input
    → tạo Task với payload đầy đủ
    → enqueue
    → ack ngay "✅ Đang xử lý..."

Các lệnh:
  /baocom              → menu chọn ngày + bữa (InlineKeyboard)
  /xemcua              → xem báo cơm của chính mình
  /dangky              → đăng ký toàn bộ tuần
  /huydangky           → huỷ toàn bộ tuần
  /tonghop             → tổng hợp tuần (admin)
  /danhsach            → danh sách nhân viên đã báo
"""

from __future__ import annotations

import logging

import telebot
import telebot.types as types

from config import settings
from db.models import DAYS_ORDER, DAYS_VI, MEALS_ORDER, MEALS_VI
from task_queue.models import Task, TaskType
from task_queue.producer import TaskQueue

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_info(message: types.Message) -> tuple[int, str]:
    """Trả về (user_id, display_name) từ message."""
    user = message.from_user
    if user.username:
        name = f"@{user.username}"
    else:
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"user_{user.id}"
    return user.id, name


def _enqueue(task: Task, task_queue: TaskQueue, message: types.Message, bot: telebot.TeleBot) -> None:
    if task_queue.enqueue(task):
        bot.reply_to(message, "⏳ Đang xử lý...", parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ Server bận, thử lại sau.")


# ─────────────────────────────────────────────────────────────────────────────
# /baocom — Hiển thị InlineKeyboard chọn ngày + bữa
# ─────────────────────────────────────────────────────────────────────────────

def cmd_baocom(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    """Hiển thị menu chọn ngày để báo cơm."""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons  = []

    for day in DAYS_ORDER:
        buttons.append(
            types.InlineKeyboardButton(
                text          = DAYS_VI[day],
                callback_data = f"meal_day_menu:{day}",
            )
        )
    keyboard.add(*buttons)
    keyboard.add(
        types.InlineKeyboardButton("✅ Đăng ký cả tuần",  callback_data="meal_all:true"),
        types.InlineKeyboardButton("❌ Huỷ cả tuần",      callback_data="meal_all:false"),
    )
    keyboard.add(
        types.InlineKeyboardButton("📋 Xem báo cơm của tôi", callback_data="meal_view"),
    )

    bot.send_message(
        message.chat.id,
        "🍱 *Báo cơm tuần này*\nChọn ngày muốn đăng ký:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /xemcua — Xem báo cơm của mình
# ─────────────────────────────────────────────────────────────────────────────

def cmd_xemcua(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    user_id, username = _get_user_info(message)
    task = Task(
        task_type = TaskType.MEAL_VIEW,
        chat_id   = message.chat.id,
        payload   = {"user_id": user_id, "username": username},
        max_retries = settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


# ─────────────────────────────────────────────────────────────────────────────
# /dangky — Đăng ký cả tuần
# ─────────────────────────────────────────────────────────────────────────────

def cmd_dangky(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    user_id, username = _get_user_info(message)
    task = Task(
        task_type = TaskType.MEAL_ALL,
        chat_id   = message.chat.id,
        payload   = {"user_id": user_id, "username": username, "value": True},
        max_retries = settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


# ─────────────────────────────────────────────────────────────────────────────
# /huydangky — Huỷ cả tuần
# ─────────────────────────────────────────────────────────────────────────────

def cmd_huydangky(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    user_id, username = _get_user_info(message)
    task = Task(
        task_type = TaskType.MEAL_ALL,
        chat_id   = message.chat.id,
        payload   = {"user_id": user_id, "username": username, "value": False},
        max_retries = settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


# ─────────────────────────────────────────────────────────────────────────────
# /tonghop — Tổng hợp tuần (chỉ admin)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_tonghop(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    if settings.ADMIN_CHAT_ID and message.chat.id != settings.ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ Chỉ admin mới dùng được lệnh này.")
        return
    task = Task(
        task_type   = TaskType.MEAL_SUMMARY,
        chat_id     = message.chat.id,
        max_retries = settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


# ─────────────────────────────────────────────────────────────────────────────
# /danhsach — Danh sách nhân viên đã báo
# ─────────────────────────────────────────────────────────────────────────────

def cmd_danhsach(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    task = Task(
        task_type   = TaskType.MEAL_STAFF,
        chat_id     = message.chat.id,
        max_retries = settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


# ─────────────────────────────────────────────────────────────────────────────
# Callback handler — xử lý bấm nút InlineKeyboard
# ─────────────────────────────────────────────────────────────────────────────

def handle_meal_callback(
    call      : types.CallbackQuery,
    bot       : telebot.TeleBot,
    task_queue: TaskQueue,
) -> None:
    """
    Routing callback_data:
      meal_day_menu:<day>              → Hiển thị sub-menu chọn bữa
      meal_toggle:<day>:<meal>:<0|1>  → Toggle 1 bữa
      meal_all:<true|false>           → Đăng ký / huỷ cả tuần
      meal_view                       → Xem báo cơm
    """
    bot.answer_callback_query(call.id)  # Tắt loading spinner trên nút

    data     = call.data
    user     = call.from_user
    user_id  = user.id
    username = (f"@{user.username}" if user.username
                else f"{user.first_name or ''} {user.last_name or ''}".strip())
    chat_id  = call.message.chat.id

    # ── meal_day_menu:<day> ──────────────────────────────────────────────────
    if data.startswith("meal_day_menu:"):
        day = data.split(":")[1]
        _show_meal_sub_menu(call, bot, day)

    # ── meal_toggle:<day>:<meal>:<0|1> ───────────────────────────────────────
    elif data.startswith("meal_toggle:"):
        _, day, meal, val = data.split(":")
        value = val == "1"
        task  = Task(
            task_type = TaskType.MEAL_REGISTER,
            chat_id   = chat_id,
            payload   = {
                "user_id" : user_id,
                "username": username,
                "day"     : day,
                "meal"    : meal,
                "value"   : value,
                "day_vi"  : DAYS_VI[day],
                "meal_vi" : MEALS_VI[meal],
            },
            max_retries = settings.MAX_RETRIES,
        )
        if task_queue.enqueue(task):
            bot.edit_message_text(
                chat_id    = chat_id,
                message_id = call.message.message_id,
                text       = f"⏳ Đang cập nhật *{MEALS_VI[meal]}* ngày *{DAYS_VI[day]}*...",
                parse_mode = "Markdown",
            )
        else:
            bot.answer_callback_query(call.id, "⚠️ Server bận, thử lại sau.", show_alert=True)

    # ── meal_all:<true|false> ────────────────────────────────────────────────
    elif data.startswith("meal_all:"):
        value = data.split(":")[1] == "true"
        task  = Task(
            task_type = TaskType.MEAL_ALL,
            chat_id   = chat_id,
            payload   = {"user_id": user_id, "username": username, "value": value},
            max_retries = settings.MAX_RETRIES,
        )
        if task_queue.enqueue(task):
            label = "toàn bộ tuần" if value else "huỷ cả tuần"
            bot.edit_message_text(
                chat_id    = chat_id,
                message_id = call.message.message_id,
                text       = f"⏳ Đang {'đăng ký' if value else 'huỷ'} {label}...",
                parse_mode = "Markdown",
            )

    # ── meal_view ────────────────────────────────────────────────────────────
    elif data == "meal_view":
        task = Task(
            task_type   = TaskType.MEAL_VIEW,
            chat_id     = chat_id,
            payload     = {"user_id": user_id, "username": username},
            max_retries = settings.MAX_RETRIES,
        )
        task_queue.enqueue(task)


def _show_meal_sub_menu(
    call: types.CallbackQuery,
    bot : telebot.TeleBot,
    day : str,
) -> None:
    """Hiển thị sub-menu chọn bữa (Sáng/Trưa/Tối) cho 1 ngày."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    meal_icons = {"morning": "☀️", "afternoon": "🌤", "evening": "🌙"}

    for meal in MEALS_ORDER:
        keyboard.add(
            types.InlineKeyboardButton(
                f"{meal_icons[meal]} {MEALS_VI[meal]} ✅",
                callback_data=f"meal_toggle:{day}:{meal}:1",
            ),
            types.InlineKeyboardButton(
                f"{meal_icons[meal]} {MEALS_VI[meal]} ❌",
                callback_data=f"meal_toggle:{day}:{meal}:0",
            ),
        )

    keyboard.add(
        types.InlineKeyboardButton("⬅️ Quay lại", callback_data="meal_back"),
    )

    bot.edit_message_text(
        chat_id    = call.message.chat.id,
        message_id = call.message.message_id,
        text       = f"🍱 *{DAYS_VI[day]}* — Chọn bữa:",
        parse_mode = "Markdown",
        reply_markup = keyboard,
    )