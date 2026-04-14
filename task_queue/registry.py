"""
task_queue/registry.py — Map TaskType → handler function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from task_queue.models import TaskType
from tasks.handlers import (
    handle_echo,
    handle_fetch_joke,
    handle_reverse_text,
    handle_slow_task,
)
from tasks.meal_handlers import (
    handle_meal_all,
    handle_meal_day,
    handle_meal_register,
    handle_meal_staff,
    handle_meal_summary,
    handle_meal_view,
)

if TYPE_CHECKING:
    import telebot
    from task_queue.models import Task

HandlerFn = Callable[["Task", "telebot.TeleBot"], None]

TASK_REGISTRY: dict[TaskType, HandlerFn] = {
    # ── Cũ ───────────────────────────────────────────────────
    TaskType.ECHO         : handle_echo,
    TaskType.REVERSE_TEXT : handle_reverse_text,
    TaskType.FETCH_JOKE   : handle_fetch_joke,
    TaskType.SLOW_TASK    : handle_slow_task,
    # ── Báo cơm ──────────────────────────────────────────────
    TaskType.MEAL_REGISTER: handle_meal_register,
    TaskType.MEAL_DAY     : handle_meal_day,
    TaskType.MEAL_ALL     : handle_meal_all,
    TaskType.MEAL_VIEW    : handle_meal_view,
    TaskType.MEAL_SUMMARY : handle_meal_summary,
    TaskType.MEAL_STAFF   : handle_meal_staff,
}


def get_handler(task_type: TaskType) -> HandlerFn:
    handler = TASK_REGISTRY.get(task_type)
    if handler is None:
        raise KeyError(f"No handler for task_type={task_type!r}")
    return handler