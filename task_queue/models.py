"""
task_queue/models.py — Task data model dùng chung toàn project.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TaskType(str, Enum):
    ECHO         = "echo"
    REVERSE_TEXT = "reverse_text"
    FETCH_JOKE   = "fetch_joke"
    SLOW_TASK    = "slow_task"


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
            f"chat={self.chat_id}, retry={self.retry_count}/{self.max_retries}, "
            f"status={self.status.value})"
        )