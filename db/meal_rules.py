"""
db/meal_rules.py - Quy tac nghiep vu cho thoi gian bao com.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from config import settings
from db.models import DAYS_ORDER, DAYS_VI, TZ_VN, get_week_start


class MealRegistrationError(ValueError):
    """Loi nghiep vu chung cua luong bao com."""


class MealRegistrationClosedError(MealRegistrationError):
    """Bao com da qua han cho ngay duoc chon."""

    def __init__(self, day: str, deadline: datetime) -> None:
        self.day = day
        self.deadline = deadline
        super().__init__(build_day_closed_message(day, deadline))


class NoMealDaysAvailableError(MealRegistrationError):
    """Khong con ngay nao trong tuan con mo de bao com."""

    def __init__(self) -> None:
        super().__init__("Không còn ngày nào trong tuần này còn mở để báo cơm.")


def normalize_now(now: datetime | None = None) -> datetime:
    """Chuan hoa moc thoi gian ve gio VN."""
    if now is None:
        return datetime.now(TZ_VN)
    if now.tzinfo is None:
        return now.replace(tzinfo=TZ_VN)
    return now.astimezone(TZ_VN)


def get_meal_day_datetime(day: str, now: datetime | None = None) -> datetime:
    """Tra ve datetime 00:00 cua ngay bao com trong tuan hien tai."""
    if day not in DAYS_ORDER:
        raise ValueError(f"Invalid day: {day}")

    current = normalize_now(now)
    week_start = get_week_start(current)
    return week_start + timedelta(days=DAYS_ORDER.index(day))


def get_meal_day_deadline(day: str, now: datetime | None = None) -> datetime:
    """Tra ve han cuoi bao com cho ngay da chon."""
    meal_day = get_meal_day_datetime(day, now=now)
    return (meal_day - timedelta(days=1)).replace(
        hour=settings.MEAL_REGISTRATION_CUTOFF_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )


def is_meal_day_open(day: str, now: datetime | None = None) -> bool:
    """Kiem tra ngay bao com co con mo hay khong."""
    current = normalize_now(now)
    deadline = get_meal_day_deadline(day, now=current)
    return current < deadline


def get_open_days(now: datetime | None = None) -> list[str]:
    """Tra ve danh sach cac ngay con mo trong tuan hien tai."""
    current = normalize_now(now)
    return [day for day in DAYS_ORDER if is_meal_day_open(day, now=current)]


def ensure_meal_day_open(day: str, now: datetime | None = None) -> None:
    """Raise loi nghiep vu neu ngay da qua han bao com."""
    current = normalize_now(now)
    if not is_meal_day_open(day, now=current):
        raise MealRegistrationClosedError(day, get_meal_day_deadline(day, now=current))


def ensure_week_has_open_days(now: datetime | None = None) -> list[str]:
    """Tra ve cac ngay con mo, neu khong co thi raise loi nghiep vu."""
    open_days = get_open_days(now=now)
    if not open_days:
        raise NoMealDaysAvailableError()
    return open_days


def format_days_vi(days: list[str]) -> str:
    """Chuyen danh sach key ngay sang nhan tieng Viet."""
    return ", ".join(DAYS_VI[day] for day in days)


def build_day_closed_message(day: str, deadline: datetime) -> str:
    """Tao thong diep qua han cho mot ngay bao com."""
    return (
        f"Quá hạn báo cơm cho *{DAYS_VI[day]}*.\n"
        f"Hạn chót là trước *{deadline.strftime('%H:%M %d/%m/%Y')}*."
    )
