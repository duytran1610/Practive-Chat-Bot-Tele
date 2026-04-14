"""
task_queue/models.py — Task data model dùng chung toàn project.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TaskType(str, Enum):
    # ── Cũ ───────────────────────────────────────────────────
    ECHO         = "echo"
    REVERSE_TEXT = "reverse_text"
    FETCH_JOKE   = "fetch_joke"
    SLOW_TASK    = "slow_task"
    # ── Báo cơm ──────────────────────────────────────────────
    MEAL_REGISTER = "meal_register"   # Đăng ký 1 bữa cụ thể
    MEAL_DAY      = "meal_day"        # Đăng ký cả ngày
    MEAL_ALL      = "meal_all"        # Đăng ký / huỷ cả tuần
    MEAL_VIEW     = "meal_view"       # Xem báo cơm của mình
    MEAL_SUMMARY  = "meal_summary"    # Tổng hợp cả tuần (admin)
    MEAL_STAFF    = "meal_staff"      # Danh sách nhân viên đã báo


class TaskStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    SUCCESS    = "success"
    FAILED     = "failed"
    DEAD       = "dead"


@dataclass
class Task:
    task_type  : TaskType
    chat_id    : int
    payload    : dict       = field(default_factory=dict)
    max_retries: int        = 3
    task_id    : str        = field(default_factory=lambda: str(uuid.uuid4()))
    retry_count: int        = 0
    created_at : datetime   = field(default_factory=lambda: datetime.now(timezone.utc))
    status     : TaskStatus = TaskStatus.PENDING

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def short_id(self) -> str:
        return self.task_id[:8]

    def __repr__(self) -> str:
        return (
            f"Task(id={self.short_id()}, type={self.task_type.value}, "
            f"chat={self.chat_id}, retry={self.retry_count}/{self.max_retries})"
        )