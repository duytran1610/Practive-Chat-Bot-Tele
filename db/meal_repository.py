"""
db/meal_repository.py — CRUD operations cho collection meal_reports.

Repository pattern: tập trung toàn bộ MongoDB queries vào đây.
Các module khác chỉ gọi MealRepository, không tự query trực tiếp.

Indexes được tạo tự động lần đầu chạy:
  - {user_id, week_start} unique → mỗi user 1 document/tuần
  - {week_start}          → query tổng hợp theo tuần nhanh hơn
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from db.connection import get_db
from db.models import (
    DAYS_ORDER,
    MEALS_ORDER,
    TZ_VN,
    format_meal_summary,
    get_week_start,
    new_meal_report,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "meal_reports"


class MealRepository:
    """
    CRUD cho collection meal_reports.

    Tất cả methods là synchronous (phù hợp worker threads của telebot).
    """

    def __init__(self) -> None:
        self._col: Collection = get_db()[COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Tạo indexes nếu chưa có — idempotent, an toàn khi gọi nhiều lần."""
        self._col.create_index(
            [("user_id", 1), ("week_start", 1)],
            unique=True,
            name="user_week_unique",
        )
        self._col.create_index(
            [("week_start", 1)],
            name="week_start_idx",
        )
        logger.debug("MongoDB indexes ensured for [%s]", COLLECTION_NAME)

    # ── Get or create ─────────────────────────────────────────────────────────

    def get_or_create(self, user_id: int, username: str) -> dict:
        """
        Lấy document báo cơm tuần hiện tại của user.
        Nếu chưa có → tạo mới.
        """
        week_start = get_week_start()
        doc = self._col.find_one({"user_id": user_id, "week_start": week_start})

        if doc is None:
            new_doc = new_meal_report(user_id, username)
            try:
                result = self._col.insert_one(new_doc)
                new_doc["_id"] = result.inserted_id
                logger.info("Created meal_report for user=%d week=%s", user_id, week_start.date())
                doc = new_doc
            except DuplicateKeyError:
                # Race condition: thread khác vừa tạo → lấy lại
                doc = self._col.find_one({"user_id": user_id, "week_start": week_start})

        return doc

    # ── Update meal ───────────────────────────────────────────────────────────

    def set_meal(
        self,
        user_id : int,
        username: str,
        day     : str,
        meal    : str,
        value   : bool,
    ) -> dict:
        """
        Cập nhật 1 bữa ăn cụ thể.

        Args:
            user_id : Telegram user_id.
            username: Tên hiển thị.
            day     : "monday" | "tuesday" | ... | "sunday"
            meal    : "morning" | "afternoon" | "evening"
            value   : True = có ăn, False = không ăn.

        Returns:
            Document sau khi cập nhật.
        """
        if day not in DAYS_ORDER:
            raise ValueError(f"Invalid day: {day}")
        if meal not in MEALS_ORDER:
            raise ValueError(f"Invalid meal: {meal}")

        week_start = get_week_start()
        now = datetime.now(TZ_VN)

        updated = self._col.find_one_and_update(
            {"user_id": user_id, "week_start": week_start},
            {
                "$set": {
                    f"meals.{day}.{meal}": value,
                    "username"           : username,   # cập nhật tên mới nhất
                    "updated_at"         : now,
                },
                "$setOnInsert": {
                    "user_id"   : user_id,
                    "week_start": week_start,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=True,  # trả về document SAU khi update
        )

        logger.info("set_meal user=%d %s/%s=%s", user_id, day, meal, value)
        return updated

    def set_day(
        self,
        user_id : int,
        username: str,
        day     : str,
        values  : dict[str, bool],
    ) -> dict:
        """
        Cập nhật tất cả bữa trong 1 ngày cùng lúc.

        Args:
            values: {"morning": True, "afternoon": False, "evening": True}
        """
        if day not in DAYS_ORDER:
            raise ValueError(f"Invalid day: {day}")

        week_start = get_week_start()
        now = datetime.now(TZ_VN)

        set_fields = {f"meals.{day}.{meal}": v for meal, v in values.items()}
        set_fields["username"]   = username
        set_fields["updated_at"] = now

        updated = self._col.find_one_and_update(
            {"user_id": user_id, "week_start": week_start},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "user_id"   : user_id,
                    "week_start": week_start,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=True,
        )
        logger.info("set_day user=%d %s=%s", user_id, day, values)
        return updated

    def set_all(
        self,
        user_id : int,
        username: str,
        value   : bool,
    ) -> dict:
        """Đặt tất cả bữa trong tuần = value (đăng ký hoặc huỷ hết)."""
        week_start = get_week_start()
        now = datetime.now(TZ_VN)

        set_fields: dict = {"username": username, "updated_at": now}
        for day in DAYS_ORDER:
            for meal in MEALS_ORDER:
                set_fields[f"meals.{day}.{meal}"] = value

        updated = self._col.find_one_and_update(
            {"user_id": user_id, "week_start": week_start},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "user_id"   : user_id,
                    "week_start": week_start,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=True,
        )
        logger.info("set_all user=%d value=%s", user_id, value)
        return updated

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_my_report(self, user_id: int, username: str) -> str:
        """Trả về chuỗi text báo cơm tuần này của user."""
        doc = self.get_or_create(user_id, username)
        return format_meal_summary(doc)

    def get_week_summary(self) -> str:
        """
        Tổng hợp báo cơm tuần này của TẤT CẢ nhân viên.
        Dùng cho admin xem tổng.
        """
        week_start = get_week_start()
        docs = list(self._col.find({"week_start": week_start}))

        if not docs:
            return "📭 Tuần này chưa có ai báo cơm."

        lines = [
            f"📊 *Tổng hợp báo cơm tuần {week_start.strftime('%d/%m/%Y')}*",
            f"👥 Số người đăng ký: {len(docs)}",
            "",
        ]

        # Đếm tổng số suất theo từng bữa
        totals: dict[str, dict[str, int]] = {
            day: {meal: 0 for meal in MEALS_ORDER}
            for day in DAYS_ORDER
        }
        for doc in docs:
            for day in DAYS_ORDER:
                for meal in MEALS_ORDER:
                    if doc["meals"].get(day, {}).get(meal):
                        totals[day][meal] += 1

        meal_icons = {"morning": "☀️", "afternoon": "🌤", "evening": "🌙"}
        from db.models import DAYS_VI, MEALS_VI

        for day in DAYS_ORDER:
            parts = []
            for meal in MEALS_ORDER:
                count = totals[day][meal]
                parts.append(f"{meal_icons[meal]}{MEALS_VI[meal]}: *{count}* suất")
            lines.append(f"*{DAYS_VI[day]}*: {' | '.join(parts)}")

        return "\n".join(lines)

    def get_staff_list(self) -> str:
        """Danh sách nhân viên đã báo cơm tuần này."""
        week_start = get_week_start()
        docs = list(self._col.find(
            {"week_start": week_start},
            {"username": 1, "user_id": 1},
        ))
        if not docs:
            return "📭 Tuần này chưa có ai báo cơm."

        lines = [f"👥 *Danh sách báo cơm tuần này ({len(docs)} người):*", ""]
        for i, doc in enumerate(docs, 1):
            lines.append(f"{i}. {doc['username']}")
        return "\n".join(lines)