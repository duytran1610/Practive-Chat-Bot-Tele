import unittest

from config import redact_mongo_uri


class ConfigTests(unittest.TestCase):
    def test_redact_mongo_uri_hides_password(self) -> None:
        uri = "mongodb+srv://user-for-bot:user-for-bot1@clusterbot.swiyvqw.mongodb.net/"

        safe_uri = redact_mongo_uri(uri)

        self.assertEqual(
            safe_uri,
            "mongodb+srv://user-for-bot:***@clusterbot.swiyvqw.mongodb.net/",
        )
        self.assertNotIn("user-for-bot1", safe_uri)


if __name__ == "__main__":
    unittest.main()
