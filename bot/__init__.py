"""
bot/__init__.py
===============
Public API của package bot.

Bên ngoài chỉ cần:
    from bot import build_bot

handlers.py là implementation detail — không expose trực tiếp.
"""

from bot.dispatcher import build_bot

__all__ = ["build_bot"]