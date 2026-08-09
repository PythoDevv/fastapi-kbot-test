"""Every bot must be wired to the persistent broadcast engine the same way.

The five bots shipped byte-identical copies of the old broadcast code, so a
defect in one was a defect in all. These checks keep the replacement uniform —
and keep the two rules that caused the missed-delivery reports from creeping
back: no ``is_registered`` filter, and no send loop inside a handler.
"""
import importlib
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from core.base_model import Base

ROOT = Path(__file__).resolve().parents[1]

# package directory -> table prefix
BOTS = {
    "kitobxon": "kitobxon",
    "Kitobmillatbot": "kitobmillatbot",
    "Millatchiroqlaribot": "millatchiroqlaribot",
    "Barakali_tanlov_bot": "barakali_tanlov_bot",
    "Manfaadli_konkurs_bot": "manfaadli_konkurs_bot",
}

POLLING_ENTRYPOINTS = (
    "main_polling.py",
    "main_polling_kitobxon.py",
    "main_polling_kitobmillatbot.py",
    "main_polling_millatchiroqlaribot.py",
    "main_polling_barakali_tanlov_bot.py",
    "main_polling_manfaadli_konkurs_bot.py",
    "main_polling_selected.py",
)


def _models(pkg: str):
    return importlib.import_module(f"bots.{pkg}.models")


def _engine(pkg: str):
    return importlib.import_module(f"bots.{pkg}.services.broadcast_service").engine


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


class SchemaTests(unittest.TestCase):
    def test_every_bot_has_the_broadcast_tables(self) -> None:
        for pkg, prefix in BOTS.items():
            _models(pkg)
            for suffix in ("broadcast_jobs", "broadcast_failures"):
                with self.subTest(bot=pkg, table=suffix):
                    self.assertIn(f"{prefix}_{suffix}", Base.metadata.tables)

    def test_job_table_carries_the_resume_state(self) -> None:
        for pkg, prefix in BOTS.items():
            _models(pkg)
            columns = Base.metadata.tables[f"{prefix}_broadcast_jobs"].columns
            for name in ("status", "cursor_id", "sent", "failed", "total",
                         "blocked", "retry_of_job_id"):
                with self.subTest(bot=pkg, column=name):
                    self.assertIn(name, columns)

    def test_job_table_carries_the_cross_process_lease(self) -> None:
        """Without it, webhook + polling on one database double-send."""
        for pkg, prefix in BOTS.items():
            _models(pkg)
            columns = Base.metadata.tables[f"{prefix}_broadcast_jobs"].columns
            for name in ("locked_by", "locked_at"):
                with self.subTest(bot=pkg, column=name):
                    self.assertIn(name, columns)

    def test_every_bot_can_flag_a_user_who_blocked_the_bot(self) -> None:
        for pkg, prefix in BOTS.items():
            _models(pkg)
            with self.subTest(bot=pkg):
                self.assertIn(
                    "is_blocked", Base.metadata.tables[f"{prefix}_users"].columns
                )


class TargetSelectionTests(unittest.TestCase):
    """The recipient query is the fix for "ko'pchilikka bormadi"."""

    def test_a_normal_broadcast_filters_nobody_out(self) -> None:
        """Not by registration, and not by a past block either — both would
        silently shrink the audience, which is the bug being fixed."""
        job = SimpleNamespace(retry_of_job_id=None)
        for pkg in BOTS:
            sql = _sql(_engine(pkg).targets_stmt(job, 0))
            with self.subTest(bot=pkg):
                self.assertNotIn("is_registered", sql)
                self.assertNotIn("is_blocked", sql)

    def test_recipients_are_ordered_by_primary_key_for_an_exact_cursor(self) -> None:
        job = SimpleNamespace(retry_of_job_id=None)
        for pkg, prefix in BOTS.items():
            sql = _sql(_engine(pkg).targets_stmt(job, 0))
            with self.subTest(bot=pkg):
                self.assertIn(f"ORDER BY {prefix}_users.id", sql)

    def test_the_reported_total_counts_every_user(self) -> None:
        job = SimpleNamespace(retry_of_job_id=None)
        for pkg in BOTS:
            sql = _sql(_engine(pkg).count_targets_stmt(job))
            with self.subTest(bot=pkg):
                self.assertNotIn("is_registered", sql)
                self.assertNotIn("is_blocked", sql)
                self.assertNotIn("WHERE", sql)

    def test_a_retry_job_targets_only_the_earlier_failures(self) -> None:
        job = SimpleNamespace(retry_of_job_id=7)
        for pkg, prefix in BOTS.items():
            sql = _sql(_engine(pkg).targets_stmt(job, 0))
            with self.subTest(bot=pkg):
                self.assertIn(f"{prefix}_broadcast_failures", sql)
                self.assertNotIn(f"FROM {prefix}_users", sql)


class HandlerTests(unittest.TestCase):
    def test_no_bot_sends_inside_the_request_handler(self) -> None:
        """The loop belongs to the background worker; a handler that blocks on
        it holds its DB session open for the whole run and dies on restart."""
        for pkg in BOTS:
            for relpath in (
                f"bots/{pkg}/handlers/broadcast.py",
                f"bots/{pkg}/services/broadcast_service.py",
            ):
                src = (ROOT / relpath).read_text(encoding="utf-8")
                with self.subTest(path=relpath):
                    self.assertNotIn("copy_message", src)
                    self.assertNotIn("all_registered_ids", src)

    def test_every_bot_clears_the_blocked_flag_on_start(self) -> None:
        for pkg in BOTS:
            src = (ROOT / f"bots/{pkg}/services/auth_service.py").read_text(
                encoding="utf-8"
            )
            with self.subTest(bot=pkg):
                self.assertIn("user.is_blocked = False", src)


class StartupResumeTests(unittest.TestCase):
    def test_every_entrypoint_resumes_unfinished_broadcasts(self) -> None:
        for name in (*POLLING_ENTRYPOINTS, "main.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(entrypoint=name):
                self.assertTrue(
                    re.search(r"resume_pending\(", src),
                    f"{name} never resumes interrupted broadcasts",
                )

    def test_every_entrypoint_parks_broadcasts_on_shutdown(self) -> None:
        """Otherwise Ctrl+C tears the DB engine down under a live send loop
        and leaves the job's lease held by a dead process."""
        for name in (*POLLING_ENTRYPOINTS, "main.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(entrypoint=name):
                self.assertTrue(
                    re.search(r"\.pause\(\)", src),
                    f"{name} never parks a running broadcast on shutdown",
                )

    def test_polling_parks_before_closing_the_bot_and_engine(self) -> None:
        for name in POLLING_ENTRYPOINTS:
            src = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(entrypoint=name):
                self.assertLess(
                    src.index(".pause()"),
                    src.index("bot.session.close()"),
                    f"{name} closes the bot session before parking the broadcast",
                )

    def test_webhook_entrypoint_covers_all_five_bots(self) -> None:
        # Read the source rather than importing: main.py pulls in uvicorn,
        # which the bare test environment does not need.
        src = (ROOT / "main.py").read_text(encoding="utf-8")
        block = re.search(r"BROADCAST_ENGINES\s*=\s*\{(.*?)\}", src, re.S)
        self.assertIsNotNone(block, "main.py has no BROADCAST_ENGINES registry")
        for key in BOTS.values():
            with self.subTest(bot=key):
                self.assertIn(f'"{key}"', block.group(1))


if __name__ == "__main__":
    unittest.main()
