"""
bot/meal_handlers.py - Telegram handlers cho tinh nang bao com.

Luong:
  User go lenh / bam nut
    -> handler parse input
    -> tao Task voi payload day du
    -> enqueue
    -> ack ngay hoac cap nhat menu
"""

from __future__ import annotations

import logging
from datetime import datetime

import telebot
import telebot.types as types

from config import settings
from db.meal_rules import (
    MealRegistrationError,
    build_day_closed_message,
    ensure_week_has_open_days,
    format_days_vi,
    get_meal_day_deadline,
    get_open_days,
    is_meal_day_open,
    normalize_now,
)
from db.models import DAYS_ORDER, DAYS_VI, MEALS_ORDER, MEALS_VI
from task_queue.models import Task, TaskType
from task_queue.producer import TaskQueue

logger = logging.getLogger(__name__)


def _get_user_info(message: types.Message) -> tuple[int, str]:
    """Tra ve (user_id, display_name) tu message."""
    user = message.from_user
    if user.username:
        name = f"@{user.username}"
    else:
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"user_{user.id}"
    return user.id, name


def _build_callback_username(call: types.CallbackQuery) -> str:
    """Tra ve ten hien thi tu callback user."""
    user = call.from_user
    if user.username:
        return f"@{user.username}"
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or f"user_{user.id}"


def _get_day_states(user_id: int, username: str, day: str) -> dict[str, bool]:
    """Lay trang thai cac bua hien tai cua mot ngay."""
    from db import MealRepository

    doc = MealRepository().get_or_create(user_id, username)
    return doc.get("meals", {}).get(day, {})


def _serialize_meal_states(meal_states: dict[str, bool] | None = None) -> str:
    """Ma hoa trang thai 3 bua thanh chuoi ngan cho callback_data."""
    states = meal_states or {}
    return "".join("1" if states.get(meal, False) else "0" for meal in MEALS_ORDER)


def _deserialize_meal_states(state_code: str) -> dict[str, bool]:
    """Giai ma callback_data thanh trang thai bua an."""
    if len(state_code) != len(MEALS_ORDER) or any(bit not in {"0", "1"} for bit in state_code):
        raise ValueError(f"Invalid state_code: {state_code}")
    return {
        meal: state_code[index] == "1"
        for index, meal in enumerate(MEALS_ORDER)
    }


def _toggle_meal_state(state_code: str, meal: str) -> dict[str, bool]:
    """Dao trang thai cua 1 bua trong state_code."""
    states = _deserialize_meal_states(state_code)
    states[meal] = not states[meal]
    return states


def _is_admin_chat(chat_id: int) -> bool:
    """Kiem tra chat hien tai co phai admin khong."""
    return settings.ADMIN_CHAT_ID is not None and chat_id == settings.ADMIN_CHAT_ID


def build_main_menu_text(is_admin: bool, now: datetime | None = None) -> str:
    """Tao noi dung cho menu chinh."""
    current = normalize_now(now)
    open_days = get_open_days(now=current)
    lines = [
        "🍱 *Báo cơm tuần này*",
        "",
        f"Hạn chót: trước *{settings.MEAL_REGISTRATION_CUTOFF_HOUR}:00* của ngày hôm trước.",
    ]
    if open_days:
        lines.append(f"Ngày còn mở: *{format_days_vi(open_days)}*.")
    else:
        lines.append("Tuần này không còn ngày nào mở để báo cơm.")
    lines.extend(
        [
            "",
            "Chọn thao tác nhanh bên dưới:",
            "• Theo ngày: chỉ các ngày còn mở mới bấm được.",
            "• Theo tuần: chỉ cập nhật các ngày còn mở trong tuần hiện tại.",
            "• Tra cứu: xem báo cơm của bạn và danh sách nhân viên đã báo.",
        ]
    )
    if is_admin:
        lines.append("• Admin: xem tổng hợp suất ăn của cả tuần.")
    return "\n".join(lines)


