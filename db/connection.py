"""
db/connection.py - MongoDB connection singleton.

Dung MongoClient dang singleton de tai su dung connection pool
thay vi tao connection moi moi lan goi.

pymongo MongoClient la thread-safe - an toan khi dung chung
giua main thread, telebot handler threads va worker threads.
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
    Tra ve MongoClient singleton (tao 1 lan, tai dung mai).
    lru_cache dam bao chi tao 1 instance du goi bao nhieu lan.
    """
    client = MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        maxPoolSize=20,
        minPoolSize=2,
    )
    logger.info("MongoDB client created -> %s", settings.safe_mongo_uri)
    return client


def get_db() -> Database:
    """Tra ve Database instance theo MONGO_DB_NAME trong config."""
    return get_client()[settings.MONGO_DB_NAME]


def ping() -> bool:
    """Kiem tra ket noi MongoDB. Tra ve True neu OK."""
    try:
        get_client().admin.command("ping")
        logger.info("MongoDB ping: OK")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as error:
        logger.error("MongoDB ping failed: %s", error)
        return False


def close() -> None:
    """Dong connection pool khi shutdown."""
    try:
        get_client().close()
        get_client.cache_clear()
        logger.info("MongoDB connection closed.")
    except Exception:
        pass
