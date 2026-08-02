"""Unit tests for the "Faqat ballarni tozalash" admin reset, shared by all bots.

Clearing scores must zero every point source on the user row — score, referral
counter, test-solved and certificate flags — and drop the test sessions behind
them, while leaving the referral links (`referred_by`) alone: wiping those is
the separate "Yangi loyiha boshlash" button's job.

They use a recording session, so they run with no database.

Run:  PYTHONPATH=. python -m pytest tests/test_score_reset.py -v
"""

import asyncio
import importlib
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

BOTS = [
    "kitobxon",
    "Kitobmillatbot",
    "Millatchiroqlaribot",
    "Barakali_tanlov_bot",
    "Manfaadli_konkurs_bot",
]


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect())).lower()


class RecordingSession:
    """In-memory stand-in for AsyncSession that keeps the statements.

    Rowcounts are keyed by statement kind so a test can tell the session wipe
    apart from the user update.
    """

    def __init__(self, *, deleted: int = 4, updated: int = 6, scalar: int = 3) -> None:
        self.statements: list = []
        self.deleted = deleted
        self.updated = updated
        self.scalar = scalar
        self.flush_calls = 0

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)
        sql = _sql(statement)
        rowcount = self.deleted if sql.startswith("delete") else self.updated
        return SimpleNamespace(rowcount=rowcount, scalar_one=lambda: self.scalar)

    async def flush(self) -> None:
        self.flush_calls += 1

    def sql_of_kind(self, kind: str) -> list[str]:
        return [s for s in map(_sql, self.statements) if s.startswith(kind)]


def _user_repo(bot_name, session):
    mod = importlib.import_module(f"bots.{bot_name}.repositories.user_repo")
    return mod.UserRepository(session)


def _quiz_repo(bot_name, session):
    mod = importlib.import_module(f"bots.{bot_name}.repositories.quiz_repo")
    return mod.QuizRepository(session)


def _admin_service(bot_name, session):
    mod = importlib.import_module(f"bots.{bot_name}.services.admin_service")
    return mod.AdminService(session)


@pytest.mark.parametrize("bot", BOTS)
def test_reset_zeroes_every_point_source(bot):
    session = RecordingSession()
    repo = _user_repo(bot, session)

    asyncio.run(repo.reset_all_scores())

    set_clause = _sql(session.statements[0]).split(" where ")[0]
    for column in ("score", "referrals_count", "test_solved", "certificate_received"):
        assert column in set_clause, column


@pytest.mark.parametrize("bot", BOTS)
def test_reset_keeps_the_referral_links(bot):
    """Who-invited-whom belongs to "Yangi loyiha boshlash", not to this button."""
    session = RecordingSession()
    repo = _user_repo(bot, session)

    asyncio.run(repo.reset_all_scores())

    set_clause = _sql(session.statements[0]).split(" where ")[0]
    assert "referred_by" not in set_clause
    assert "referral_bonus_awarded" not in set_clause


@pytest.mark.parametrize("bot", BOTS)
def test_reset_skips_rows_that_are_already_clean(bot):
    session = RecordingSession()
    repo = _user_repo(bot, session)

    asyncio.run(repo.reset_all_scores())

    where_clause = _sql(session.statements[0]).split(" where ", 1)[1]
    assert "score" in where_clause
    assert "referrals_count" in where_clause
    assert "test_solved" in where_clause
    assert "certificate_received" in where_clause


@pytest.mark.parametrize("bot", BOTS)
def test_reset_returns_affected_row_count(bot):
    session = RecordingSession(updated=23)
    repo = _user_repo(bot, session)

    assert asyncio.run(repo.reset_all_scores()) == 23


@pytest.mark.parametrize("bot", BOTS)
def test_count_scored_users_matches_the_reset_filter(bot):
    session = RecordingSession(scalar=17)
    repo = _user_repo(bot, session)

    assert asyncio.run(repo.count_scored_users()) == 17
    sql = _sql(session.statements[0])
    assert sql.startswith("select count(")
    for column in ("score", "referrals_count", "test_solved", "certificate_received"):
        assert column in sql, column


@pytest.mark.parametrize("bot", BOTS)
def test_delete_all_sessions_wipes_the_session_table(bot):
    session = RecordingSession(deleted=31)
    repo = _quiz_repo(bot, session)

    assert asyncio.run(repo.delete_all_sessions()) == 31
    sql = _sql(session.statements[0])
    assert sql.startswith("delete from ")
    assert sql.rstrip().endswith("_test_sessions")  # unconditional, no WHERE
    assert session.flush_calls == 1


@pytest.mark.parametrize("bot", BOTS)
def test_apply_reset_wipes_sessions_and_users(bot):
    session = RecordingSession(deleted=12, updated=8)
    service = _admin_service(bot, session)

    result = asyncio.run(service.apply_score_reset())

    assert result.deleted_sessions == 12
    assert result.cleared_users == 8
    assert len(session.sql_of_kind("delete")) == 1
    assert len(session.sql_of_kind("update")) == 1


@pytest.mark.parametrize("bot", BOTS)
def test_preview_reports_totals_without_writing(bot):
    session = RecordingSession(scalar=9)
    service = _admin_service(bot, session)

    preview = asyncio.run(service.preview_score_reset())

    assert preview.total_users == 9
    assert preview.scored_users == 9
    assert preview.test_sessions == 9
    assert all(_sql(stmt).startswith("select") for stmt in session.statements)


@pytest.mark.parametrize("bot", BOTS)
def test_admin_panel_exposes_the_clear_scores_button(bot):
    reply = importlib.import_module(f"bots.{bot}.keyboards.reply")

    texts = {button.text for row in reply.admin_panel().keyboard for button in row}
    assert reply.ADMIN_BUTTON_CLEAR_SCORES in texts
