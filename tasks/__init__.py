"""
tasks/__init__.py
=================
Public API của package tasks.

Expose tất cả handler functions để registry.py import gọn:
    from tasks import handle_echo, handle_fetch_joke, ...

Khi thêm module mới (vd: ml_handlers.py), chỉ cần thêm import
ở đây — registry.py không cần thay đổi.
"""

from tasks.handlers import (
    handle_echo,
    handle_fetch_joke,
    handle_reverse_text,
    handle_slow_task,
)

__all__ = [
    "handle_echo",
    "handle_reverse_text",
    "handle_fetch_joke",
    "handle_slow_task",
]