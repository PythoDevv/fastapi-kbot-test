import asyncio
import csv
import importlib
import tempfile
import unittest
from pathlib import Path


USER_EXCEL_MODULES = (
    "bots.Kitobxonmillattbot.utils.excel",
    "bots.Kitobmillatbot.utils.excel",
    "bots.Millatchiroqlaribot.utils.excel",
    "bots.Barakali_tanlov_bot.utils.excel",
    "bots.Manfaadli_konkurs_bot.utils.excel",
    "bots.kitobxon.utils.excel",
)


class UserImportTests(unittest.TestCase):
    def test_csv_field_larger_than_python_default_limit_is_imported(self):
        long_name = "A" * 131_073

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "users.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "ID",
                        "FIO",
                        "Username",
                        "Telefon",
                        "Referallar",
                        "Ball",
                        "Javoblar",
                        "Kim taklif qildi (ID)",
                        "Telegram ID raqami",
                        "Qo'shilgan vaqti",
                    ]
                )
                writer.writerow(
                    [
                        "1",
                        long_name,
                        "@test",
                        "",
                        "0",
                        "0",
                        "0",
                        "",
                        "123456789",
                        "",
                    ]
                )

            for module_name in USER_EXCEL_MODULES:
                with self.subTest(module=module_name):
                    module = importlib.import_module(module_name)
                    users, errors = module.import_users_from_excel(str(path))

                    self.assertEqual(errors, [])
                    self.assertEqual(len(users), 1)
                    self.assertEqual(users[0]["telegram_id"], 123456789)
                    self.assertEqual(users[0]["fio"], long_name)

    def test_large_import_flushes_database_rows_in_batches(self):
        module = importlib.import_module(
            "bots.Kitobxonmillattbot.services.admin_service"
        )

        class FakeSession:
            def __init__(self):
                self.added_batch_sizes = []
                self.flush_count = 0
                self.commit_count = 0

            def add_all(self, users):
                self.added_batch_sizes.append(len(users))

            async def flush(self):
                self.flush_count += 1

            async def commit(self):
                self.commit_count += 1

        class FakeUsers:
            async def get_by_telegram_ids(self, telegram_ids):
                return {}

        session = FakeSession()
        service = module.AdminService(session)
        service.users = FakeUsers()
        users_data = [
            {
                "telegram_id": index,
                "fio": f"User {index}",
                "username": None,
                "mobile_number": None,
                "referrals_count": 0,
                "score": 0,
                "referred_by": None,
            }
            for index in range(1, 2_002)
        ]

        result = asyncio.run(service.import_users(users_data))

        self.assertEqual(result, (0, 2_001, 0))
        self.assertEqual(session.commit_count, 1)
        self.assertEqual(session.flush_count, 3)
        self.assertEqual(session.added_batch_sizes, [1_000, 1_000, 1])


if __name__ == "__main__":
    unittest.main()