def build_main_menu_keyboard(
    is_admin: bool,
    now: datetime | None = None,
) -> types.InlineKeyboardMarkup:
    """Tao keyboard cho menu chinh."""
    current = normalize_now(now)
    open_days = set(get_open_days(now=current))
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    day_buttons = []

    for day in DAYS_ORDER:
        if day in open_days:
            day_buttons.append(
                types.InlineKeyboardButton(
                    text=f"🟢 {DAYS_VI[day]}",
                    callback_data=f"meal_day_menu:{day}",
                )
            )
        else:
            day_buttons.append(
                types.InlineKeyboardButton(
                    text=f"🔒 {DAYS_VI[day]}",
                    callback_data=f"meal_locked:{day}",
                )
            )

    for index in range(0, len(day_buttons), 2):
        keyboard.add(*day_buttons[index:index + 2])

    if open_days:
        keyboard.add(
            types.InlineKeyboardButton("✅ Đăng ký các ngày mở", callback_data="meal_all:true"),
            types.InlineKeyboardButton("❌ Hủy các ngày mở", callback_data="meal_all:false"),
        )
    else:
        keyboard.add(
            types.InlineKeyboardButton("🔒 Không còn ngày mở", callback_data="meal_week_locked"),
        )

    keyboard.add(
        types.InlineKeyboardButton("📄 Báo cơm của tôi", callback_data="meal_view"),
        types.InlineKeyboardButton("👥 Danh sách đã báo", callback_data="meal_staff"),
    )
    if is_admin:
        keyboard.add(
            types.InlineKeyboardButton("📊 Tổng hợp tuần", callback_data="meal_summary"),
        )
    return keyboard


def build_day_menu_text(
    day: str,
    now: datetime | None = None,
    meal_states: dict[str, bool] | None = None,
) -> str:
    """Tao text cho menu theo ngay."""
    current = normalize_now(now)
    deadline = get_meal_day_deadline(day, now=current)
    if not is_meal_day_open(day, now=current):
        return (
            f"🔒 *{DAYS_VI[day]}* đã khóa\n"
            f"Hạn chót là trước *{deadline.strftime('%H:%M %d/%m/%Y')}*."
        )

    states = meal_states or {}
    state_text = " | ".join(
        f"{MEALS_VI[meal]}={'True' if states.get(meal, False) else 'False'}"
        for meal in MEALS_ORDER
    )
    return (
        f"🍱 *{DAYS_VI[day]}*\n"
        f"Hạn chót: trước *{deadline.strftime('%H:%M %d/%m/%Y')}*.\n"
        f"Trạng thái hiện tại: {state_text}\n"
        "Bấm checkbox để đổi True/False rồi nhấn *Xác nhận* để gửi."
    )


def build_day_menu_keyboard(
    day: str,
    now: datetime | None = None,
    meal_states: dict[str, bool] | None = None,
) -> types.InlineKeyboardMarkup:
    """Tao keyboard cho menu theo ngay."""
    current = normalize_now(now)
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    if is_meal_day_open(day, now=current):
        states = meal_states or {}
        state_code = _serialize_meal_states(states)
        for meal in MEALS_ORDER:
            current_value = states.get(meal, False)
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{'☑️' if current_value else '☐'} {MEALS_VI[meal]}",
                    callback_data=f"meal_day_toggle:{day}:{state_code}:{meal}",
                ),
            )

        keyboard.add(
            types.InlineKeyboardButton("✅ Xác nhận", callback_data=f"meal_day_submit:{day}:{state_code}"),
        )
    else:
        keyboard.add(
            types.InlineKeyboardButton("🔒 Đã quá hạn", callback_data=f"meal_locked:{day}"),
        )

    keyboard.add(
        types.InlineKeyboardButton("📄 Xem tuần của tôi", callback_data="meal_view"),
    )
    keyboard.add(
        types.InlineKeyboardButton("⬅️ Quay lại menu", callback_data="meal_menu"),
    )
    return keyboard


def show_meal_home(
    chat_id: int,
    bot: telebot.TeleBot,
    *,
    intro_text: str | None = None,
    now: datetime | None = None,
) -> None:
    """Gui menu chinh bao com."""
    current = normalize_now(now)
    is_admin = _is_admin_chat(chat_id)
    text = build_main_menu_text(is_admin, now=current)
    if intro_text:
        text = f"{intro_text}\n\n{text}"
    bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=build_main_menu_keyboard(is_admin, now=current),
    )


