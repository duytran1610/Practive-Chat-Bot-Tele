"""
db/meal_repository.py - CRUD operations cho collection meal_reports.

Repository pattern: tap trung toan bo MongoDB queries vao day.
Cac module khac chi goi MealRepository, khong tu query truc tiep.

Indexes duoc tao tu dong lan dau chay:
  - {user_id, week_start} unique -> moi user 1 document/tuan
  - {week_start} -> query tong hop theo tuan nhanh hon
"""

from __future__ import annotations

import logging
from datetime import datetime

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from db.connection import get_db
from db.meal_rules import ensure_meal_day_open, ensure_week_has_open_days
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

    Tat ca methods la synchronous, phu hop worker threads cua telebot.
    """

    def __init__(self) -> None:
        self._col: Collection = get_db()[COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Tao indexes neu chua co."""
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

    def get_or_create(self, user_id: int, username: str) -> dict:
        """Lay document bao com tuan hien tai cua user, neu chua co thi tao moi."""
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
                doc = self._col.find_one({"user_id": user_id, "week_start": week_start})

        return doc

    def set_meal(
        self,
        user_id: int,
        username: str,
        day: str,
        meal: str,
        value: bool,
        now: datetime | None = None,
    ) -> dict:
        """Cap nhat 1 bua an cu the."""
        if day not in DAYS_ORDER:
            raise ValueError(f"Invalid day: {day}")
        if meal not in MEALS_ORDER:
            raise ValueError(f"Invalid meal: {meal}")

        current = now or datetime.now(TZ_VN)
        ensure_meal_day_open(day, now=current)
        week_start = get_week_start(current)

        updated = self._col.find_one_and_update(
            {"user_id": user_id, "week_start": week_start},
            {
                "$set": {
                    f"meals.{day}.{meal}": value,
                    "username": username,
                    "updated_at": current,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "week_start": week_start,
                    "created_at": current,
                },
            },
            upsert=True,
            return_document=True,
        )

        logger.info("set_meal user=%d %s/%s=%s", user_id, day, meal, value)
        return updated

    def set_day(
        self,
        user_id: int,
        username: str,
        day: str,
        values: dict[str, bool],
        now: datetime | None = None,
    ) -> dict:
        """Cap nhat tat ca bua trong 1 ngay cung luc."""
        if day not in DAYS_ORDER:
            raise ValueError(f"Invalid day: {day}")

        current = now or datetime.now(TZ_VN)
        ensure_meal_day_open(day, now=current)
        week_start = get_week_start(current)

        set_fields = {f"meals.{day}.{meal}": v for meal, v in values.items()}
        set_fields["username"] = username
        set_fields["updated_at"] = current

        updated = self._col.find_one_and_update(
            {"user_id": user_id, "week_start": week_start},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "user_id": user_id,
                    "week_start": week_start,
                    "created_at": current,
                },
            },
            upsert=True,
            return_document=True,
        )
        logger.info("set_day user=%d %s=%s", user_id, day, values)
        return updated

    def set_all(
        self,
        user_id: int,
        username: str,
        value: bool,
        now: datetime | None = None,
    ) -> dict:
        """Cap nhat tat ca ngay con mo trong tuan = value."""
        current = now or datetime.now(TZ_VN)
        week_start = get_week_start(current)
        open_days = ensure_week_has_open_days(now=current)

        set_fields: dict[str, object] = {"username": username, "updated_at": current}
        for day in open_days:
            for meal in MEALS_ORDER:
                set_fields[f"meals.{day}.{meal}"] = value

        updated = self._col.find_one_and_update(
            {"user_id": user_id, "week_start": week_start},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "user_id": user_id,
                    "week_start": week_start,
                    "created_at": current,
                },
            },
            upsert=True,
            return_document=True,
        )
        logger.info("set_all user=%d value=%s open_days=%s", user_id, value, open_days)
        return updated

    def get_my_report(self, user_id: int, username: str) -> str:
        """Tra ve chuoi text bao com tuan nay cua user."""
        doc = self.get_or_create(user_id, username)
        return format_meal_summary(doc)

    def get_week_summary(self) -> str:
        """Tong hop bao com tuan nay cua tat ca nhan vien."""
        week_start = get_week_start()
        docs = list(self._col.find({"week_start": week_start}))

        if not docs:
            return "📭 Tuần này chưa có ai báo cơm."

        lines = [
            f"📊 *Tổng hợp báo cơm tuần {week_start.strftime('%d/%m/%Y')}*",
            f"👥 Số người đăng ký: {len(docs)}",
            "",
        ]

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
        """Danh sach nhan vien da bao com tuan nay."""
        week_start = get_week_start()
        docs = list(self._col.find(
            {"week_start": week_start},
            {"username": 1, "user_id": 1},
        ))
        if not docs:
            return "📭 Tuần này chưa có ai báo cơm."

        lines = [f"👥 *Danh sách báo cơm tuần này ({len(docs)} người):*", ""]
        for index, doc in enumerate(docs, 1):
            lines.append(f"{index}. {doc['username']}")
        return "\n".join(lines)
