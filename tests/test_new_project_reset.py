"""Unit tests for the "Yangi loyiha boshlash" admin reset, shared by all bots.

Starting a new project only reopens who-invited-whom: `referred_by` is cleared
and the one-time bonus claim is unlocked so an existing bot member can be
invited again. Scores and referral counters are project history and must
survive the reset untouched — that is the invariant these tests pin down.

They use a recording session, so they run with no database.

Run:  PYTHONPATH=. python -m pytest tests/test_new_project_reset.py -v
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


class RecordingSession:
    """In-memory stand-in for AsyncSession that keeps the statements."""

    def __init__(self, *, rowcount: int = 7, scalar: int = 3) -> None:
        self.statements: list = []
        self.rowcount = rowcount
        self.scalar = scalar
        self.flush_calls = 0

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return SimpleNamespace(
            rowcount=self.rowcount,
            scalar_one=lambda: self.scalar,
        )

    async def flush(self) -> None:
        self.flush_calls += 1


def _user_repo(bot_name, session):
    mod = importlib.import_module(f"bots.{bot_name}.repositories.user_repo")
    return mod.UserRepository(session)


def _admin_service(bot_name, session):
    mod = importlib.import_module(f"bots.{bot_name}.services.admin_service")
    return mod.AdminService(session)


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect())).lower()


@pytest.mark.parametrize("bot", BOTS)
def test_reset_clears_only_the_referral_link_columns(bot):
    session = RecordingSession()
    repo = _user_repo(bot, session)

    asyncio.run(repo.reset_referral_links())

    sql = _sql(session.statements[0])
    assert sql.startswith("update ")
    set_clause = sql.split(" where ")[0]
    assert "referred_by" in set_clause
    assert "referral_bonus_awarded" in set_clause
    # The whole point of the reset: history stays.
    assert "score" not in set_clause
    assert "referrals_count" not in set_clause


@pytest.mark.parametrize("bot", BOTS)
def test_reset_touches_only_rows_that_still_hold_referral_state(bot):
    session = RecordingSession()
    repo = _user_repo(bot, session)

    asyncio.run(repo.reset_referral_links())

    where_clause = _sql(session.statements[0]).split(" where ", 1)[1]
    assert "referred_by is not null" in where_clause
    assert " or " in where_clause
    assert "referral_bonus_awarded" in where_clause


@pytest.mark.parametrize("bot", BOTS)
def test_reset_returns_affected_row_count(bot):
    session = RecordingSession(rowcount=42)
    repo = _user_repo(bot, session)

    assert asyncio.run(repo.reset_referral_links()) == 42


@pytest.mark.parametrize("bot", BOTS)
def test_count_referred_users_only_counts_linked_users(bot):
    session = RecordingSession(scalar=11)
    repo = _user_repo(bot, session)

    assert asyncio.run(repo.count_referred_users()) == 11
    sql = _sql(session.statements[0])
    assert sql.startswith("select count(")
    assert "referred_by is not null" in sql


@pytest.mark.parametrize("bot", BOTS)
def test_apply_reset_flushes_and_reports_cleared_users(bot):
    session = RecordingSession(rowcount=5)
    service = _admin_service(bot, session)

    result = asyncio.run(service.apply_new_project_reset())

    assert result.cleared_users == 5
    assert session.flush_calls == 1


@pytest.mark.parametrize("bot", BOTS)
def test_preview_reports_totals_without_writing(bot):
    session = RecordingSession(scalar=9)
    service = _admin_service(bot, session)

    preview = asyncio.run(service.preview_new_project_reset())

    assert preview.total_users == 9
    assert preview.referred_users == 9
    assert all(_sql(stmt).startswith("select") for stmt in session.statements)


@pytest.mark.parametrize("bot", BOTS)
def test_admin_panel_exposes_the_new_project_button(bot):
    reply = importlib.import_module(f"bots.{bot}.keyboards.reply")

    texts = {
        button.text
        for row in reply.admin_panel().keyboard
        for button in row
    }
    assert reply.ADMIN_BUTTON_NEW_PROJECT in texts


@pytest.mark.parametrize("bot", BOTS)
def test_registered_users_can_be_referred_again(bot):
    """The /start referral gate must not exclude already-registered users."""
    import inspect

    start = importlib.import_module(f"bots.{bot}.handlers.start")
    source = inspect.getsource(start.cmd_start)

    assert "not result.user.referred_by" in source
    assert "not result.user.is_registered and not result.user.referred_by" not in source
