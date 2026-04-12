"""
task_queue/producer.py — Thread-safe queue wrapper (stdlib queue.Queue).

pyTelegramBotAPI chạy handlers trong thread pool, nên dùng
threading-safe stdlib queue thay vì asyncio.Queue.
"""

from __future__ import annotations

import logging
import queue as _stdlib_queue

from task_queue.models import Task

logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Thread-safe wrapper quanh stdlib queue.Queue.

    API:
        enqueue(task)  -> bool        Đưa task vào queue; False nếu full.
        dequeue(timeout) -> Task|None Block tối đa `timeout` giây.
        task_done()                   Báo hoàn thành (cho join()).
        join()                        Block cho đến khi queue rỗng hoàn toàn.
        stats (property) -> dict      Số liệu runtime.
    """

    def __init__(self, maxsize: int = 500) -> None:
        self._q: _stdlib_queue.Queue[Task] = _stdlib_queue.Queue(maxsize=maxsize)
        self._enqueued_total = 0
        self._dropped_total  = 0

    def enqueue(self, task: Task) -> bool:
        try:
            self._q.put_nowait(task)
            self._enqueued_total += 1
            logger.info("ENQUEUED  | %s | qsize=%d", task, self._q.qsize())
            return True
        except _stdlib_queue.Full:
            self._dropped_total += 1
            logger.warning("DROPPED   | %s | queue full (max=%d)", task, self._q.maxsize)
            return False

    def dequeue(self, timeout: float = 1.0) -> "Task | None":
        try:
            return self._q.get(timeout=timeout)
        except _stdlib_queue.Empty:
            return None

    def task_done(self) -> None:
        self._q.task_done()

    def join(self) -> None:
        self._q.join()

    @property
    def size(self) -> int:
        return self._q.qsize()

    @property
    def is_full(self) -> bool:
        return self._q.full()

    @property
    def stats(self) -> dict:
        return {
            "current_size"   : self.size,
            "max_size"       : self._q.maxsize,
            "enqueued_total" : self._enqueued_total,
            "dropped_total"  : self._dropped_total,
        }