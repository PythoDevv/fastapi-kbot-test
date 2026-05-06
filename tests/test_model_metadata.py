import unittest

import bots.kitobxon.models  # noqa: F401
import bots.Kitobmillatbot.models  # noqa: F401
from core.base_model import Base


class ModelMetadataTests(unittest.TestCase):
    def test_kitobmillatbot_tables_are_registered(self) -> None:
        expected_tables = {
            "kitobmillatbot_users",
            "kitobmillatbot_quiz_settings",
            "kitobmillatbot_test_sessions",
            "kitobmillatbot_test_answers",
            "kitobmillatbot_poll_map",
        }
        self.assertTrue(expected_tables.issubset(Base.metadata.tables))


if __name__ == "__main__":
    unittest.main()
