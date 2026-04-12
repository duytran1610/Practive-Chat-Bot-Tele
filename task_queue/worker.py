"""
task_queue/worker.py — Worker pool: N threads tiêu thụ task từ TaskQueue.

Mỗi worker thread:
  1. Dequeue Task (block với timeout 1s để check stop-flag)
  2. Gọi handler tương ứng
  3. Lỗi → retry exponential backoff
  4. Hết retry → mark DEAD, notify admin + user
  5. Luôn gọi task_done() để queue.join() hoạt động đúng
"""

from __future__ import annotations

import logging
import threading
import time

import telebot

from config import settings
from task_queue.models import Task, TaskStatus
from task_queue.producer import TaskQueue
from task_queue.registry import get_handler

logger = logging.getLogger(__name__)


def _worker_loop(
    worker_id: int,
    task_queue: TaskQueue,
    bot: telebot.TeleBot,
    stop_event: threading.Event,
) -> None:
    logger.info("Worker-%d started [thread=%s]", worker_id, threading.current_thread().name)

    while not stop_event.is_set():
        task: Task | None = task_queue.dequeue(timeout=1.0)
        if task is None:
            continue  # timeout — kiểm tra stop_event rồi lặp lại

        task.status = TaskStatus.PROCESSING
        logger.info("PROCESSING | Worker-%d | %s", worker_id, task)

        start = time.monotonic()
        try:
            handler = get_handler(task.task_type)
            handler(task, bot)
            task.status = TaskStatus.SUCCESS
            logger.info("SUCCESS    | Worker-%d | %s | %.2fs",
                        worker_id, task, time.monotonic() - start)
        except Exception as exc:
            logger.error("FAILED     | Worker-%d | %s | %.2fs | %s: %s",
                         worker_id, task, time.monotonic() - start,
                         type(exc).__name__, exc, exc_info=True)
            _handle_retry(task, task_queue, bot, exc)
        finally:
            task_queue.task_done()

    logger.info("Worker-%d stopped.", worker_id)


def _handle_retry(
    task: Task,
    task_queue: TaskQueue,
    bot: telebot.TeleBot,
    exc: Exception,
) -> None:
    """Exponential backoff: delay = base * 2^(retry_count-1)"""
    if task.can_retry:
        task.retry_count += 1
        delay = settings.RETRY_BASE_DELAY * (2 ** (task.retry_count - 1))
        logger.warning("RETRY      | %s | attempt %d/%d | backoff=%.1fs",
                       task, task.retry_count, task.max_retries, delay)
        time.sleep(delay)
        if not task_queue.enqueue(task):
            _mark_dead(task, bot, exc, reason="queue full during retry")
    else:
        _mark_dead(task, bot, exc)


def _mark_dead(
    task: Task,
    bot: telebot.TeleBot,
    exc: Exception,
    reason: str = "max retries exceeded",
) -> None:
    task.status = TaskStatus.DEAD
    logger.error("DEAD       | %s | reason=%s | %s: %s",
                 task, reason, type(exc).__name__, exc)

    if settings.ADMIN_CHAT_ID:
        try:
            bot.send_message(
                settings.ADMIN_CHAT_ID,
                f"💀 *Dead Task*\nID: `{task.task_id}`\n"
                f"Type: `{task.task_type.value}`\n"
                f"Reason: {reason}\nError: `{type(exc).__name__}: {exc}`",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    try:
        bot.send_message(
            task.chat_id,
            f"❌ Yêu cầu không thể xử lý sau {task.max_retries} lần thử. "
            "Vui lòng thử lại sau.",
        )
    except Exception:
        pass


class WorkerPool:
    """
    Quản lý N worker threads với graceful shutdown.

    Usage:
        pool = WorkerPool(task_queue, bot, num_workers=3)
        pool.start()
        ...
        pool.stop(drain_timeout=30.0)
    """

    def __init__(self, task_queue: TaskQueue, bot: telebot.TeleBot, num_workers: int) -> None:
        self._task_queue  = task_queue
        self._bot         = bot
        self._num_workers = num_workers
        self._stop_event  = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for i in range(self._num_workers):
            t = threading.Thread(
                target=_worker_loop,
                args=(i, self._task_queue, self._bot, self._stop_event),
                name=f"Worker-{i}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)
        logger.info("WorkerPool started — %d workers.", self._num_workers)

    def stop(self, drain_timeout: float = 30.0) -> None:
        logger.info("WorkerPool stopping (drain_timeout=%.0fs)…", drain_timeout)
        self._stop_event.set()

        drain = threading.Thread(target=self._task_queue.join, daemon=True)
        drain.start()
        drain.join(timeout=drain_timeout)
        if drain.is_alive():
            logger.warning("Queue drain timed out.")

        for t in self._threads:
            t.join(timeout=5.0)
        logger.info("WorkerPool stopped.")