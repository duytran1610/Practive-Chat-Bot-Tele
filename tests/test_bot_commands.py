import unittest

from bot.dispatcher import build_bot_commands


class BotCommandTests(unittest.TestCase):
    def test_build_bot_commands_contains_start_and_meal_commands(self) -> None:
        commands = build_bot_commands()
        names = [command.command for command in commands]

        self.assertIn("start", names)
        self.assertIn("baocom", names)
        self.assertIn("xemcua", names)
        self.assertIn("dangky", names)
        self.assertIn("huydangky", names)
        self.assertIn("danhsach", names)
        self.assertIn("status", names)
        self.assertNotIn("echo", names)
        self.assertNotIn("reverse", names)
        self.assertNotIn("joke", names)

    def test_build_bot_commands_has_descriptions(self) -> None:
        commands = build_bot_commands()

        self.assertTrue(all(command.description for command in commands))


if __name__ == "__main__":
    unittest.main()