def _enqueue(task: Task, task_queue: TaskQueue, message: types.Message, bot: telebot.TeleBot) -> None:
    if task_queue.enqueue(task):
        bot.reply_to(message, "⏳ Đang xử lý...", parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ Server bận, thử lại sau.")


def _enqueue_from_callback(
    task: Task,
    task_queue: TaskQueue,
    call: types.CallbackQuery,
    bot: telebot.TeleBot,
    loading_text: str,
) -> None:
    """Enqueue task tu callback va cap nhat message hien tai."""
    if task_queue.enqueue(task):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=loading_text,
            parse_mode="Markdown",
        )
    else:
        bot.answer_callback_query(call.id, "⚠️ Server bận, thử lại sau.", show_alert=True)


def _show_day_menu(call: types.CallbackQuery, bot: telebot.TeleBot, day: str) -> None:
    """Hien thi menu thao tac cua mot ngay."""
    current = normalize_now()
    meal_states = _get_day_states(call.from_user.id, _build_callback_username(call), day)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=build_day_menu_text(day, now=current, meal_states=meal_states),
        parse_mode="Markdown",
        reply_markup=build_day_menu_keyboard(day, now=current, meal_states=meal_states),
    )


def _show_main_menu(call: types.CallbackQuery, bot: telebot.TeleBot) -> None:
    """Quay lai menu chinh."""
    current = normalize_now()
    is_admin = _is_admin_chat(call.message.chat.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=build_main_menu_text(is_admin, now=current),
        parse_mode="Markdown",
        reply_markup=build_main_menu_keyboard(is_admin, now=current),
    )


