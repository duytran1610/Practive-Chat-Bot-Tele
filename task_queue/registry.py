"""
task_queue/registry.py — Map TaskType → handler function.

Thêm task mới:
  1. Thêm entry vào TaskType  (task_queue/models.py)
  2. Viết handler             (tasks/handlers.py)
  3. Đăng ký ở đây           (TASK_REGISTRY)
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

if TYPE_CHECKING:
    import telebot
    from task_queue.models import Task

HandlerFn = Callable[["Task", "telebot.TeleBot"], None]

TASK_REGISTRY: dict[TaskType, HandlerFn] = {
    TaskType.ECHO         : handle_echo,
    TaskType.REVERSE_TEXT : handle_reverse_text,
    TaskType.FETCH_JOKE   : handle_fetch_joke,
    TaskType.SLOW_TASK    : handle_slow_task,
}


def get_handler(task_type: TaskType) -> HandlerFn:
    handler = TASK_REGISTRY.get(task_type)
    if handler is None:
        raise KeyError(f"No handler for task_type={task_type!r}")
    return handler