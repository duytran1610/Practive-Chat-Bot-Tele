"""
db/models.py — MongoDB document schemas (dùng plain dict + helper functions).

Collection: meal_reports
Document schema:
{
    "_id"        : ObjectId (auto),
    "user_id"    : int,           # Telegram user_id
    "username"   : str,           # @username hoặc full name
    "week_start" : datetime,      # Thứ 2 đầu tuần (00:00:00 UTC+7)
    "meals": {
        "monday":    {"morning": bool, "afternoon": bool, "evening": bool},
        "tuesday":   {"morning": bool, "afternoon": bool, "evening": bool},
        "wednesday": {"morning": bool, "afternoon": bool, "evening": bool},
        "thursday":  {"morning": bool, "afternoon": bool, "evening": bool},
        "friday":    {"morning": bool, "afternoon": bool, "evening": bool},
        "saturday":  {"morning": bool, "afternoon": bool, "evening": bool},
        "sunday":    {"morning": bool, "afternoon": bool, "evening": bool},
    },
    "created_at" : datetime,
    "updated_at" : datetime,
}
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

# ── Constants ─────────────────────────────────────────────────────────────────

DAYS_VI = {
    "monday"   : "Thứ 2",
    "tuesday"  : "Thứ 3",
    "wednesday": "Thứ 4",
    "thursday" : "Thứ 5",
    "friday"   : "Thứ 6",
    "saturday" : "Thứ 7",
    "sunday"   : "Chủ nhật",
}

MEALS_VI = {
    "morning"  : "Sáng",
    "afternoon": "Trưa",
    "evening"  : "Tối",
}

DAYS_ORDER = list(DAYS_VI.keys())    # ["monday", ..., "sunday"]
MEALS_ORDER = list(MEALS_VI.keys())  # ["morning", "afternoon", "evening"]

TZ_VN = timezone(timedelta(hours=7))  # UTC+7


# ── Helpers ───────────────────────────────────────────────────────────────────

def empty_week_meals() -> dict:
    """Trả về dict meals mặc định — tất cả False (chưa đăng ký)."""
    return {
        day: {meal: False for meal in MEALS_ORDER}
        for day in DAYS_ORDER
    }


def get_week_start(dt: datetime | None = None) -> datetime:
    """
    Trả về datetime của thứ 2 đầu tuần chứa `dt` (giờ VN).
    Dùng làm key để nhóm báo cơm theo tuần.
    """
    if dt is None:
        dt = datetime.now(TZ_VN)
    # weekday(): 0=Monday, 6=Sunday
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def new_meal_report(user_id: int, username: str) -> dict:
    """Tạo document meal_report mới cho tuần hiện tại."""
    now = datetime.now(TZ_VN)
    return {
        "user_id"   : user_id,
        "username"  : username,
        "week_start": get_week_start(now),
        "meals"     : empty_week_meals(),
        "created_at": now,
        "updated_at": now,
    }


def format_meal_summary(doc: dict) -> str:
    """
    Chuyển document MongoDB → chuỗi text hiển thị cho Telegram.

    Ví dụ output:
        📅 Tuần 14/07 – 20/07
        👤 @nguyenvana

        Thứ 2: ☀️ Sáng ✅ | 🌤 Trưa ❌ | 🌙 Tối ✅
        Thứ 3: ☀️ Sáng ❌ | 🌤 Trưa ✅ | 🌙 Tối ❌
        ...
    """
    week_start: datetime = doc["week_start"]
    week_end   = week_start + timedelta(days=6)
    meals: dict = doc["meals"]

    lines = [
        f"📅 *Tuần {week_start.strftime('%d/%m')} – {week_end.strftime('%d/%m/%Y')}*",
        f"👤 {doc['username']}",
        "",
    ]

    meal_icons = {"morning": "☀️", "afternoon": "🌤", "evening": "🌙"}

    for day in DAYS_ORDER:
        day_meals = meals.get(day, {})
        parts = []
        for meal in MEALS_ORDER:
            icon   = meal_icons[meal]
            name   = MEALS_VI[meal]
            status = "✅" if day_meals.get(meal) else "❌"
            parts.append(f"{icon}{name} {status}")
        lines.append(f"*{DAYS_VI[day]}*: {' | '.join(parts)}")

    return "\n".join(lines)