def cmd_baocom(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    """Hien thi menu chinh bao com."""
    del task_queue
    show_meal_home(message.chat.id, bot)


def cmd_xemcua(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    user_id, username = _get_user_info(message)
    task = Task(
        task_type=TaskType.MEAL_VIEW,
        chat_id=message.chat.id,
        payload={"user_id": user_id, "username": username},
        max_retries=settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


def cmd_dangky(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    user_id, username = _get_user_info(message)
    task = Task(
        task_type=TaskType.MEAL_ALL,
        chat_id=message.chat.id,
        payload={"user_id": user_id, "username": username, "value": True},
        max_retries=settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


def cmd_huydangky(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    user_id, username = _get_user_info(message)
    task = Task(
        task_type=TaskType.MEAL_ALL,
        chat_id=message.chat.id,
        payload={"user_id": user_id, "username": username, "value": False},
        max_retries=settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


def cmd_tonghop(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    if not _is_admin_chat(message.chat.id):
        bot.reply_to(message, "⛔ Chỉ admin mới dùng được lệnh này.")
        return
    task = Task(
        task_type=TaskType.MEAL_SUMMARY,
        chat_id=message.chat.id,
        max_retries=settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


def cmd_danhsach(message: types.Message, bot: telebot.TeleBot, task_queue: TaskQueue) -> None:
    task = Task(
        task_type=TaskType.MEAL_STAFF,
        chat_id=message.chat.id,
        max_retries=settings.MAX_RETRIES,
    )
    _enqueue(task, task_queue, message, bot)


def _answer_locked_day(call: types.CallbackQuery, day: str, bot: telebot.TeleBot) -> None:
    """Thong bao ly do ngay da bi khoa."""
    deadline = get_meal_day_deadline(day)
    bot.answer_callback_query(
        call.id,
        build_day_closed_message(day, deadline),
        show_alert=True,
    )


def handle_meal_callback(
    call: types.CallbackQuery,
    bot: telebot.TeleBot,
    task_queue: TaskQueue,
) -> None:
    """
    Routing callback_data:
      meal_menu                       -> Hien thi menu chinh
      meal_day_menu:<day>            -> Hien thi sub-menu chon bua
      meal_locked:<day>              -> Bao ngay da qua han
      meal_week_locked               -> Bao khong con ngay nao mo
      meal_day_toggle:<day>:<state>:<meal> -> Toggle checkbox trong ngay
      meal_day_submit:<day>:<state>  -> Xac nhan gui cac bua da chon
      meal_all:<true|false>          -> Dang ky / huy cac ngay mo
      meal_view                      -> Xem bao com
      meal_staff                     -> Xem danh sach da bao
      meal_summary                   -> Tong hop tuan (admin)
    """
    data = call.data
    user = call.from_user
    user_id = user.id
    username = _build_callback_username(call)
    chat_id = call.message.chat.id

    if data == "meal_menu":
        bot.answer_callback_query(call.id)
        _show_main_menu(call, bot)
        return

    if data == "meal_week_locked":
        bot.answer_callback_query(call.id, "⛔ Tuần này không còn ngày nào mở để báo cơm.", show_alert=True)
        return

    if data.startswith("meal_locked:"):
        _answer_locked_day(call, data.split(":")[1], bot)
        return

    if data.startswith("meal_day_menu:"):
        bot.answer_callback_query(call.id)
        day = data.split(":")[1]
        _show_day_menu(call, bot, day)
        return

    if data.startswith("meal_day_toggle:"):
        _, day, state_code, meal = data.split(":")
        if not is_meal_day_open(day):
            _answer_locked_day(call, day, bot)
            return
        bot.answer_callback_query(call.id)
        meal_states = _toggle_meal_state(state_code, meal)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=build_day_menu_text(day, meal_states=meal_states),
            parse_mode="Markdown",
            reply_markup=build_day_menu_keyboard(day, meal_states=meal_states),
        )
        return

    if data.startswith("meal_day_submit:"):
        _, day, state_code = data.split(":")
        if not is_meal_day_open(day):
            _answer_locked_day(call, day, bot)
            return
        meal_states = _deserialize_meal_states(state_code)
        task = Task(
            task_type=TaskType.MEAL_DAY,
            chat_id=chat_id,
            payload={
                "user_id": user_id,
                "username": username,
                "day": day,
                "day_vi": DAYS_VI[day],
                "values": meal_states,
                "message_id": call.message.message_id,
            },
            max_retries=settings.MAX_RETRIES,
        )
        _enqueue_from_callback(
            task,
            task_queue,
            call,
            bot,
            loading_text=f"⏳ Đang xác nhận báo cơm cho *{DAYS_VI[day]}*...",
        )
        return

    if data.startswith("meal_all:"):
        try:
            ensure_week_has_open_days()
        except MealRegistrationError:
            bot.answer_callback_query(call.id, "⛔ Tuần này không còn ngày nào mở để báo cơm.", show_alert=True)
            return
        value = data.split(":")[1] == "true"
        task = Task(
            task_type=TaskType.MEAL_ALL,
            chat_id=chat_id,
            payload={"user_id": user_id, "username": username, "value": value},
            max_retries=settings.MAX_RETRIES,
        )
        _enqueue_from_callback(
            task,
            task_queue,
            call,
            bot,
            loading_text=(
                "⏳ Đang cập nhật các ngày còn mở trong tuần..."
                if value
                else "⏳ Đang hủy các ngày còn mở trong tuần..."
            ),
        )
        return

    if data == "meal_view":
        task = Task(
            task_type=TaskType.MEAL_VIEW,
            chat_id=chat_id,
            payload={"user_id": user_id, "username": username},
            max_retries=settings.MAX_RETRIES,
        )
        _enqueue_from_callback(
            task,
            task_queue,
            call,
            bot,
            loading_text="⏳ Đang tải báo cơm của bạn...",
        )
        return

    if data == "meal_staff":
        task = Task(
            task_type=TaskType.MEAL_STAFF,
            chat_id=chat_id,
            max_retries=settings.MAX_RETRIES,
        )
        _enqueue_from_callback(
            task,
            task_queue,
            call,
            bot,
            loading_text="⏳ Đang tải danh sách đã báo cơm...",
        )
        return

    if data == "meal_summary":
        if not _is_admin_chat(chat_id):
            bot.answer_callback_query(call.id, "⛔ Chỉ admin mới xem được tổng hợp.", show_alert=True)
            return
        task = Task(
            task_type=TaskType.MEAL_SUMMARY,
            chat_id=chat_id,
            max_retries=settings.MAX_RETRIES,
        )
        _enqueue_from_callback(
            task,
            task_queue,
            call,
            bot,
            loading_text="⏳ Đang tổng hợp báo cơm toàn tuần...",
        )
