"""
tasks/__init__.py
=================
Public API cua package tasks.

Expose cac handler function de registry.py import gon.
"""

from tasks.handlers import handle_slow_task

__all__ = [
    "handle_slow_task",
]
