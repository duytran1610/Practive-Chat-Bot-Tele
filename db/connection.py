"""
db/connection.py — MongoDB connection singleton.

Dùng MongoClient dạng singleton để tái sử dụng connection pool
thay vì tạo connection mới mỗi lần gọi.

pymongo MongoClient là thread-safe — an toàn khi dùng chung
giữa main thread, telebot handler threads và worker threads.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """
    Trả về MongoClient singleton (tạo 1 lần, tái dùng mãi).
    lru_cache đảm bảo chỉ tạo 1 instance dù gọi bao nhiêu lần.
    """
    client = MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,   # timeout khi không kết nối được
        connectTimeoutMS=5000,
        maxPoolSize=20,                  # tối đa 20 connections trong pool
        minPoolSize=2,                   # giữ ít nhất 2 connections sẵn sàng
    )
    logger.info("MongoDB client created → %s", settings.MONGO_URI)
    return client


def get_db() -> Database:
    """Trả về Database instance theo MONGO_DB_NAME trong config."""
    return get_client()[settings.MONGO_DB_NAME]


def ping() -> bool:
    """Kiểm tra kết nối MongoDB. Trả về True nếu OK."""
    try:
        get_client().admin.command("ping")
        logger.info("MongoDB ping: OK")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error("MongoDB ping failed: %s", e)
        return False


def close() -> None:
    """Đóng connection pool khi shutdown."""
    try:
        get_client().close()
        get_client.cache_clear()
        logger.info("MongoDB connection closed.")
    except Exception:
        pass