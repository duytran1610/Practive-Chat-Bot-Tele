from datetime import datetime
import unittest
from unittest.mock import patch

from bot.meal_handlers import build_main_menu_keyboard
from db.meal_rules import MealRegistrationClosedError, get_open_days, is_meal_day_open
from task_queue.models import Task, TaskType
from tasks import meal_handlers as task_meal_handlers


def _callback_data(markup) -> list[str]:
    return [button.callback_data for row in markup.keyboard for button in row]


class MealRuleTests(unittest.TestCase):
    def test_day_is_open_before_cutoff_previous_day(self) -> None:
        now = datetime(2026, 4, 13, 15, 59)

        self.assertTrue(is_meal_day_open("tuesday", now=now))

    def test_day_is_closed_at_cutoff_previous_day(self) -> None:
        now = datetime(2026, 4, 13, 16, 0)

        self.assertFalse(is_meal_day_open("tuesday", now=now))

    def test_open_days_only_include_remaining_days_before_their_deadline(self) -> None:
        now = datetime(2026, 4, 18, 15, 0)

        self.assertEqual(get_open_days(now=now), ["sunday"])

    def test_main_menu_marks_locked_days(self) -> None:
        now = datetime(2026, 4, 13, 16, 30)
        callbacks = _callback_data(build_main_menu_keyboard(is_admin=False, now=now))

        self.assertIn("meal_locked:monday", callbacks)
        self.assertIn("meal_locked:tuesday", callbacks)
        self.assertIn("meal_day_menu:wednesday", callbacks)


class MealTaskHandlerTests(unittest.TestCase):
    def test_handle_meal_register_sends_business_error_without_raising(self) -> None:
        class FakeRepo:
            def set_meal(self, **_kwargs):
                raise MealRegistrationClosedError("tuesday", datetime(2026, 4, 13, 16, 0))

        class FakeBot:
            def __init__(self) -> None:
                self.messages: list[str] = []

            def send_message(self, _chat_id: int, text: str, parse_mode: str | None = None) -> None:
                del parse_mode
                self.messages.append(text)

        task = Task(
            task_type=TaskType.MEAL_REGISTER,
            chat_id=123,
            payload={
                "user_id": 1,
                "username": "@demo",
                "day": "tuesday",
                "meal": "morning",
                "value": True,
                "day_vi": "Thứ 3",
                "meal_vi": "Sáng",
            },
        )
        bot = FakeBot()

        with patch.object(task_meal_handlers, "_repo", return_value=FakeRepo()):
            task_meal_handlers.handle_meal_register(task, bot)

        self.assertEqual(len(bot.messages), 1)
        self.assertIn("Quá hạn báo cơm", bot.messages[0])


if __name__ == "__main__":
    unittest.main()
