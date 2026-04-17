from datetime import datetime
import unittest

from bot.meal_handlers import (
    build_day_menu_keyboard,
    build_day_menu_text,
    build_main_menu_keyboard,
    build_main_menu_text,
)


def _button_texts(markup) -> list[str]:
    return [button.text for row in markup.keyboard for button in row]


def _callback_data(markup) -> list[str]:
    return [button.callback_data for row in markup.keyboard for button in row]


class MealUiTests(unittest.TestCase):
    def test_build_main_menu_keyboard_for_user(self) -> None:
        now = datetime(2026, 4, 13, 15, 0)
        markup = build_main_menu_keyboard(is_admin=False, now=now)
        callbacks = _callback_data(markup)
        texts = _button_texts(markup)

        self.assertIn("meal_locked:monday", callbacks)
        self.assertIn("meal_day_menu:tuesday", callbacks)
        self.assertIn("meal_all:true", callbacks)
        self.assertIn("meal_view", callbacks)
        self.assertIn("meal_staff", callbacks)
        self.assertNotIn("meal_summary", callbacks)
        self.assertIn("👥 Danh sách đã báo", texts)

    def test_build_main_menu_keyboard_for_admin(self) -> None:
        now = datetime(2026, 4, 13, 15, 0)
        markup = build_main_menu_keyboard(is_admin=True, now=now)

        self.assertIn("meal_summary", _callback_data(markup))
        self.assertIn("📊 Tổng hợp tuần", _button_texts(markup))

    def test_build_day_menu_keyboard_contains_checkbox_and_submit_for_open_day(self) -> None:
        now = datetime(2026, 4, 13, 15, 0)
        markup = build_day_menu_keyboard(
            "tuesday",
            now=now,
            meal_states={"morning": True, "afternoon": False, "evening": True},
        )
        callbacks = _callback_data(markup)
        texts = _button_texts(markup)

        self.assertIn("meal_day_toggle:tuesday:101:morning", callbacks)
        self.assertIn("meal_day_toggle:tuesday:101:afternoon", callbacks)
        self.assertIn("meal_day_toggle:tuesday:101:evening", callbacks)
        self.assertIn("meal_day_submit:tuesday:101", callbacks)
        self.assertIn("meal_menu", callbacks)
        self.assertIn("☑️ Sáng", texts)
        self.assertIn("☐ Trưa", texts)
        self.assertIn("✅ Xác nhận", texts)

    def test_build_day_menu_text_shows_current_states(self) -> None:
        now = datetime(2026, 4, 13, 15, 0)
        text = build_day_menu_text(
            "tuesday",
            now=now,
            meal_states={"morning": True, "afternoon": False, "evening": True},
        )

        self.assertIn("Sáng=True", text)
        self.assertIn("Trưa=False", text)
        self.assertIn("Xác nhận", text)

    def test_build_main_menu_text_mentions_admin_section_only_for_admin(self) -> None:
        now = datetime(2026, 4, 13, 15, 0)
        user_text = build_main_menu_text(is_admin=False, now=now)
        admin_text = build_main_menu_text(is_admin=True, now=now)

        self.assertNotIn("admin", user_text.lower())
        self.assertIn("admin", admin_text.lower())


if __name__ == "__main__":
    unittest.main()
