import unittest

from sqlalchemy.orm import configure_mappers

import bots.kitobxon.models  # noqa: F401
import bots.Kitobmillatbot.models  # noqa: F401


class SqlalchemyModelRegistryTests(unittest.TestCase):
    def test_mappers_configure_with_both_bot_model_modules_loaded(self) -> None:
        configure_mappers()


if __name__ == "__main__":
    unittest.main()
