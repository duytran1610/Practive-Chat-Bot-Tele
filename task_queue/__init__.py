"""
task_queue/__init__.py
======================
Public API của package task_queue.

Từ bên ngoài chỉ cần:
    from task_queue import Task, TaskType, TaskQueue, WorkerPool, get_handler
"""

from task_queue.models import Task, TaskStatus, TaskType
from task_queue.producer import TaskQueue
from task_queue.registry import TASK_REGISTRY, HandlerFn, get_handler
from task_queue.worker import WorkerPool

__all__ = [
    "Task",
    "TaskType",
    "TaskStatus",
    "TaskQueue",
    "WorkerPool",
    "get_handler",
    "TASK_REGISTRY",
    "HandlerFn",
]